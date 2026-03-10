import ptrace
from utils import get_first_byte, change_first_byte, split_bytes, create_word


class Memory:
    def __init__(self, child_pid):
        self.child_pid = child_pid

    def _get_byte(self, address):
        word = ptrace.peekdata(self.child_pid, address)
        return get_first_byte(word)

    def _get_byte_range(self, start_address, end_address, step=1):
        bytes_list = []
        if step == 1:
            # take 2 bytes at a time, as peekdata returns a word, to prevent unneccessary calls
            for address in range(start_address, end_address, 2):
                word = ptrace.peekdata(self.child_pid, address)
                bytes_list += split_bytes(word)
            # remove last byte if taking one too much
            length = end_address - start_address
            bytes_list = bytes_list[:length]
        else:
            for address in range(start_address, end_address, step):
                byte = self._get_byte(address)
                bytes_list.append(byte)
        return bytes(bytes_list)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self._get_byte_range(key.start, key.stop, key.step)
        else:
            return self._get_byte(key)

    def _set_byte(self, address, value):
        word = ptrace.peekdata(self.child_pid, address)
        new_word = change_first_byte(word, value)
        ptrace.pokedata(self.child_pid, address, new_word)

    def _set_byte_range(self, data, start_address, end_address, step=1):
        if step == 1:
            # set 2 bytes at a time, as pokedata takes a word, to prevent unneccessary calls
            # except for the last byte if the range is odd
            for i, address in enumerate(range(start_address, end_address - 1, 2)):
                word = create_word(data[i * 2], data[i * 2 + 1])
                ptrace.pokedata(self.child_pid, address, word)
            length = end_address - start_address
            if length % 2 == 1:  # if the range is odd length, set the last byte seperately
                self._set_byte(end_address - 1, data[-1])
        else:
            for i, address in enumerate(range(start_address, end_address, step)):
                self._set_byte(address, data[i])

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            self._set_byte_range(value, key.start, key.stop, key.step)
        else:
            self._set_byte(key, value)
