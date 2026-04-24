from pyx64dbg.utils import get_first_byte, change_first_byte
import pyx64dbg.ptrace as ptrace
from pyx64dbg.cint import CInt
import os

BREAKPOINT_INSTRUCTION = 0xCC

class Breakpoints:
    def __init__(self, child_pid, ensure_running):
        self.addresses = set()
        self.original_bytes = {}
        self.child_pid = child_pid
        self._ensure_running = ensure_running
    
    def get_breakpoints(self):
        """
        Returns a list of the current breakpoints.
        """
        self._ensure_running()
        return self.addresses
    
    def add_breakpoint(self, address : CInt | int):
        """
        Adds a breakpoint at the given address.
        """
        self._ensure_running()
        address = int(address) # convert to int if it's a CInt
        if address in self.addresses:
            return
        original_word = ptrace.peekdata(self.child_pid, address)
        breakpoint_word = change_first_byte(original_word, BREAKPOINT_INSTRUCTION)
        ptrace.pokedata(self.child_pid, address, breakpoint_word)
        self.addresses.add(address)
        self.original_bytes[address] = get_first_byte(original_word)
    
    def remove_breakpoint(self, address : CInt | int):
        """
        Removes a breakpoint at the given address.
        """
        self._ensure_running()
        address = int(address) # convert to int if it's a CInt
        if address not in self.addresses:
            raise ValueError("Addresses isn't a breakpoint")
        original_byte = self.original_bytes[address]
        breakpoint_word = ptrace.peekdata(self.child_pid, address)
        non_breakpoint_word = change_first_byte(breakpoint_word, original_byte)
        ptrace.pokedata(self.child_pid, address, non_breakpoint_word)
        self.addresses.remove(address)
        del self.original_bytes[address]
        