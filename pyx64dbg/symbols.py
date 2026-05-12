import bisect
from enum import Enum

from pyx64dbg.number_types import CNumBase, UInt64

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
    def __init__(self, symbols: list[Symbol], base_address: UInt64=UInt64(0)) -> None:
        self.symbols: list[Symbol] = symbols
        self.base_address: UInt64 = base_address
        self._setup_base_address()
        self._init_symbol_dicts()
        self._init_sorted_symbols()
    
    def _setup_base_address(self):
        """
        A helper function that adds the base address to the symbol addresses (which are offsets at initialization).
        """
        for symbol in self.symbols:
            symbol.address += self.base_address

    def _init_symbol_dicts(self):
        """
        A helper function that initializes the dictionaries for function and object symbols, for convenient access by name.
        """
        self.functions: dict[str, UInt64] = {}
        self.objects: dict[str, UInt64] = {}
        for symbol in self.symbols:
            if symbol.type == SymbolType.FUNCTION:
                self.functions[symbol.name] = symbol.address
            elif symbol.type == SymbolType.OBJECT:
                self.objects[symbol.name] = symbol.address
    
    def _init_sorted_symbols(self):
        """
        A helper function that initializes a sorted list of symbols by address, for efficient lookup by address.
        The list is a list of tuples of (address, symbol), sorted by address.
        """
        self.sorted_addresses: list[tuple[UInt64, Symbol]] = []
        for symbol in self.symbols:
            if symbol.type in (SymbolType.FUNCTION, SymbolType.OBJECT): # only include relevant symbols
                self.sorted_addresses.append((symbol.address, symbol))
            
        self.sorted_addresses.sort(key=lambda x: x[0]) # sort by address

    
    def get_symbol_by_address(self, address: CNumBase) -> Symbol | None:
        """
        A function to lookup a symbol by its address.
        Uses binary search on the sorted list of symbols by address for efficient lookup.
        """
        address = UInt64(address) # convert to UInt64 if it's something else
        # find the closest symbol with an address less than or equal to the given address
        # we need to subtract 1 as it returns the first greater than it
        closest_symbol = bisect.bisect_right(self.sorted_addresses, address, key=lambda x: x[0]) - 1
        if closest_symbol > 0: # if we found a symbol (the index isn't negative)
            symbol_address, symbol = self.sorted_addresses[closest_symbol]
            if symbol_address <= address < symbol_address + symbol.size:
                return symbol
        return None # if we didn't find a symbol that contains the given address, return None
    
    def get_symbol_by_name(self, name: str) -> UInt64 | None:
        """
        Returns the address of the symbol with the given name, or None if it doesn't exist.
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
        For example, if there's a function symbol named 'main', it can be accessed as symbols.main to get its address.
        Checks both function and object symbols, but not other symbols, for the same reason as in get_symbol_by_name.
        """
        res = self.get_symbol_by_name(name)
        if res is not None:
            return res
        else: # we didn't find a symbol
            raise AttributeError(f"Symbol '{name}' not found")
    
    def __getitem__(self, name: str) -> UInt64:
        """
        Allow accessing symbols using dictionary-like syntax as well, for convenience.
        For example, symbols['main'] would return the address of the 'main' function symbol.
        Checks both function and object symbols, but not other symbols, for the same reason as in get_symbol_by_name.
        """
        res = self.get_symbol_by_name(name)
        if res is not None:
            return res
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
            res_str += f"  {symbol}\n"
        res_str += "])"
        return res_str
