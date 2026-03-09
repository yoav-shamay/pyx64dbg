from utils import get_first_byte, change_first_byte

BREAKPOINT_INSTRUCTION = 0xCC

class Breakpoints:
    def __init__(self, ptrace):
        self.addresses = set()
        self.original_bytes = {}
        self.ptrace = ptrace
    
    def get_breakpoints(self):
        return self.addresses
    
    def add_breakpoint(self, address):
        if address in self.addresses:
            return
        original_word = self.ptrace.peekdata(address)
        breakpoint_word = change_first_byte(original_word, BREAKPOINT_INSTRUCTION)
        self.ptrace.pokedata(address, breakpoint_word)
        self.addersses.add(address)
        self.original_bytes[address] = get_first_byte(original_word)
    
    def remove_breakpoint(self, address):
        if address not in self.addresses:
            raise ValueError("Addresses isn't a breakpoint")
        original_byte = self.original_bytes[address]
        breakpoint_word = self.ptrace.peekdata(address)
        non_breakpoint_word = change_first_byte(breakpoint_word, original_byte)
        self.ptrace.pokedata(address, non_breakpoint_word)
        self.addresses.remove(address)
        self.original_bytes.remove(address)
    
    
    def step_from_breakpoint(self, address):
        original_byte = self.original_bytes[address]
        breakpoint_word = self.ptrace.peekdata(address)
        non_breakpoint_word = change_first_byte(breakpoint_word, original_byte)
        self.ptrace.pokedata(address, non_breakpoint_word)
        self.ptrace.single_step()
        self.ptrace.pokedata(address, breakpoint_word)
        