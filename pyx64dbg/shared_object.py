from pyx64dbg.number_types import UInt64
from pyx64dbg.parse_elf import ELFFileParser
from pyx64dbg.symbols import Symbols
import os

class SharedObject:
    """
    Represents a shared object (so file) loaded in the debugged process.
    Saves the base address, file path, name (only the file name, without the path), and symbols of the shared object.
    The symbols are parsed from the shared object file using ELFFileParser, and their addresses are adjusted according to the ASLR loaded base address of the shared object.
    """
    def __init__(self, base_address: UInt64, file_path: str):
        self.base_address: UInt64 = base_address
        self.file_path: str = file_path
        # get the file name from the file path
        self.name: str = os.path.basename(file_path)
        with ELFFileParser(file_path) as elf_parser:
            symbol_list = elf_parser.get_elf_symbols()
        self.symbols: Symbols = Symbols(symbol_list, self.base_address)