from cint import CInt


def read_instruction(self, address, instruction_cnt=None):
    self._ensure_running()
    act_cnt = 1 if instruction_cnt is None else instruction_cnt
    MAX_INSTRUCTION_BYTES = 15
    code = self.memory[address : address + act_cnt * MAX_INSTRUCTION_BYTES]
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
    self._ensure_running()
    act_cnt = 1 if cnt is None else cnt
    byte_width = type.size // 8
    byte_cnt = act_cnt * byte_width
    data = self.memory[address : address + byte_cnt]
    res = []
    for i in range(act_cnt):
        res.append(type.from_bytes(data[i * byte_width : (i + 1) * byte_width]))
    if (
        cnt is None
    ):  # if the user didn't specify a count, return a single number instead of a list
        return res[0]
    else:
        return res


def write_number(self, address, value: int | CInt, width: int = None):
    """
    Writes a number to the given address.
    Value can be an int or a CInt. If it's a CInt, the width will be determined from the type.
    Otherwise, the width should be provided as a parameter (in bits, should be a multiple of 8).
    """
    self._ensure_running()
    if isinstance(value, CInt):
        width = value.size # determine width from the CInt type
        bytes_to_write = value.to_bytes()
    else:
        if width is None:
            raise ValueError("Width must be provided when writing an int value")
        bytes_to_write = value.to_bytes(width // 8, byteorder="little")
    width_bytes = width // 8
    self.memory[address : address + width_bytes] = bytes_to_write
