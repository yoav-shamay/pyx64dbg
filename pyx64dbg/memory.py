from pyx64dbg.number_types import CIntBase, Int8, UInt64, UInt8
import pyx64dbg.ptrace as ptrace
from pyx64dbg.breakpoint import BREAKPOINT_INSTRUCTION
from typing import TYPE_CHECKING, Optional, TypeVar, overload
import mmap
import capstone

if TYPE_CHECKING:
    from pyx64dbg.debugger import Debugger

# get the system page size for reading c strings in chunks
PAGE_SIZE = mmap.PAGESIZE

# generic for type annotation in read_number
T = TypeVar("T", bound=CIntBase)


class Memory:
    """
    Represents the memory of the debugged process.
    Can read and write bytes from the memory using the following syntax:
    memory[address] -> reads a byte from the given address
    memory[start:end] -> reads the bytes at [start,end), returning a bytes object
    memory[address] = value -> writes a byte to the given address. Value should be an int in the range [0, 255]
    memory[start:end] = value -> writes a range of bytes to the given address. Value should be a bytes object of length end - start.
    Can also use memory[start:end:step] for reading/writing with a step.
    """

    def __init__(self, debugger: "Debugger") -> None:
        """
        Initializes the Memory object with a reference to the parent Debugger object.
        """
        self._debugger: Debugger = debugger

    def _get_raw_byte(self, address: int) -> int:
        """
        A helper function for getting a single byte from the memory directly.
        Doesn't replace breakpoint bytes with the original byte.
        We usually use UInt64 for addresses in the API but for internal functions here int is more convinient (as ptrace also uses it, and it prevents double casting)
        """
        memory_bytes = ptrace.get_memory_range(
            self._debugger.child_pid, address, 1
        )  # read the memory at this location, returns a bytes object
        return memory_bytes[0]

    def _get_raw_byte_range(
        self, start_address: int, end_address: int, step: int
    ) -> list[int]:
        """
        A helper function for getting a range of bytes from the memory directly.
        Doesn't replace breakpoint bytes with the original byte.
        """
        if step == 1:
            result = ptrace.get_memory_range(
                self._debugger.child_pid, start_address, end_address - start_address
            )
            return list(result)
        # for steps, there is no reason to bother with optimizing., and steps making optimizations frequently impossible
        # It's rarely used and when used likely with a small range size
        byte_list: list[int] = []
        for address in range(start_address, end_address, step):
            byte = self._get_raw_byte(address)
            byte_list.append(byte)
        return byte_list

    def _replace_read_breakpoint_byte(self, data: int, address: int) -> int:
        """
        Potentially replaces a data with the original byte if the address is a breakpoint.
        Returns the given data if the address isn't a breakpoint, and the original byte if it is.
        """
        if (
            address in self._debugger.breakpoints.get_breakpoints()
        ):  # we can also use int instead of UInt64 to reference addresses in breakpoints due to them being considered equal by all means
            return self._debugger.breakpoints._original_bytes[address]
        else:
            return data

    # overload declerations for type annotation, as it can either get int or slice
    @overload
    def __getitem__(self, key: int | CIntBase) -> UInt8: ...
    @overload
    def __getitem__(self, key: slice) -> bytes: ...

    def __getitem__(self, key: int | CIntBase | slice) -> UInt8 | bytes:
        """
        Array access operator for reading from memory.
        Reads a byte or a range of bytes from the memory.
        Can be accessed with both slicing and single index.
        Slicing must include start and stop, and can optionally include a step.
        """
        self._debugger._ensure_running()
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("Memory slice must have start and stop defined")
            step = (
                int(key.step) if key.step is not None else 1
            )  # convert to int if CInt and handle None (default step is 1)
            start = int(key.start)
            stop = int(key.stop)
            result_byte_range = self._get_raw_byte_range(start, stop, step)
            # replace breakpoint bytes with original bytes in the result
            for i in range(len(result_byte_range)):
                address = (
                    start + i * step
                )  # the address of the current byte in the input range
                updated_byte = self._replace_read_breakpoint_byte(
                    result_byte_range[i], address
                )
                result_byte_range[i] = updated_byte
            return bytes(result_byte_range)
        else:
            address = int(key)  # Convert to int if it was a CIntBase
            byte = self._get_raw_byte(address)
            act_val = self._replace_read_breakpoint_byte(byte, address)
            return UInt8(
                act_val
            )  # return the value as UInt8 to represent byte type accurately

    def _set_raw_byte(self, address: int, value: int) -> None:
        """
        A helper function for setting a single byte in the memory directly.
        Doesn't handle setting byte on a breakpoint specially.
        """
        value_bytes = bytes([value])
        ptrace.write_memory_range(self._debugger.child_pid, address, value_bytes)

    def _set_raw_byte_range(
        self, data: bytes, start_address: int, end_address: int, step: int
    ) -> None:
        """
        A helper function for setting a range of bytes in the memory directly.
        Doesn't handle setting bytes on breakpoints specially.
        """
        if step == 1:
            ptrace.write_memory_range(self._debugger.child_pid, start_address, data)
        else:
            # for steps, there is no reason to bother with optimizing, due to rare use and likely small range size, and steps making optimizations frequenytly impossible
            for i, address in enumerate(range(start_address, end_address, step)):
                self._set_raw_byte(address, data[i])

    def _write_potentially_breakpoint_byte(self, byte: int, address: int) -> int:
        """
        A helper function for handeling writes that could potentially be writing to a breakpoint address.
        If the address is a breakpoint, updates the internal original_byte in the breakpoint state.
        Returns the breakpoint instruction byte (as this should be the in-process byte there).
        Otherwise, returns the byte as it should be written to the memory.
        """
        # we can sue address as int to reference breakpoints due to them being considered equal to UInt64 and we don't create new dictionary keys here
        if address in self._debugger.breakpoints.get_breakpoints():
            self._debugger.breakpoints._original_bytes[address] = byte
            return BREAKPOINT_INSTRUCTION
        else:
            return byte

    def set_byte(
        self,
        address: int | CIntBase,
        value: int | CIntBase,
        trigger_updates: bool = True,
    ) -> None:
        """
        Sets a byte in the process memory at the given address.
        """
        self._debugger._ensure_running()
        key = int(address)  # convert to int if it's a CInt
        value = int(value)
        if address in self._debugger.breakpoints.get_breakpoints():
            # if it's a breakpoint we only need to update our internal state
            # no need to perform any syscall
            self._debugger.breakpoints._original_bytes[key] = value
        else:
            # otherwise write it normally
            self._set_raw_byte(key, value)
        if trigger_updates:
            self._debugger.update_callbacks.trigger()

    def set_byte_range(
        self,
        value: bytes,
        start: int | CIntBase,
        end: int | CIntBase,
        step: int | CIntBase | None = 1,
        trigger_updates: bool = True,
    ) -> None:
        """
        Sets a range of addresses in the process memory to the given bytes.
        """
        self._debugger._ensure_running()
        start = int(start)  # convert to int if CInt
        stop = int(end)  # convert to int if CInt
        step = (
            int(step) if step is not None else 1
        )  # convert to int if CInt and handle None (default step is 1). None is needed as it can come from slice
        # replace breakpoint bytes in writes with 0xCC and update the original byte in state for them
        value_list = list(value)
        for i in range(len(value)):
            address = start + i * step
            updated_byte = self._write_potentially_breakpoint_byte(
                value_list[i], address
            )
            value_list[i] = updated_byte
        value = bytes(value_list)
        self._set_raw_byte_range(value, start, stop, step)
        if trigger_updates:
            self._debugger.update_callbacks.trigger()

    # overloads for __setitem__, as we get different types based on the key type (slice or number)
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
        Set item operator for writing to memory.
        Can write a byte or a range of bytes to the memory.
        Can be accessed with both slicing and single index.
        Slicing must include start and stop, and can optionally include a step.
        """
        self._debugger._ensure_running()
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("Memory slice must have start and stop defined")
            self.set_byte_range(
                value, key.start, key.stop, key.step, trigger_updates=False
            )  # we choose to trigger updates in the end by ourselves, as the pattern is to not call it by intermediate functions
        else:
            if isinstance(value, bytes):
                value = value[
                    0
                ]  # if it's a bytes object, take the first byte as the value to write
            self.set_byte(key, value, trigger_updates=False)
        self._debugger.update_callbacks.trigger()  # as it's an operator, we can't have an optional parameter, so we trigger in the end anyway

    def read_instruction(
        self, address: int | CIntBase, instruction_cnt: Optional[int] = None
    ) -> list[capstone.CsInsn] | capstone.CsInsn:
        """
        Reads an instruction from the given address and disassembles it using capstone.
        Can optionally disassemble multiple instructions by providing an instruction count.
        Returns a CsInsn object representing the instruction at the given address.
        If instruction count is provided, returns a list of CsInsn objects representing the instructions at the given address.
        """
        self._debugger._ensure_running()
        act_cnt = (
            1 if instruction_cnt is None else instruction_cnt
        )  # actual instruction count to read, default is 1 if not provided
        MAX_INSTRUCTION_BYTES = (
            15  # The maximum length of an instruction in x86_64 is 15 bytes
        )
        address = int(address)  # Convert to int if isn't already.
        code = self[
            address : address + act_cnt * MAX_INSTRUCTION_BYTES
        ]  # use our __getitem__ to read the instruction bytes
        instructions: list[capstone.CsInsn] = list(
            self._debugger._cs.disasm(code, address, count=act_cnt)
        )
        if instruction_cnt is None:
            # if the user didn't specify an instruction count, return a single instruction instead of a list
            return instructions[0]
        else:
            return instructions

    # overloads based on whether or not cnt is provided to indicate when we return a list
    @overload
    def read_number(
        self, address: int | CIntBase, number_type: type[T], cnt: None = None
    ) -> T: ...
    @overload
    def read_number(
        self, address: int | CIntBase, number_type: type[T], cnt: int
    ) -> list[T]: ...

    def read_number(
        self, address: int | CIntBase, number_type: type[T], cnt: Optional[int] = None
    ) -> T | list[T]:
        """
        Reads a number of the given type from the given address.
        Type should be one of the number types defined in number_types, such as Int32, UInt64, etc.
        If cnt is provided, reads cnt numbers of the given type and returns them as a list
        """
        self._debugger._ensure_running()
        act_cnt = (
            1 if cnt is None else cnt
        )  # actual count to read, default is 1 if not provided
        byte_cnt = (
            act_cnt * number_type.size
        )  # the number of bytes to read for the given count and number type
        data = self[
            address : address + byte_cnt
        ]  # use our __getitem__ to read the bytes for the number(s)
        res: list[T] = []
        for i in range(act_cnt):
            start_index = i * number_type.size
            end_index = (i + 1) * number_type.size
            res.append(number_type.from_bytes(data[start_index:end_index]))
        if (
            cnt is None
        ):  # if the user didn't specify a count, return a single number instead of a list
            return res[0]
        else:
            return res

    def write_number(
        self,
        address: int | CIntBase,
        value: int | CIntBase,
        width: Optional[int] = None,
        trigger_updates: bool = True,
    ) -> None:
        """
        Writes a number to the given address.
        Value can be an int or a CIntBase. If it's a CIntBase, the width will be determined from the type.
        Otherwise, the width should be provided as a parameter (in bytes)
        """
        self._debugger._ensure_running()
        if isinstance(value, CIntBase):
            width = value.size  # determine width from the CIntBase type
            bytes_to_write = value.to_bytes()
        else:
            if width is None:
                raise ValueError("Width must be provided when writing an int value")
            bytes_to_write = value.to_bytes(
                width, byteorder="little"
            )  # use little-endian byte order for x86_64s
        # we don't trigger updates by internal calls even though it's the only one to keep a consistent pattern
        self.set_byte_range(
            bytes_to_write, address, address + width, trigger_updates=False
        )
        if trigger_updates:
            self._debugger.update_callbacks.trigger()

    def read_c_string(self, address: int | CIntBase) -> bytes:
        """
        Reads a null-terminated string from the given address.
        """
        self._debugger._ensure_running()
        address = int(address)  # convert to int if it's a CIntBase
        res = b""
        # read until we get a null terminator
        while True:
            # batch read a whole page of memory to use less syscalls.
            # it's safe to read until the end of the current page as the mapped memory is guaranteed to be in multiples of the page size.
            until_end_of_page = PAGE_SIZE - (address % PAGE_SIZE)
            chunk = self._debugger.memory[address : address + until_end_of_page]
            res += chunk
            address += until_end_of_page
            if (
                b"\x00" in chunk
            ):  # if we got a null terminator in the chunk, we can stop reading more memory
                break
        # trim the string at the null terminator
        null_term = res.index(b"\x00")
        res = res[:null_term]
        return res
