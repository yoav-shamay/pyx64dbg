from elftools.elf.elffile import ELFFile
from pyx64dbg.number_types import UInt64
from pyx64dbg.symbols import Symbol, SymbolType
from typing import BinaryIO

# mapping from elftools symbol types to our SymbolType enum
elftools_symtypes = {
    'STT_FUNC': SymbolType.FUNCTION,
    'STT_OBJECT': SymbolType.OBJECT
}

# constants for PLT entry sizes, used for resolving PLT symbols
PLT_HEADER_SIZE = 16
PLT_STUB_SIZE = 16

class ELFFileParser:
    """
    Class used to parse an ELF file and extract relevant information.
    Allows to parse symbols (which also includes got/plt entries), the entry point offset, check if it's a PIE binary and get the base address if it's not.
    Uses pyelftools to parse the ELF file.
    """
    def __init__(self, file_name : str):
        self.file: BinaryIO = open(file_name, 'rb')
        self.elffile: ELFFile = ELFFile(self.file)

    def get_elf_symbols(self) -> list[Symbol]:
        """
        Returns a list of Symbol instances representing the symbols in the ELF file.
        This includes symbols in the .symtab section (if present) or the .dynsym section (if .symtab is not present).
        In addition it includes PLT entries (as type FUNCTION) and GOT entries (as type OBJECT).
        They are named as the external symbol with a "_plt" or "_got" suffix
        """
        symbols: list[Symbol] = []
        symtab = self.elffile.get_section_by_name('.symtab')
        dynsym = self.elffile.get_section_by_name('.dynsym')
        if symtab is not None:
            # if we have .symtab, prefer parsing symbols from there.
            # Should be present in non-stripped binaries.
            for symbol in symtab.iter_symbols():
                name = symbol.name
                address = UInt64(symbol['st_value']) # convert the address to UInt64 from the int pyelftools gives us
                if address == 0:
                    continue  # skip symbols with no address, which are likely external or undefined. in this case, we will resolve them through the PLT later
                size = symbol['st_size']
                st_info = symbol['st_info']
                # get the symbol type using the mapping, default to OTHER if we don't recognize it
                symbol_type = elftools_symtypes.get(st_info['type'], SymbolType.OTHER)
                symbols.append(Symbol(name, address, size, symbol_type))
        elif dynsym is not None:
            # if .symtab is not available, try .dynsym for dynamic symbols
            for symbol in dynsym.iter_symbols():
                name = symbol.name
                address = UInt64(symbol['st_value']) # convert the address to UInt64 from the int pyelftools gives us
                if address == 0:
                    continue  # skip symbols with no address, which are likely external or undefined. in this case, we will resolve them through the PLT later
                size = symbol['st_size']
                st_info = symbol['st_info']
                symbol_type = elftools_symtypes.get(st_info['type'], SymbolType.OTHER)
                symbols.append(Symbol(name, address, size, symbol_type))
        # resolve PLT entries for external functions, only if there's a dynsym section (otherwise the binary is static and doesn't have external symbols or a PLT)
        if dynsym is not None:
            plt_section = self.elffile.get_section_by_name('.plt')
            rela_plt = self.elffile.get_section_by_name('.rela.plt')
            if rela_plt is not None and plt_section is not None:
                # if we have both .rela.plt and .plt sections, we can resolve the PLT entries to get plt and got symbols
                plt_base = plt_section['sh_addr'] # get the plt base offset, to calculate the address of each PLT entry
                for i, rel in enumerate(rela_plt.iter_relocations()):
                    symbol_index = rel['r_info_sym'] # the index of the symbol in the .dynsym section
                    # get the symbol from the .dynsym section (always present there, even if .symtab doesn't exist)
                    symbol = dynsym.get_symbol(symbol_index)
                    name = symbol.name # the name of the external symbol
                    # PLT entries are sequential, after the header (16 bytes), each entry is 16 bytes
                    plt_address = plt_base + PLT_HEADER_SIZE + i * PLT_STUB_SIZE
                    plt_sym_name = name + "_plt" # to indicate plt symbols, add a "_plt" suffix to the name
                    symbols.append(Symbol(plt_sym_name, plt_address, PLT_STUB_SIZE,  SymbolType.FUNCTION))
                    # add the got entry for this symbol as well
                    got_address = rel['r_offset'] # the got offset in the ELF is given directly in the relocation entry
                    got_sym_name = name + "_got" # to indicate got symbols, add a "_got" suffix to the name
                    symbols.append(Symbol(got_sym_name, got_address, size, SymbolType.OBJECT))
        return symbols
    
    def get_entry_point_offset(self) -> int:
        """
        Returns the entry point offset of the ELF file.
        """
        return self.elffile.header['e_entry']

    def is_pie(self) -> bool:
        """
        Returns True if the ELF file is a PIE binary, False otherwise.
        """
        return self.elffile.header['e_type'] == 'ET_DYN'
    
    def get_load_base_address(self) -> int:
        """
        Returns the load base address of the ELF file, for non-PIE binaries.
        Raises an exception if the binary is a PIE, as it doesn't have a fixed load base address.
        """
        if self.is_pie():
            raise ValueError("PIE binaries don't have a fixed load base address")
        # the load base address is the virtual address of the first LOAD segment in the ELF file
        for segment in self.elffile.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                return segment['p_vaddr']
        raise ValueError("No LOAD segment found in ELF file")

    def close(self) -> None:
        """
        Closes the file associated with this ELFFileParser instance.
        """
        if not self.file.closed:
            self.file.close()
    
    def __enter__(self):
        """
        Context manager entry, returns self to allow using with statement.
        Every initialization is done in the constructor already.
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit, closes the file when exiting the with statement.
        """
        self.close()