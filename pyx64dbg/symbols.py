from __future__ import annotations

import bisect
from enum import Enum
import heapq
from pyx64dbg.number_types import CIntBase, UInt64

class SymbolType(Enum):
    """
    An enum representing the type of a symbol.
    Can be either a function, object, or something else (other).
    """
    FUNCTION = 1
    OBJECT = 2
    OTHER = 3

class Symbol:
    """
    An object representing a symbol in the debugged process.
    Has a name, address, size and type (function/object/other).
    """
    def __init__(self, name: str, address: UInt64, size: int, symbol_type: SymbolType) -> None:
        self.name: str = name
        self.address: UInt64 = address
        self.size: int = size
        self.type: SymbolType = symbol_type

    def __repr__(self) -> str:
        """
        Returns showcase of the symbol.
        Format: Symbol(name=..., address=0x..., size=..., type=...)
        """
        return f"Symbol(name={self.name}, address={hex(self.address)}, size={self.size}, type={self.type})"

class Symbols:
    """
    A class representing the symbols of the executable or a shared object.
    Allows looking up symbols by name or by address, and also provides convenient access to function and object symbols separately.
    The address of the symbols is absolute, including the base address of the executable / shared object.
    """
    def __init__(self, symbols: list[Symbol], load_bias: UInt64=UInt64(0)) -> None:
        self.symbols: list[Symbol] = symbols
        self._setup_load_bias(load_bias)
        self._init_symbol_dicts()
        self._init_sorted_symbols()
    
    def _setup_load_bias(self, load_bias: UInt64):
        """
        A helper function that adds the base address to the symbol addresses (which are offsets at initialization).
        """
        for symbol in self.symbols:
            symbol.address += load_bias

    def _init_symbol_dicts(self):
        """
        A helper function that initializes the dictionaries for function and object symbols, for convenient access by name.
        """
        self.functions: dict[str, Symbol] = {}
        self.objects: dict[str, Symbol] = {}
        for symbol in self.symbols:
            if symbol.type == SymbolType.FUNCTION:
                self.functions[symbol.name] = symbol
            elif symbol.type == SymbolType.OBJECT:
                self.objects[symbol.name] = symbol
    
    def _init_sorted_symbols(self):
        """
        A helper function that initializes a sorted list of symbols by address, for efficient lookup by address.
        Creates a disjoint sorted list of tuples (start_address, end_address, symbol) sorted by start_address, where end_address is start_address + size.
        If multiple symbols overlap, the ranges will still be disjoint, and in each range the smallest symbol containing that range will be used.
        Therefore, the same symbol can appear multiple times in the list.
        """
        events: list[tuple[UInt64, Symbol, bool]] = [] # list of (address, symbol, is_start) for the start and end of each symbol
        for symbol in self.symbols:
            if symbol.type not in (SymbolType.FUNCTION, SymbolType.OBJECT) or symbol.size == 0:
                # we only include function and object symbols in the sorted list, as other symbols can be confusing to access by address and aren't as useful for most use cases
                # Also symbols with size 0 can't include addresses (their range is empty) so we skip them as well
                continue
            events.append((symbol.address, symbol, True)) # start of the symbol
            events.append((symbol.address + symbol.size, symbol, False)) # end of the symbol
        events.sort(key=lambda x: x[0]) # sort by address
        active_symbols: set[Symbol] = set() # set of currently active symbols (symbols that have started but not ended yet)
        # A heap of active symbols sorted by size, to efficiently get the smallest active symbol
        # Uses a lazy deletion approach, where the heap might include inactive symbols. We'll delete only the top symbol when it isn't active.
        # Contains a tuple of (size, id, name) to sort by size, and if sizes are equal, sort by id to ensure consistency.
        active_symbols_heap: list[tuple[int, int, Symbol]] = []
        # Tuple of (start_address, end_address, symbol_name) sorted by start_address, representing the disjoint ranges of addresses covered by the symbols, and the smallest symbol covering that range.
        # the range is [start_address, end_address) (inclusive of start_address and exclusive of end_address)
        self._sorted_ranges: list[tuple[UInt64, UInt64, Symbol]] = []
        last_address: UInt64 | None = None
        for address, symbol, is_start in events:
            if last_address is not None and last_address < address:
                # if we have a last address and it's less than the current address, we have a range of addresses between last_address and address that is covered by the currently active symbols
                # Before accessing the top remove any inactive symbols from the top of the heap (lazy deletion)
                while active_symbols_heap and active_symbols_heap[0][2] not in active_symbols:
                    heapq.heappop(active_symbols_heap)
                if len(active_symbols_heap) > 0:
                    # if the list isn't empty, the smallest active symbol is the one at the top of the heap
                    smallest_active_symbol = active_symbols_heap[0][2]
                    self._sorted_ranges.append((last_address, address, smallest_active_symbol))
            last_address = address
            if is_start:
                # if a start, add to heap and active symbols set
                active_symbols.add(symbol)
                heapq.heappush(active_symbols_heap, (symbol.size, id(symbol), symbol))
            else:
                # if an end, remove from active symbols set
                active_symbols.remove(symbol)

    
    def get_symbol_by_address(self, address: int | CIntBase) -> Symbol | None:
        """
        A function to lookup a symbol by its address.
        Uses binary search on the sorted list of symbols by address for efficient lookup.
        """
        address = UInt64(address) # convert to UInt64 if it's something else
        # find the closest symbol with an address less than or equal to the given address
        # we need to subtract 1 as it returns the first greater than it
        closest_symbol = bisect.bisect_right(self._sorted_ranges, address, key=lambda x: x[0]) - 1
        if closest_symbol >= 0: # if we found a symbol (the index isn't negative)
            start_address, end_address, symbol = self._sorted_ranges[closest_symbol]
            if start_address <= address < end_address:
                # verify that the address is actually within the range
                return symbol
        return None # if we didn't find a symbol that contains the given address, return None
    
    def get_symbol_by_name(self, name: str) -> Symbol | None:
        """
        Returns the symbol with the given name, or None if it doesn't exist.
        Checks both function and object symbols.
        Doesn't check other symbols, as they are not relevant for most use cases and can cause confusion if accessed by name.
        """
        if name in self.functions:
            return self.functions[name]
        elif name in self.objects:
            return self.objects[name]
        else:
            return None

    def __getattr__(self, name: str) -> UInt64:
        """
        Allow accessing symbols as attributes of the Symbols object, for convenience.
        Returns the address of the symbol with the given name.
        For example, if there's a function symbol named 'main', it can be accessed as symbols.main to get its address.
        Checks both function and object symbols, but not other symbols, for the same reason as in get_symbol_by_name.
        """
        res = self.get_symbol_by_name(name)
        if res is not None:
            return res.address
        else: # we didn't find a symbol
            raise AttributeError(f"Symbol '{name}' not found")
    
    def __getitem__(self, name: str) -> UInt64:
        """
        Allow accessing symbols using dictionary-like syntax as well, for convenience.
        Returns the address of the symbol with the given name.
        For example, symbols['main'] would return the address of the 'main' function symbol.
        Checks both function and object symbols, but not other symbols, for the same reason as in get_symbol_by_name.
        """
        res = self.get_symbol_by_name(name)
        if res is not None:
            return res.address
        else: # we didn't find a symbol
            raise KeyError(name)
    
    def __repr__(self) -> str:
        """
        Returns a string representation of the Symbols object.
        Format: Symbols([
            Symbol(name=..., address=0x..., size=..., type=...),
            Symbol(name=..., address=0x..., size=..., type=...),
            ...
        ])
        """
        res_str = "Symbols([\n"
        for symbol in self.symbols:
            res_str += f"  {repr(symbol)}\n"
        res_str += "])"
        return res_str
