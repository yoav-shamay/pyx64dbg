from cint import CInt
import ptrace
from utils import get_bits_range, set_bits_range, signed_to_unsigned, in_range
from number_types import signed_integers_by_width, unsigned_integers_by_width

# format: "reg_name": ["reg_name_in_struct", (offset, size_in_bits)]
STANDARD_REGS = {
    "rax": ["rax", (0, 64)],
    "eax": ["rax", (0, 32)],
    "ax": ["rax", (0, 16)],
    "al": ["rax", (0, 8)],
    "ah": ["rax", (8, 8)],

    "rbx": ["rbx", (0, 64)],
    "ebx": ["rbx", (0, 32)],
    "bx": ["rbx", (0, 16)],
    "bl": ["rbx", (0, 8)],
    "bh": ["rbx", (8, 8)],

    "rcx": ["rcx", (0, 64)],
    "ecx": ["rcx", (0, 32)],
    "cx": ["rcx", (0, 16)],
    "cl": ["rcx", (0, 8)],
    "ch": ["rcx", (8, 8)],

    "rdx": ["rdx", (0, 64)],
    "edx": ["rdx", (0, 32)],
    "dx": ["rdx", (0, 16)],
    "dl": ["rdx", (0, 8)],
    "dh": ["rdx", (8, 8)],

    "rsi": ["rsi", (0, 64)],
    "esi": ["rsi", (0, 32)],
    "si": ["rsi", (0, 16)],

    "rdi": ["rdi", (0, 64)],
    "edi": ["rdi", (0, 32)],
    "di": ["rdi", (0, 16)],

    "rsp": ["rsp", (0, 64)],
    "esp": ["rsp", (0, 32)],
    "sp": ["rsp", (0, 16)],

    "rbp": ["rbp", (0, 64)],
    "ebp": ["rbp", (0, 32)],
    "bp": ["rbp", (0, 16)],

    "rip": ["rip", (0, 64)],
    "eip": ["rip", (0, 32)],
    "ip": ["rip", (0, 16)],

    "r8": ["r8", (0, 64)],
    "r9": ["r9", (0, 64)],
    "r10": ["r10", (0, 64)],
    "r11": ["r11", (0, 64)],
    "r12": ["r12", (0, 64)],
    "r13": ["r13", (0, 64)],
    "r14": ["r14", (0, 64)],
    "r15": ["r15", (0, 64)],

    "cs": ["cs", (0, 64)],
    "ss": ["ss", (0, 64)],
    "ds": ["ds", (0, 64)],
    "es": ["es", (0, 64)],
    "fs": ["fs", (0, 64)],
    "gs": ["gs", (0, 64)],

    "eflags": ["eflags", (0, 64)],
    "fs_base": ["fs_base", (0, 64)],
    "gs_base": ["gs_base", (0, 64)],
    "orig_rax": ["orig_rax", (0, 64)],
}

class Registers:
    """
    Represents the registers of the debugged process.
    Can read and write registers using the following syntax:
    registers[reg_name] / registers.reg_name -> accesses the value of the register with the given name.
    Can also use registers.get(reg_name) and registers.set(reg_name, value) for more explicit access.
    Can provide signed=True/False to get/set for signed or unsigned values. By default, it's True.
    """
    def __init__(self, child_pid, ensure_running):
        self.child_pid = child_pid
        self._ensure_running = ensure_running
        self._refresh_registers()

    def _refresh_registers(self):
        self._ensure_running()
        self.standard_regs = ptrace.get_standard_regs(self.child_pid)
    
    def get(self, reg_name, signed=True):
        self._ensure_running()
        if reg_name in STANDARD_REGS:
            reg_name, (offset, reg_size) = STANDARD_REGS[reg_name]
            res = get_bits_range(self.standard_regs[reg_name], offset, reg_size)
            if signed:
                res = signed_integers_by_width[reg_size](res)
            else:
                res = unsigned_integers_by_width[reg_size](res)
            return res
            # TODO add support for more register sets
        else:
            raise KeyError(reg_name)
    
    def set(self, reg_name, value, signed=True):
        self._ensure_running()
        if reg_name in STANDARD_REGS:
            reg_name, (offset, reg_size) = STANDARD_REGS[reg_name]
            if isinstance(value, CInt):
                signed = value.is_signed
                value = int(value) # convert to int if it's a CInt
            if not in_range(value, reg_size, signed):
                raise ValueError(f"Value {value} too large for register {reg_name}") # TODO should I do automatic reduction to the size (mod)? might use the types for auto conversion
            if signed:
                value = signed_to_unsigned(value, reg_size)
            full_reg_value = self.standard_regs[reg_name]
            new_full_reg_value = set_bits_range(full_reg_value, offset, reg_size, value)
            self.standard_regs[reg_name] = new_full_reg_value
            ptrace.set_standard_regs(self.child_pid, self.standard_regs)
            self._refresh_registers()
            # TODO add support for more register sets
        else:
            raise KeyError(reg_name)
    
    def __getitem__(self, key):
        return self.get(key)
    
    def __setitem__(self, key, value):
        self.set(key, value)

    def __getattr__(self, name):
        if name in STANDARD_REGS:
            return self.get(name)
        else:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in STANDARD_REGS: # TODO add more sets of registers once added
            self.set(name, value)
        else:
            super().__setattr__(name, value)