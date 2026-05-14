from __future__ import annotations

from typing import TYPE_CHECKING, Optional, overload

from pyx64dbg.number_types import CNumBase, UInt64, CIntBase, UInt8

if TYPE_CHECKING:
    from pyx64dbg.debugger import Debugger


class StackFrame:
    """
    A stack frame representing a single call in the call stack.
    RBP is the base (top) of the stack frame, and RSP is the current stack pointer (bottom) of the frame.
    Allows reading and writing using offsets from RBP (As common in x86-64 assembly), and accessing saved RBP/RIP values.
    """

    def __init__(self, rbp: UInt64, rsp: UInt64, debugger: Debugger):
        self.rbp: UInt64 = rbp
        self.rsp: UInt64 = rsp
        self._debugger: Debugger = debugger

    # overloads for __getitem__ as we return different types based on the key type (slice or number)
    @overload
    def __getitem__(self, key: int | CIntBase) -> UInt8: ...
    @overload
    def __getitem__(self, key: slice) -> bytes: ...

    def __getitem__(self, key: int | CIntBase | slice) -> UInt8 | bytes:
        """
        Get a byte or range of bytes from the stack frame, using the RBP as the base address.
        The key can be an integer offset from RBP or a slice with start and stop offsets from RBP.
        For example, stack_frame[0] would return the byte at RBP, and stack_frame[-8:0] would return the 8 bytes below RBP.
        """
        self._debugger._ensure_running()
        if isinstance(key, slice):
            # for slice - we need to adjust start and stop to rbp
            if key.start is None or key.stop is None:
                raise ValueError("StackFrame slice must have start and stop defined")
            step = (
                int(key.step) if key.step is not None else 1
            )  # convert to int if CIntBase and handle None
            start = key.start + self.rbp
            stop = key.stop + self.rbp
            return self._debugger.memory[start:stop:step]
        else:
            # for int - we just need to adjust it to rbp
            return self._debugger.memory[self.rbp + key]

    # overloads for __setitem__ as we accept different types based on the key type (slice or number)
    @overload
    def __setitem__(
        self, key: int | CIntBase, value: int | CIntBase | bytes
    ) -> None: ...
    @overload
    def __setitem__(self, key: slice, value: bytes) -> None: ...

    def __setitem__(
        self, key: int | CIntBase | slice, value: int | CIntBase | bytes
    ) -> None:
        """
        Set a byte or range of bytes in the stack frame, using the RBP as the base address.
        The key can be an integer offset from RBP or a slice with start and stop offsets from RBP.
        For example, stack_frame[0] = 0x90 would set the byte at RBP to 0x90, and stack_frame[-8:0] =  b"\x00"*8 would set the 8 bytes below RBP to 0.
        """
        self._debugger._ensure_running()
        if isinstance(key, slice):
            # for slice - we need to adjust start and stop to rbp
            if key.start is None or key.stop is None:
                raise ValueError("StackFrame slice must have start and stop defined")
            step = (
                int(key.step) if key.step is not None else 1
            )  # convert to int if CIntBase and handle None
            start = key.start + self.rbp
            stop = key.stop + self.rbp
            self._debugger.memory[start:stop:step] = value
        else:
            # for int - we just need to adjust it to rbp
            self._debugger.memory[self.rbp + key] = value

    @property
    def saved_rbp(self) -> UInt64:
        """
        Returns the saved RBP value of the stack frame, which is located at the base of the frame (RBP).
        """
        return UInt64.from_bytes(
            self[0:8]
        )  # use our __getitem__ to read relative to rbp

    @saved_rbp.setter
    def saved_rbp(self, value: int | CIntBase) -> None:
        """
        Sets the saved RBP value of the stack frame, which is located at the base of the frame (RBP).
        """
        # convert value to bytes
        if isinstance(value, CIntBase):
            value = value.to_bytes()
        else:  # if it's int, we need to specify the byte length and endianness to convert it to bytes
            value = value.to_bytes(8, byteorder="little")
        # use our __setitem__ to set relative to rbp
        self[0:8] = value

    @property
    def saved_rip(self) -> UInt64:
        """
        Returns the saved RIP value of the stack frame, which is located at RBP + 8 (after the saved RBP).
        """
        return UInt64.from_bytes(
            self[8:16]
        )  # use our __getitem__ to read relative to rbp

    @saved_rip.setter
    def saved_rip(self, value: int | CIntBase) -> None:
        """
        Sets the saved RIP value of the stack frame, which is located at RBP + 8 (after the saved RBP).
        """
        # convert value to bytes
        if isinstance(value, CIntBase):
            value_bytes = value.to_bytes()
        else:  # if it's int, we need to specify the byte length and endianness to convert it to bytes
            value_bytes = value.to_bytes(8, byteorder="little")

        self[8:16] = value_bytes  # use our __setitem__ to set relative to rbp

    # overloads for read_number as we return different types based on the cnt parameter (single number or list of numbers)
    @overload
    def read_number(
        self, offset: int | CIntBase, type: type[CNumBase], cnt: None = None
    ) -> CNumBase: ...
    @overload
    def read_number(
        self, offset: int | CIntBase, type: type[CNumBase], cnt: int
    ) -> list[CNumBase]: ...

    def read_number(
        self, offset: int | CIntBase, type: type[CNumBase], cnt: Optional[int] = None
    ) -> CNumBase | list[CNumBase]:
        """
        Reads a number of the given type from the given offset in the stack frame.
        Type should be one of the number types defined in number_types, such as Int32, UInt64, Float32, etc.
        If cnt is provided, reads cnt numbers of the given type and returns them as a list
        """
        act_cnt = (
            1 if cnt is None else cnt
        )  # if cnt is None, we read a single number, otherwise we read cnt numbers
        type_byte_width = type.size // 8
        byte_cnt = act_cnt * type_byte_width
        data = self[offset : offset + byte_cnt]
        res: list[bytes] = []
        for i in range(act_cnt):
            res.append(
                type.from_bytes(data[i * type_byte_width : (i + 1) * type_byte_width])
            )
        if (
            cnt is None
        ):  # if the user didn't specify a count, return a single number instead of a list
            return res[0]
        else:
            return res

    def __repr__(self) -> str:
        """
        Shows the stack frame, in the format of StackFrame(rbp=0x..., rsp=0x..., saved_rbp=0x..., saved_rip=0x...).
        """
        return f"StackFrame(rbp={hex(self.rbp)}, rsp={hex(self.rsp)}, saved_rbp={hex(self.saved_rbp)}, saved_rip={hex(self.saved_rip)})"


class Stack:
    """
    Represents the call stack of the debugged program, allowing access to individual stack frames.
    Allows accessing current frame using current_frame(), and specific frame using [index].
    The current frame is index 0, the caller's frame is index 1, etc.
    See the help of StackFrame for more information on how to use a specific stack frame.
    """

    def __init__(self, debugger: Debugger) -> None:
        self._debugger = debugger

    def current_frame(self) -> StackFrame:
        """
        Returns the current stack frame, using the current RBP and RSP values from the registers.
        Raises IndexError if RBP is 0, which means there are no stack frames available (can happen if run right on entry)
        """
        self._debugger._ensure_running()
        if self._debugger.registers.rbp == 0:
            raise IndexError("No stack frames available")
        rbp = UInt64(
            self._debugger.registers.rbp
        )  # convert to UInt64 as it's an address
        rsp = UInt64(self._debugger.registers.rsp)
        return StackFrame(rbp, rsp, self._debugger)

    def __getitem__(self, index: int | CIntBase) -> StackFrame:
        """
        Get the index-th stack frame.
        0 is the current frame, 1 is the caller's frame, etc.
        """
        self._debugger._ensure_running()
        if index < 0:
            raise IndexError("Stack frame index cannot be negative")
        current_frame = self.current_frame()
        for _ in range(index):
            if current_frame.saved_rbp == 0:  # reached the end of the stack frames
                raise IndexError("Stack frame index out of range")
            # move to the caller's frame by reading the saved RBP and using RSP + 16 (exclude the saved RBP and saved RIP) as the new RSP
            current_frame = StackFrame(
                current_frame.saved_rbp, current_frame.rbp + 16, self._debugger
            )
        return current_frame

    def frame_count(self) -> int:
        """
        Returns the number of stack frames available, by traversing the stack until we reach a frame with saved RBP of 0.
        """
        self._debugger._ensure_running()
        count = 0
        cur_frame = self.current_frame()
        # step up in frames until we reach a frame with saved RBP of 0, which means it's the end of the stack frames
        while True:
            count += 1
            if cur_frame.saved_rbp == 0:
                break
            cur_frame = StackFrame(
                cur_frame.saved_rbp, cur_frame.rbp + 16, self._debugger
            )
        return count

    def __repr__(self) -> str:
        """
        Show the number of frames in the stack as a general overview.
        Format: Stack(frame_count=...)
        """
        return f"Stack(frame_count={self.frame_count()})"
