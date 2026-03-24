from utils import get_first_byte, change_first_byte
import ptrace

BREAKPOINT_INSTRUCTION = 0xCC

class Breakpoints:
    def __init__(self, child_pid):
        self.addresses = set()
        self.original_bytes = {}
        self.child_pid = child_pid
    
    def get_breakpoints(self):
        return self.addresses
    
    def add_breakpoint(self, address):
        if address in self.addresses:
            return
        original_word = ptrace.peekdata(self.child_pid, address)
        breakpoint_word = change_first_byte(original_word, BREAKPOINT_INSTRUCTION)
        ptrace.pokedata(self.child_pid, address, breakpoint_word)
        self.addresses.add(address)
        self.original_bytes[address] = get_first_byte(original_word)
    
    def remove_breakpoint(self, address):
        if address not in self.addresses:
            raise ValueError("Addresses isn't a breakpoint")
        original_byte = self.original_bytes[address]
        breakpoint_word = ptrace.peekdata(self.child_pid, address)
        non_breakpoint_word = change_first_byte(breakpoint_word, original_byte)
        ptrace.pokedata(self.child_pid, address, non_breakpoint_word)
        self.addresses.remove(address)
        del self.original_bytes[address]
    
    
    def _step_from_breakpoint(self, address):
        original_byte = self.original_bytes[address]
        breakpoint_word = ptrace.peekdata(self.child_pid, address)
        non_breakpoint_word = change_first_byte(breakpoint_word, original_byte)
        ptrace.pokedata(self.child_pid, address, non_breakpoint_word)
        ptrace.single_step(self.child_pid)
        ptrace.pokedata(self.child_pid, address, breakpoint_word)
        