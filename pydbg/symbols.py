import bisect
from enum import Enum

class SymbolType(Enum):
    FUNCTION = 1
    OBJECT = 2
    OTHER = 3

class Symbol:
    def __init__(self, name : str, address : int, size: int, type : SymbolType):
        self.name = name
        self.address = address
        self.size = size
        self.type = type
    
    def __repr__(self):
        return f"Symbol(name={self.name}, address={hex(self.address)}, size={self.size}, type={self.type})"

class Symbols:
    def __init__(self, symbols, base_address=0):
        self.symbols = symbols
        self.base_address = base_address
        self._setup_base_address()
        self._init_symbol_dicts()
        self._init_sorted_symbols()
    
    def _setup_base_address(self):
        for symbol in self.symbols:
            symbol.address += self.base_address

    def _init_symbol_dicts(self):
        self.functions = {}
        self.objects = {}
        for symbol in self.symbols:
            if symbol.type == SymbolType.FUNCTION:
                self.functions[symbol.name] = symbol.address
            elif symbol.type == SymbolType.OBJECT:
                self.objects[symbol.name] = symbol.address
    
    def _init_sorted_symbols(self):
        self.sorted_addresses = []
        for symbol in self.symbols:
            if symbol.type in (SymbolType.FUNCTION, SymbolType.OBJECT): # only include relevant symbols
                self.sorted_addresses.append((symbol.address, symbol))
            
        self.sorted_addresses.sort(key=lambda x: x[0]) # sort by address

    
    def get_symbol_by_address(self, address):
        closest_symbol = bisect.bisect_right(self.sorted_addresses, address, key=lambda x: x[0]) - 1 # find the closest symbol with an address less than or equal to the given address
        if closest_symbol >= 0:
            symbol_address, symbol = self.sorted_addresses[closest_symbol]
            if symbol_address <= address < symbol_address + symbol.size:
                return symbol
        return None
    
    def __getattr__(self, name):
        """
        Allow accessing symbols as attributes of the Symbols object, for convenience.
        For example, if there's a function symbol named 'main', it can be accessed as symbols.main to get its address.
        """
        if name in self.functions:
            return self.functions[name]
        elif name in self.objects:
            return self.objects[name]
        else:
            raise AttributeError(f"Symbol '{name}' not found")
    
    def __repr__(self):
        res_str = "Symbols([\n"
        for symbol in self.symbols:
            res_str += f"  {symbol}\n"
        res_str += "])"
        return res_str
