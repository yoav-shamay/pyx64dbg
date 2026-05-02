from pyx64dbg.cint import CInt
import pyx64dbg.ptrace as ptrace
from pyx64dbg.cfloat import CFloat
from pyx64dbg.number_types import Int8, Int16, Int32, Int64, Float32, Float64, Float80
from pyx64dbg.vector_register import Vector64, Vector128, Vector256, VectorRegister

# format: "reg_name": ["reg_name_in_struct", (first_byte, last_byte, type)]
STANDARD_REGS = {
    "rax": ["rax", (0, 7, Int64)],
    "eax": ["rax", (0, 3, Int32)],
    "ax": ["rax", (0, 1, Int16)],
    "al": ["rax", (0, 0, Int8)],
    "ah": ["rax", (1, 1, Int8)],

    "rbx": ["rbx", (0, 7, Int64)],
    "ebx": ["rbx", (0, 3, Int32)],
    "bx": ["rbx", (0, 1, Int16)],
    "bl": ["rbx", (0, 0, Int8)],
    "bh": ["rbx", (1, 1, Int8)],

    "rcx": ["rcx", (0, 7, Int64)],
    "ecx": ["rcx", (0, 3, Int32)],
    "cx": ["rcx", (0, 1, Int16)],
    "cl": ["rcx", (0, 0, Int8)],
    "ch": ["rcx", (1, 1, Int8)],

    "rdx": ["rdx", (0, 7, Int64)],
    "edx": ["rdx", (0, 3, Int32)],
    "dx": ["rdx", (0, 1, Int16)],
    "dl": ["rdx", (0, 0, Int8)],
    "dh": ["rdx", (1, 1, Int8)],

    "rsi": ["rsi", (0, 7, Int64)],
    "esi": ["rsi", (0, 3, Int32)],
    "si": ["rsi", (0, 1, Int16)],

    "rdi": ["rdi", (0, 7, Int64)],
    "edi": ["rdi", (0, 3, Int32)],
    "di": ["rdi", (0, 1, Int16)],

    "rsp": ["rsp", (0, 7, Int64)],
    "esp": ["rsp", (0, 3, Int32)],
    "sp": ["rsp", (0, 1, Int16)],

    "rbp": ["rbp", (0, 7, Int64)],
    "ebp": ["rbp", (0, 3, Int32)],
    "bp": ["rbp", (0, 1, Int16)],

    "rip": ["rip", (0, 7, Int64)],
    "eip": ["rip", (0, 3, Int32)],
    "ip": ["rip", (0, 1, Int16)],

    "r8": ["r8", (0, 7, Int64)],
    "r9": ["r9", (0, 7, Int64)],
    "r10": ["r10", (0, 7, Int64)],
    "r11": ["r11", (0, 7, Int64)],
    "r12": ["r12", (0, 7, Int64)],
    "r13": ["r13", (0, 7, Int64)],
    "r14": ["r14", (0, 7, Int64)],
    "r15": ["r15", (0, 7, Int64)],

    "cs": ["cs", (0, 7, Int64)],
    "ss": ["ss", (0, 7, Int64)],
    "ds": ["ds", (0, 7, Int64)],
    "es": ["es", (0, 7, Int64)],
    "fs": ["fs", (0, 7, Int64)],
    "gs": ["gs", (0, 7, Int64)],

    "eflags": ["eflags", (0, 7, Int64)],
    "fs_base": ["fs_base", (0, 7, Int64)],
    "gs_base": ["gs_base", (0, 7, Int64)],
    "orig_rax": ["orig_rax", (0, 7, Int64)],
}

# format: "reg_name": ("reg_name_in_struct" or ["reg_name_in_struct_list"], type)
# different from STANDARD_REGS as they don't have sub-registers.
# List of names is used in ymm registers, where the upper 128 bits are accessed through a different register name than the lower 128 bits (xmm)
EXTENDED_REGS = {
    "fcw": ("fcw", Int16),
    "fsw": ("fsw", Int16),
    "ftw": ("ftw", Int8),
    "fop": ("fop", Int16),
    "fip": ("fip", Int64),
    "fdp": ("fdp", Int64),
    "mxcsr": ("mxcsr", Int32),
    "mxcsr_mask": ("mxcsr_mask", Int32),
    "st0": ("st_mm0", Float80),
    "st1": ("st_mm1", Float80),
    "st2": ("st_mm2", Float80),
    "st3": ("st_mm3", Float80),
    "st4": ("st_mm4", Float80),
    "st5": ("st_mm5", Float80),
    "st6": ("st_mm6", Float80),
    "st7": ("st_mm7", Float80),
    "mm0": ("st_mm0", Vector64),
    "mm1": ("st_mm1", Vector64),
    "mm2": ("st_mm2", Vector64),
    "mm3": ("st_mm3", Vector64),
    "mm4": ("st_mm4", Vector64),
    "mm5": ("st_mm5", Vector64),
    "mm6": ("st_mm6", Vector64),
    "mm7": ("st_mm7", Vector64),
    "xmm0": ("xmm0", Vector128),
    "xmm1": ("xmm1", Vector128),
    "xmm2": ("xmm2", Vector128),
    "xmm3": ("xmm3", Vector128),
    "xmm4": ("xmm4", Vector128),
    "xmm5": ("xmm5", Vector128),
    "xmm6": ("xmm6", Vector128),
    "xmm7": ("xmm7", Vector128),
    "xmm8": ("xmm8", Vector128),
    "xmm9": ("xmm9", Vector128),
    "xmm10": ("xmm10", Vector128),
    "xmm11": ("xmm11", Vector128),
    "xmm12": ("xmm12", Vector128),
    "xmm13": ("xmm13", Vector128),
    "xmm14": ("xmm14", Vector128),
    "xmm15": ("xmm15", Vector128),
    "ymm0": (["xmm0", "ymm0_h"], Vector256),
    "ymm1": (["xmm1", "ymm1_h"], Vector256),
    "ymm2": (["xmm2", "ymm2_h"], Vector256),
    "ymm3": (["xmm3", "ymm3_h"], Vector256),
    "ymm4": (["xmm4", "ymm4_h"], Vector256),
    "ymm5": (["xmm5", "ymm5_h"], Vector256), 
    "ymm6": (["xmm6", "ymm6_h"], Vector256),
    "ymm7": (["xmm7", "ymm7_h"], Vector256),
    "ymm8": (["xmm8", "ymm8_h"], Vector256),
    "ymm9": (["xmm9", "ymm9_h"], Vector256),
    "ymm10": (["xmm10", "ymm10_h"], Vector256),
    "ymm11": (["xmm11", "ymm11_h"], Vector256),
    "ymm12": (["xmm12", "ymm12_h"], Vector256),
    "ymm13": (["xmm13", "ymm13_h"], Vector256),
    "ymm14": (["xmm14", "ymm14_h"], Vector256),
    "ymm15": (["xmm15", "ymm15_h"], Vector256),
}


def _convert_value_to_bytes(value, width_bytes):
    if isinstance(value, int):
        num_width = (value.bit_length() + 8) // 8 # +1 for the sign bit, which is needed for correct two's complement representation of negative numbers
        res = value.to_bytes(max(num_width, width_bytes), byteorder='little', signed=True)
        return res[:width_bytes]
    elif isinstance(value, float):
        if width_bytes >= 10:
            return Float80(value).to_bytes().ljust(width_bytes, b'\x00') # pad with zeros if the required width is larger
        elif width_bytes >= 8:
            return Float64(value).to_bytes()[:width_bytes].ljust(width_bytes, b'\x00') # pad with zeros if the required width is larger
        elif width_bytes >= 4:
            return Float32(value).to_bytes()[:width_bytes].ljust(width_bytes, b'\x00') # pad with zeros if the required width is larger
        else:
            raise ValueError(f"Cannot convert float to bytes for register assignment with width {width_bytes} bytes")
    elif isinstance(value, CInt):
        res = value.to_bytes()
        if value.is_signed and value < 0:
            # for negative signed values, we need to ensure the bytes are in correct two's complement form by padding with 0xFF if needed
            res = res.ljust(width_bytes, b'\xFF')
        else:
            res = res.ljust(width_bytes, b'\x00')
        return res[:width_bytes]
    elif isinstance(value, CFloat) or isinstance(value, VectorRegister):
        res = value.to_bytes()
        res = res.ljust(width_bytes, b'\x00') # pad with zeros if the float/vector is smaller than the required width
        return res[:width_bytes]
    elif isinstance(value, list):
        # for a list, recursively convert each element to bytes and concatenate
        # this is needed for example for easy assignments to vectors
        res = b""
        for part in value:
            res += _convert_value_to_bytes(part, width_bytes // len(value))
        return res
    elif isinstance(value, bytes):
        if len(value) < width_bytes:
            # if it's bytes but shorter than the required width, pad with zeros
            return value.ljust(width_bytes, b'\x00')
        else:
            return value[:width_bytes]
    else:
        raise TypeError(f"Cannot convert value of type {type(value)} to bytes for register assignment")

class Registers:
    """
    Represents the registers of the debugged process.
    Can read and write registers using the following syntax:
    registers[reg_name] / registers.reg_name -> accesses the value of the register with the given name.
    Can also use registers.get(reg_name) and registers.set(reg_name, value) for more explicit access.
    Vector registers (ymm / xmm) are returned in the VectorRegister format, see help(VectorRegister) for more details and supported operations on vector registers.
    """
    def __init__(self, child_pid, ensure_running, trigger_update_callbacks):
        self.child_pid = child_pid
        self._ensure_running = ensure_running
        self._trigger_update_callbacks = trigger_update_callbacks
        self._refresh_registers()

    def _refresh_registers(self):
        self._ensure_running()
        self.standard_regs = ptrace.get_standard_regs(self.child_pid)
        self.extended_regs = ptrace.get_extended_regs(self.child_pid)
    
    def get(self, reg_name):
        self._ensure_running()
        if reg_name in STANDARD_REGS:
            reg_name, (first_byte, last_byte, reg_type) = STANDARD_REGS[reg_name]
            reg_bytes = self.standard_regs[reg_name][first_byte : last_byte + 1]
            return reg_type.from_bytes(reg_bytes)
        elif reg_name in EXTENDED_REGS:
            reg_info = EXTENDED_REGS[reg_name]
            act_names, reg_type = reg_info
            if isinstance(act_names, list):
                # register split across multiple actual registers (e.g. ymm) - concatenate the parts together
                reg_bytes = b""
                for act_name in act_names:
                    reg_bytes += self.extended_regs[act_name]
            else:
                reg_bytes = self.extended_regs[act_names]
            # if it's a vector register we need to pass the parent Registers object to it, so it can trigger updates when its lanes are modified
            if issubclass(reg_type, VectorRegister):
                return reg_type(reg_bytes, self, reg_name)
            else:
                return reg_type.from_bytes(reg_bytes)
        else:
            raise KeyError(reg_name)
    
    def set(self, reg_name, value, trigger_updates = True):
        self._ensure_running()
        if reg_name in STANDARD_REGS:
            reg_name, (first_byte, last_byte, reg_type) = STANDARD_REGS[reg_name]
            value = _convert_value_to_bytes(value, reg_type.size)
            full_reg_value = bytearray(self.standard_regs[reg_name])
            full_reg_value[first_byte : last_byte + 1] = value
            self.standard_regs[reg_name] = bytes(full_reg_value)
            modified_regs_dict = {reg_name: self.standard_regs[reg_name]}
            ptrace.set_standard_regs(self.child_pid, modified_regs_dict)
        elif reg_name in EXTENDED_REGS:
            reg_info = EXTENDED_REGS[reg_name]
            act_names, reg_type = reg_info
            # we need to convert the value to bytes
            value_bytes = _convert_value_to_bytes(value, reg_type.size)
            modified_regs_dict = {}
            if isinstance(act_names, list):
                # Registers split across multiple actual registers (e.g. ymm) - need to split the value bytes accordingly
                for i, act_name in enumerate(act_names):
                    low_byte = i * (len(value_bytes) // len(act_names))
                    high_byte = (i + 1) * (len(value_bytes) // len(act_names))
                    part_bytes = value_bytes[low_byte : high_byte]
                    self.extended_regs[act_name] = part_bytes
                    modified_regs_dict[act_name] = part_bytes
            else:
                modified_regs_dict[act_names] = value_bytes
                self.extended_regs[act_names] = value_bytes
            ptrace.set_extended_regs(self.child_pid, modified_regs_dict)
        else:
            raise KeyError(reg_name)
        if trigger_updates:
            self._trigger_update_callbacks()
    
    def __getitem__(self, key):
        return self.get(key)
    
    def __setitem__(self, key, value):
        self.set(key, value)

    def __getattr__(self, name):
        if name in STANDARD_REGS or name in EXTENDED_REGS:
            return self.get(name)
        else:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in STANDARD_REGS or name in EXTENDED_REGS:
            self.set(name, value)
        else:
            super().__setattr__(name, value)