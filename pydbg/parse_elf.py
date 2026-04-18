from elftools.elf.elffile import ELFFile
from symbols import Symbol, SymbolType

elftools_symtypes = {
    'STT_FUNC': SymbolType.FUNCTION,
    'STT_OBJECT': SymbolType.OBJECT
}

class ELFFileParser:
    def __init__(self, file_name : str):
        self.file = open(file_name, 'rb')
        self.elffile = ELFFile(self.file)

    def get_elf_symbols(self) -> list[Symbol]:
        symbols = []
        symtab = self.elffile.get_section_by_name('.symtab')
        if symtab is not None:
            for symbol in symtab.iter_symbols():
                name = symbol.name
                address = symbol['st_value']
                size = symbol['st_size']
                st_info = symbol['st_info']
                type = elftools_symtypes.get(st_info['type'], SymbolType.OTHER)
                symbols.append(Symbol(name, address, size, type))
        return symbols
    
    def get_entry_point(self) -> int:
        return self.elffile.header['e_entry']

    def close(self) -> None:
        if not self.file.closed:
            self.file.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()