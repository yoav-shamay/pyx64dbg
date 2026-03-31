from cint import CInt
import ptrace
from breakpoint import BREAKPOINT_INSTRUCTION
from utils import (
    get_first_byte,
    change_first_byte,
    split_bytes,
    create_word,
    WORD_SIZE,
    change_byte_prefix,
)
from capstone import Cs, CS_ARCH_X86, CS_MODE_64


class Memory:  # TODO handle reading on breakpoints, which requires reading the original byte instead of the breakpoint instruction
    """
    Represents the memory of the debugged process.
    Can read and write bytes from the memory using the following syntax:
    memory[address] -> reads a byte from the given address
    memory[start:end] -> reads the bytes at [start,end), returning a bytes object
    memory[address] = value -> writes a byte to the given address. Value should be an int in the range [0, 255]
    memory[start:end] = value -> writes a range of bytes to the given address. Value should be a bytes object of length end - start.
    Can also use memory[start:end:step] for reading/writing with a step.
    """

    def __init__(self, child_pid, breakpoints):
        self.child_pid = child_pid
        self.cs = Cs(CS_ARCH_X86, CS_MODE_64)
        self.cs.detail = True
        self.breakpoints = breakpoints

    def _get_raw_byte(self, address):
        word = ptrace.peekdata(self.child_pid, address)
        return get_first_byte(word)

    def _get_raw_byte_range(self, start_address, end_address, step):
        if step == 1:
            result = ptrace.get_memory_range(
                self.child_pid, start_address, end_address - start_address
            )
            return list(result)
        else:
            # for steps, there is no reason to bother with optimizing, due to rare use and likely small range size, and steps making optimizations frequenytly impossible
            byte_list = []
            for address in range(start_address, end_address, step):
                byte = self._get_raw_byte(address)
                byte_list.append(byte)
            return byte_list

    def _replace_read_breakpoint_byte(self, data, address):
        if address in self.breakpoints.get_breakpoints():
            return self.breakpoints.original_bytes[address]
        else:
            return data

    def __getitem__(self, key):
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("Memory slice must have start and stop defined")
            step = key.step if key.step is not None else 1
            result_byte_range = self._get_raw_byte_range(key.start, key.stop, step)
            for i in range(len(result_byte_range)):
                address = key.start + i * step
                updated_byte = self._replace_read_breakpoint_byte(
                    result_byte_range[i], address
                )
                result_byte_range[i] = updated_byte
            return bytes(result_byte_range)
        else:
            byte = self._get_raw_byte(key)
            return self._replace_read_breakpoint_byte(byte, key)

    def _set_raw_byte(self, address, value):
        word = ptrace.peekdata(self.child_pid, address)
        new_word = change_first_byte(word, value)
        ptrace.pokedata(self.child_pid, address, new_word)

    def _set_raw_byte_range(self, data, start_address, end_address, step):
        if step == 1:
            ptrace.write_memory_range(self.child_pid, start_address, data)
        else:
            # for steps, there is no reason to bother with optimizing, due to rare use and likely small range size, and steps making optimizations frequenytly impossible
            for i, address in enumerate(range(start_address, end_address, step)):
                self._set_raw_byte(address, data[i])

    def _replace_write_breakpoint_byte(self, byte, address):
        if address in self.breakpoints.get_breakpoints():
            self.breakpoints.original_bytes[address] = byte
            return BREAKPOINT_INSTRUCTION
        else:
            return byte

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("Memory slice must have start and stop defined")
            step = key.step if key.step is not None else 1
            value = list(value)
            for i in range(len(value)):
                address = key.start + i * step
                updated_byte = self._replace_write_breakpoint_byte(value[i], address)
                value[i] = updated_byte
            value = bytes(value)
            self._set_raw_byte_range(value, key.start, key.stop, step)
        else:
            value = self._replace_write_breakpoint_byte(value, key)
            self._set_raw_byte(key, value)

    def read_instruction(
        self, address, instruction_cnt=None
    ):  # TODO should this and the next one be here or in a seperate reading / disassembly module?
        act_cnt = 1 if instruction_cnt is None else instruction_cnt
        MAX_INSTRUCTION_BYTES = 15
        code = self[address : address + act_cnt * MAX_INSTRUCTION_BYTES]
        instructions = list(self.cs.disasm(code, address, count=act_cnt))
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
        act_cnt = 1 if cnt is None else cnt
        byte_cnt = type.size * act_cnt
        data = self[address : address + byte_cnt]
        res = []
        for i in range(act_cnt):
            res.append(type.from_bytes(data[i * type.size : (i + 1) * type.size]))
        if (
            cnt is None
        ):  # if the user didn't specify a count, return a single number instead of a list
            return res[0]
        else:
            return res
