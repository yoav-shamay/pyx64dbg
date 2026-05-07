from pyx64dbg.number_types import UInt64
from pyx64dbg.cint import CInt

class StackFrame:
    """
    A stack frame representing a single call in the call stack.
    RBP is the base (top) of the stack frame, and RSP is the current stack pointer (bottom) of the frame.
    Allows reading and writing using offsets from RBP (As common in x86-64 assembly), and accessing saved RBP/RIP values.
    """
    def __init__(self, rbp, rsp, memory, ensure_running):
        self.rbp = rbp
        self.rsp = rsp
        self.memory = memory
        self._ensure_running = ensure_running

    def __getitem__(self, key):
        """
        Get a byte or range of bytes from the stack frame, using the RBP as the base address.
        The key can be an integer offset from RBP or a slice with start and stop offsets from RBP.
        For example, stack_frame[0] would return the byte at RBP, and stack_frame[-8:0] would return the 8 bytes below RBP.
        """
        self._ensure_running()
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
        self._ensure_running()
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
        return UInt64.from_bytes(self[0:8])
    
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
        return UInt64.from_bytes(self[8:16])
    
    @saved_rip.setter
    def saved_rip(self, value : int | CInt):
        # convert value to bytes
        if isinstance(value, CInt):
            value = value.to_bytes()
        else:
            value = value.to_bytes(8, byteorder="little")
        
        self[8:16] = value

    def read_number(self, offset, type, cnt=None):
        """
        Reads a number of the given type from the given offset in the stack frame.
        Type should be one of the number types defined in number_types, such as Int32, UInt64, etc.
        If cnt is provided, reads cnt numbers of the given type and returns them as a list
        """
        act_cnt = 1 if cnt is None else cnt
        type_byte_width = type.size // 8
        byte_cnt = act_cnt * type_byte_width
        data = self[offset : offset + byte_cnt]
        res = []
        for i in range(act_cnt):
            res.append(type.from_bytes(data[i * type_byte_width : (i + 1) * type_byte_width]))
        if cnt is None: # if the user didn't specify a count, return a single number instead of a list
            return res[0]
        else:
            return res
    
    def __repr__(self):
        return f"StackFrame(rbp={hex(self.rbp)}, rsp={hex(self.rsp)}, saved_rbp={hex(self.saved_rbp)}, saved_rip={hex(self.saved_rip)})"


class Stack:
    """
    Represents the call stack of the debugged program, allowing access to individual stack frames.
    Allows accessing current frame using current_frame(), and specific frame using [index].
    The current frame is index 0, the caller's frame is index 1, etc.
    To get help on usage of StackFrames, use help(StackFrame) in the console.
    """
    def __init__(self, memory, registers, ensure_running):
        self.memory = memory
        self.registers = registers
        self._ensure_running = ensure_running

    def current_frame(self):
        self._ensure_running()
        if self.registers.rbp == 0:
            raise IndexError("No stack frames available")
        return StackFrame(self.registers.rbp, self.registers.rsp, self.memory, self._ensure_running)

    def __getitem__(self, index : int | CInt):
        """
        Get the index-th stack frame.
        0 is the current frame, 1 is the caller's frame, etc.
        """
        self._ensure_running()
        if index < 0:
            raise IndexError("Stack frame index cannot be negative")
        current_frame = self.current_frame()
        for _ in range(index):
            if current_frame.saved_rbp == 0: # reached the end of the stack frames
                raise IndexError("Stack frame index out of range")
            # move to the caller's frame by reading the saved RBP and using RSP + 16 (exclude the saved RBP and saved RIP) as the new RSP
            current_frame = StackFrame(current_frame.saved_rbp, current_frame.rbp + 16, self.memory, self._ensure_running)
        return current_frame
    
    def frame_count(self):
        """
        Returns the number of stack frames available, by traversing the stack until we reach a frame with saved RBP of 0.
        """
        self._ensure_running()
        count = 0
        cur_frame = self.current_frame()
        while True:
            count += 1
            if cur_frame.saved_rbp == 0:
                break
            cur_frame = StackFrame(cur_frame.saved_rbp, cur_frame.rbp + 16, self.memory, self._ensure_running)
        return count

    def __repr__(self):
        """
        Show the number of frames in the stack as a general overview.
        """
        return f"Stack(frame_count={self.frame_count()})"