from elftools.elf.elffile import ELFFile
from pydbg.symbols import Symbol, SymbolType

elftools_symtypes = {
    'STT_FUNC': SymbolType.FUNCTION,
    'STT_OBJECT': SymbolType.OBJECT
}

PLT_HEADER_SIZE = 16
PLT_STUB_SIZE = 16

class ELFFileParser:
    def __init__(self, file_name : str):
        self.file = open(file_name, 'rb')
        self.elffile = ELFFile(self.file)

    def get_elf_symbols(self) -> list[Symbol]:
        symbols = []
        symtab = self.elffile.get_section_by_name('.symtab')
        dynsym = self.elffile.get_section_by_name('.dynsym')
        if symtab is not None:
            for symbol in symtab.iter_symbols():
                name = symbol.name
                plt_address = symbol['st_value']
                if plt_address == 0:
                    continue  # skip symbols with no address, which are likely external or undefined. in this case, we will resolve them through the PLT later
                size = symbol['st_size']
                st_info = symbol['st_info']
                type = elftools_symtypes.get(st_info['type'], SymbolType.OTHER)
                symbols.append(Symbol(name, plt_address, size, type))
        else:
            # if .symtab is not available, try .dynsym for dynamic symbols
            if dynsym is not None:
                for symbol in dynsym.iter_symbols():
                    name = symbol.name
                    plt_address = symbol['st_value']
                    if plt_address == 0:
                        continue  # skip symbols with no address, which are likely external or undefined. in this case, we will resolve them through the PLT later
                    size = symbol['st_size']
                    st_info = symbol['st_info']
                    type = elftools_symtypes.get(st_info['type'], SymbolType.OTHER)
                    symbols.append(Symbol(name, plt_address, size, type))
        # resolve PLT entries for external functions
        plt_section = self.elffile.get_section_by_name('.plt')
        rela_plt = self.elffile.get_section_by_name('.rela.plt')
        if rela_plt is not None and plt_section is not None:
            plt_base = plt_section['sh_addr']
            for i, rel in enumerate(rela_plt.iter_relocations()):
                symbol_index = rel['r_info_sym']
                # get the symbol from the .dynsym section (always present there, even if .symtab doesn't exist)
                symbol = dynsym.get_symbol(symbol_index)
                name = symbol.name
                # PLT entries are sequential, after the header (16 bytes), each entry is 16 bytes, so we calculate the address directly
                plt_address = plt_base + PLT_HEADER_SIZE + i * PLT_STUB_SIZE
                symbols.append(Symbol(name + "_plt", plt_address, PLT_STUB_SIZE,  SymbolType.FUNCTION))
                # add the got entry for this symbol as well
                got_address = rel['r_offset']
                symbols.append(Symbol(name + '_got', got_address, size, SymbolType.OBJECT))
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