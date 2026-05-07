from typing import Callable
from pyx64dbg.utils import get_first_byte, change_first_byte
import pyx64dbg.ptrace as ptrace
from pyx64dbg.cint import CInt

# the breakpoint instruction in x86_64. It's a single CC byte.
BREAKPOINT_INSTRUCTION = 0xCC

class Breakpoints:
    """
    Handles the breakpoint list.
    Allows to add/remove/get breakpoints.
    Uses software breakpoints, placing an 0xCC byte at the address.
    """
    def __init__(self, child_pid: int, ensure_running: Callable, trigger_update_callbacks: callable) -> None:
        self.addresses: set[int] = set()
        self.original_bytes: dict[int, int] = {}
        self.child_pid: int = child_pid
        self._ensure_running: Callable = ensure_running
        self._trigger_update_callbacks: Callable = trigger_update_callbacks

    def get_breakpoints(self) -> list[int]:
        """
        Returns a list of the current breakpoints.
        """
        self._ensure_running()
        return self.addresses
    
    def add_breakpoint(self, address : CInt | int, notify_updates: bool = True) -> None:
        """
        Adds a breakpoint at the given address.
        """
        self._ensure_running()
        address = int(address) # convert to int if it's a CInt
        if address in self.addresses:
            return
        original_word = ptrace.peekdata(self.child_pid, address) # take the original word at the address
        breakpoint_word = change_first_byte(original_word, BREAKPOINT_INSTRUCTION) # change the first byte to a breakpoint
        ptrace.pokedata(self.child_pid, address, breakpoint_word) # write it to the memory
        self.addresses.add(address)
        self.original_bytes[address] = get_first_byte(original_word) # save the original byte
        if notify_updates:
            self._trigger_update_callbacks()
    
    def remove_breakpoint(self, address : CInt | int, notify_updates: bool = True) -> None:
        """
        Removes a breakpoint at the given address.
        """
        self._ensure_running()
        address = int(address) # convert to int if it's a CInt
        if address not in self.addresses: # check if it's actually a breakpoint before trying to remove it
            raise ValueError("Addresses isn't a breakpoint")
        original_byte = self.original_bytes[address] # get the original byte for the address
        breakpoint_word = ptrace.peekdata(self.child_pid, address) # get the full word as we can only write a word at a time
        non_breakpoint_word = change_first_byte(breakpoint_word, original_byte)
        ptrace.pokedata(self.child_pid, address, non_breakpoint_word)
        self.addresses.remove(address) # remove the address from the breakpoints set and original bytes dict
        del self.original_bytes[address]
        if notify_updates:
            self._trigger_update_callbacks()