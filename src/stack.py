from number_types import UInt64
from cint import CInt

class StackFrame:
    """
    A stack frame representing a single call in the call stack.
    RBP is the base (top) of the stack frame, and RSP is the current stack pointer (bottom) of the frame.
    Allows reading and writing using offsets from RBP (As common in x86-64 assembly), and accessing saved RBP/RIP values.
    """
    def __init__(self, rbp, rsp, memory):
        self.rbp = rbp
        self.rsp = rsp
        self.memory = memory
    
    def __getitem__(self, key):
        """
        Get a byte or range of bytes from the stack frame, using the RBP as the base address.
        The key can be an integer offset from RBP or a slice with start and stop offsets from RBP.
        For example, stack_frame[0] would return the byte at RBP, and stack_frame[-8:0] would return the 8 bytes below RBP.
        """
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("StackFrame slice must have start and stop defined")
            step = (
                int(key.step) if key.step is not None else 1
            )  # convert to int if CInt and handle None
            start = int(key.start + self.rbp)  # convert to int if CInt
            stop = int(key.stop + self.rbp)  # convert to int if CInt
            return self.memory[start:stop:step]
        else:
            key = int(key) # convert to int if CInt
            return self.memory[self.rbp + key]
    
    def __setitem__(self, key, value):
        """
        Set a byte or range of bytes in the stack frame, using the RBP as the base address.
        The key can be an integer offset from RBP or a slice with start and stop offsets from RBP.
        For example, stack_frame[0] = 0x90 would set the byte at RBP to 0x90, and stack_frame[-8:0] = b"\x00"*8 would set the 8 bytes below RBP to 0.
        """
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("StackFrame slice must have start and stop defined")
            step = (
                int(key.step) if key.step is not None else 1
            )  # convert to int if CInt and handle None
            start = int(key.start + self.rbp)  # convert to int if CInt
            stop = int(key.stop + self.rbp)  # convert to int if CInt
            self.memory[start:stop:step] = value
        else:
            key = int(key) # convert to int if CInt
            self.memory[self.rbp + key] = value
    @property
    def saved_rbp(self):
        return UInt64(self[0:8])
    
    @saved_rbp.setter
    def saved_rbp(self, value : int | CInt):
        # convert value to bytes
        if isinstance(value, CInt):
            value = value.to_bytes()
        else:
            value = value.to_bytes(8, byteorder="little")
        
        self[0:8] = value
    
    @property    
    def saved_rip(self):
        return UInt64(self[8:16])
    
    @saved_rip.setter
    def saved_rip(self, value : int | CInt):
        # convert value to bytes
        if isinstance(value, CInt):
            value = value.to_bytes()
        else:
            value = value.to_bytes(8, byteorder="little")
        
        self[8:16] = value


class Stack:
    """
    Represents the call stack of the debugged program, allowing access to individual stack frames.
    Allows accessing current frame using current_frame(), and specific frame using [index].
    The current frame is index 0, the caller's frame is index 1, etc.
    """
    def __init__(self, memory, registers):
        self.memory = memory
        self.registers = registers
    
    def current_frame(self):
        return StackFrame(self.registers.rbp, self.registers.rsp, self.memory)

    def __getitem__(self, index : int):
        """
        Get the index-th stack frame.
        0 is the current frame, 1 is the caller's frame, etc.
        """
        current_frame = self.current_frame()
        for _ in range(index):
            if current_frame.saved_rbp == 0: # reached the end of the stack frames
                raise IndexError("Stack frame index out of range")
            # move to the caller's frame by reading the saved RBP and using RSP + 16 (exclude the saved RBP and saved RIP) as the new RSP
            current_frame = StackFrame(current_frame.saved_rbp(), current_frame.rbp + 16, self.memory)
        return current_frame