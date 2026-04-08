import ptrace
from breakpoint import BREAKPOINT_INSTRUCTION
from utils import get_first_byte, change_first_byte


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

    def __init__(self, child_pid, breakpoints, ensure_running):
        self.child_pid = child_pid
        self.breakpoints = breakpoints
        self._ensure_running = ensure_running

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
        self._ensure_running()
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("Memory slice must have start and stop defined")
            step = (
                int(key.step) if key.step is not None else 1
            )  # convert to int if CInt and handle None
            start = int(key.start)  # convert to int if CInt
            stop = int(key.stop)  # convert to int if CInt
            result_byte_range = self._get_raw_byte_range(start, stop, step)
            for i in range(len(result_byte_range)):
                address = start + i * step
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
        self._ensure_running()
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("Memory slice must have start and stop defined")
            step = (
                int(key.step) if key.step is not None else 1
            )  # convert to int if CInt and handle None
            start = int(key.start)  # convert to int if CInt
            stop = int(key.stop)  # convert to int if CInt
            value = list(value)
            for i in range(len(value)):
                address = start + i * step
                updated_byte = self._replace_write_breakpoint_byte(value[i], address)
                value[i] = updated_byte
            value = bytes(value)
            self._set_raw_byte_range(value, start, stop, step)
        else:
            value = self._replace_write_breakpoint_byte(value, key)
            self._set_raw_byte(key, value)
