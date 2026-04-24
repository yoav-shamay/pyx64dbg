from pydbg.parse_elf import ELFFileParser
from pydbg.symbols import Symbols
import os

class SharedObject:
    def __init__(self, base_address: int, file_path: str):
        self.base_address = base_address
        self.file_path = file_path
        # get the file name from the file path
        self.name = os.path.basename(file_path)
        with ELFFileParser(file_path) as elf_parser:
            symbol_list = elf_parser.get_elf_symbols()
        self.symbols = Symbols(symbol_list, self.base_address)