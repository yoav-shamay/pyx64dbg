from __future__ import annotations

from typing import TYPE_CHECKING
import pyx64dbg.os_interaction as os_interaction
from pyx64dbg.number_types import CIntBase, UInt64

# the breakpoint instruction in x86_64. It's a single CC byte.
BREAKPOINT_INSTRUCTION = 0xCC
# bytes representation of the breakpoint instruction, used for writing to memory.
BREAKPOINT_INSTRUCTION_BYTES = bytes([BREAKPOINT_INSTRUCTION])

if TYPE_CHECKING:
    from pyx64dbg.debugger import Debugger

class Breakpoints:
    """
    Handles the breakpoint list.
    Allows to add/remove/get breakpoints.
    Uses software breakpoints, placing an 0xCC byte at the address.
    """
    def __init__(self, debugger: Debugger) -> None:
        self._addresses: set[UInt64] = set()
        self._original_bytes: dict[UInt64, int] = {}
        self._debugger: Debugger = debugger

    def get_breakpoints(self) -> set[UInt64]:
        """
        Returns a set of the current breakpoints.
        """
        self._debugger._ensure_running()
        return self._addresses
    
    def add_breakpoint(self, address : CIntBase | int, notify_updates: bool = True) -> None:
        """
        Adds a breakpoint at the given address.
        """
        self._debugger._ensure_running()
        address = UInt64(address) # convert to UInt64 if it's another type
        if address in self._addresses:
            return
        original_byte = os_interaction.get_memory_range(self._debugger.child_pid, int(address), 1) # take the original word at the address
        self._original_bytes[address] = original_byte[0] # save the original byte for the address (use index 0 as it's bytes object)
        os_interaction.write_memory_range(self._debugger.child_pid, int(address), BREAKPOINT_INSTRUCTION_BYTES) # write the breakpoint instruction at the address
        self._addresses.add(address)
        if notify_updates:
            self._debugger.update_callbacks.trigger()
    
    def remove_breakpoint(self, address : CIntBase | int, notify_updates: bool = True) -> None:
        """
        Removes a breakpoint at the given address.
        """
        self._debugger._ensure_running()
        address = UInt64(address) # convert to UInt64 if it's another type
        if address not in self._addresses: # check if it's actually a breakpoint before trying to remove it
            raise ValueError("Addresses isn't a breakpoint")
        original_byte = self._original_bytes[address] # get the original byte for the address
        os_interaction.write_memory_range(self._debugger.child_pid, int(address), bytes([original_byte])) # write the original byte back to the address
        self._addresses.remove(address) # remove the address from the breakpoints set and original bytes dict
        del self._original_bytes[address]
        if notify_updates:
            self._debugger.update_callbacks.trigger()