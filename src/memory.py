from cint import CInt
import ptrace
from utils import get_first_byte, change_first_byte, split_bytes, create_word, WORD_SIZE, change_byte_prefix
from capstone import Cs, CS_ARCH_X86, CS_MODE_64


class Memory: # TODO handle reading on breakpoints, which requires reading the original byte instead of the breakpoint instruction
    def __init__(self, child_pid):
        self.child_pid = child_pid
        self.cs = Cs(CS_ARCH_X86, CS_MODE_64)
        self.cs.detail = True

    def _get_byte(self, address):
        word = ptrace.peekdata(self.child_pid, address)
        return get_first_byte(word)

    def _get_byte_range(self, start_address, end_address, step):
        bytes_list = []
        if step == 1:
            # take 8 bytes at a time, as peekdata returns a word, to prevent unneccessary calls
            for address in range(start_address, end_address, WORD_SIZE):
                word = ptrace.peekdata(self.child_pid, address)
                bytes_list += split_bytes(word)
            # remove last few bytes if the range size isn't a multiple of 8
            length = end_address - start_address
            bytes_list = bytes_list[:length]
        else:
            for address in range(start_address, end_address, step):
                byte = self._get_byte(address)
                bytes_list.append(byte)
        return bytes(bytes_list)

    def __getitem__(self, key):
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("Memory slice must have start and stop defined")
            step = key.step if key.step is not None else 1
            return self._get_byte_range(key.start, key.stop, step)
        else:
            return self._get_byte(key)

    def _set_byte(self, address, value):
        word = ptrace.peekdata(self.child_pid, address)
        new_word = change_first_byte(word, value)
        ptrace.pokedata(self.child_pid, address, new_word)

    def _set_byte_range(self, data, start_address, end_address, step):
        if step == 1:
            # set 8 bytes at a time, as pokedata takes a word, to prevent unneccessary calls
            # except for the last byte if the range size isn't a multiple of 8
            for i, address in enumerate(range(start_address, end_address - WORD_SIZE + 1, WORD_SIZE)):
                word = create_word(data[i * WORD_SIZE:(i+1) * WORD_SIZE])
                ptrace.pokedata(self.child_pid, address, word)
            length = end_address - start_address
            if length % WORD_SIZE != 0:  # if the range isn't a multiple of 8, we need to handle the remainder
                remaining_amt = length % WORD_SIZE
                address = end_address - remaining_amt + 1
                word = ptrace.peekdata(self.child_pid, address)
                data_num = create_word(data[-remaining_amt:], remaining_amt)
                new_word = change_byte_prefix(word, data_num, remaining_amt)
                ptrace.pokedata(self.child_pid, address, new_word)
        else:
            for i, address in enumerate(range(start_address, end_address, step)):
                self._set_byte(address, data[i])

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            if key.start is None or key.stop is None:
                raise ValueError("Memory slice must have start and stop defined")
            step = key.step if key.step is not None else 1
            self._set_byte_range(value, key.start, key.stop, step)
        else:
            self._set_byte(key, value)
    
    def read_instruction(self, address, instruction_cnt=None):
        act_cnt = 1 if instruction_cnt is None else instruction_cnt
        MAX_INSTRUCTION_BYTES = 15
        code = self[address:address + act_cnt * MAX_INSTRUCTION_BYTES]
        instructions = list(self.cs.disasm(code, address, count=act_cnt))
        if instruction_cnt is None: # if the user didn't specify an instruction count, return a single instruction instead of a list
            return instructions[0]
        else:
            return instructions

    
    def read_number(self, address, type : CInt, cnt = None):
        act_cnt = 1 if cnt is None else cnt
        byte_cnt = type.size * act_cnt
        data = self[address:address + byte_cnt]
        res = []
        for i in range(act_cnt):
            res.append(type.from_bytes(data[i*type.size:(i+1)*type.size]))
        if cnt is None: # if the user didn't specify a count, return a single number instead of a list
            return res[0]
        else:
            return res
