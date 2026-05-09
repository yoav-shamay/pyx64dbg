import capstone
from pyx64dbg.number_types import CIntBase
import mmap
from typing import Optional

def read_instruction(self, address : int, instruction_cnt : Optional[int]=None) -> list[capstone.CsInsn] | capstone.CsInsn:
    self._ensure_running()
    act_cnt = 1 if instruction_cnt is None else instruction_cnt
    MAX_INSTRUCTION_BYTES = 15
    code = self.memory[address : address + act_cnt * MAX_INSTRUCTION_BYTES]
    instructions = list(self._cs.disasm(code, address, count=act_cnt))
    if instruction_cnt is None:
        # if the user didn't specify an instruction count, return a single instruction instead of a list
        return instructions[0]
    else:
        return instructions


def read_number(self, address, type, cnt=None):
    """
    Reads a number of the given type from the given address.
    Type should be one of the number types defined in number_types, such as Int32, UInt64, etc.
    If cnt is provided, reads cnt numbers of the given type and returns them as a list
    """
    self._ensure_running()
    act_cnt = 1 if cnt is None else cnt
    byte_cnt = act_cnt * type.size
    data = self.memory[address : address + byte_cnt]
    res = []
    for i in range(act_cnt):
        res.append(type.from_bytes(data[i * type.size : (i + 1) * type.size]))
    if (
        cnt is None
    ):  # if the user didn't specify a count, return a single number instead of a list
        return res[0]
    else:
        return res


def write_number(self, address, value: int | CIntBase, width: int = None, trigger_updates = True):
    """
    Writes a number to the given address.
    Value can be an int or a CIntBase. If it's a CIntBase, the width will be determined from the type.
    Otherwise, the width should be provided as a parameter (in bytes)
    """
    self._ensure_running()
    if isinstance(value, CIntBase):
        width = value.size # determine width from the CIntBase type
        bytes_to_write = value.to_bytes()
    else:
        if width is None:
            raise ValueError("Width must be provided when writing an int value")
        bytes_to_write = value.to_bytes(width, byteorder="little")
    # we don't trigger updates by internal calls even though it's the only one to keep a consistent pattern
    self.memory.set_byte_range(bytes_to_write, address, address + width, trigger_updates=False)
    if trigger_updates:
        self.memory._trigger_update_callbacks()

# get the system page size for reading c strings in chunks
PAGE_SIZE = mmap.PAGESIZE

def read_c_string(self, address : int | CIntBase) -> bytes:
    """
    Reads a null-terminated string from the given address.
    """
    self._ensure_running()
    address = int(address) # convert to int if it's a CIntBase
    res = b""
    while b"\x00" not in res:
        # batch read a whole page of memory to use less syscalls.
        # it's safe to read until the end of the current page as the mapped memory is guaranteed to be in multiples of the page size.
        until_end_of_page = PAGE_SIZE - (address % PAGE_SIZE)
        chunk = self.memory[address : address + until_end_of_page]
        res += chunk
        address += until_end_of_page
    # trim the string at the null terminator
    null_term = res.index(b"\x00")
    res = res[:null_term]
    return res