from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeAlias, TypeVar
from collections.abc import Collection

import pyx64dbg.os_interaction as os_interaction
from pyx64dbg.number_types import CNumBase, Int8, Int16, Int32, Int64, Float32, Float64, Float80, CFloatBase, CIntBase
from pyx64dbg.vector_register import Vector64, Vector128, Vector256, VectorRegister

if TYPE_CHECKING:
    from pyx64dbg.debugger import Debugger

# types that we can convert to bytes and assign to a register
RegisterSettableTypes: TypeAlias = int | float | CNumBase | VectorRegister | Collection["RegisterSettableTypes"] | bytes

def _convert_value_to_bytes(value: RegisterSettableTypes, width_bytes: int) -> bytes:
    """
    An helper function to convert a value of various possible types to bytes for register assignment.
    Works with integers, floats, C integers, VectorRegister, bytes, and list of any of those types.
    """
    if isinstance(value, int):
        num_width = (value.bit_length() + 8) // 8 # +1 for the sign bit, which is needed for correct two's complement representation of negative numbers
        res = value.to_bytes(max(num_width, width_bytes), byteorder='little', signed=True) # we convert it either by the minimum possible and then crop or by width_bytes (which pads it)
        return res[:width_bytes]
    elif isinstance(value, float):
        # we divide into cases based on the width, so we use the to_bytes of the correct float type
        # we use the closest type we know and pad with zeros if it isn't exactly (like 16 bytes for a float which might happen)
        if width_bytes >= 10:
            return Float80(value).to_bytes().ljust(width_bytes, b'\x00') # pad with zeros if the required width is larger
        elif width_bytes >= 8:
            return Float64(value).to_bytes()[:width_bytes].ljust(width_bytes, b'\x00') # pad with zeros if the required width is larger
        elif width_bytes >= 4:
            return Float32(value).to_bytes()[:width_bytes].ljust(width_bytes, b'\x00') # pad with zeros if the required width is larger
        else:
            raise ValueError(f"Cannot convert float to bytes for register assignment with width {width_bytes} bytes")
    elif isinstance(value, CIntBase):
        res = value.to_bytes()
        if value.is_signed and value < 0:
            # for negative signed values, we need to ensure the bytes are in correct two's complement form by padding with 0xFF if needed
            res = res.ljust(width_bytes, b'\xFF')
        else:
            # for positive signed values and unsigned values, we pad with 0x00 if needed
            res = res.ljust(width_bytes, b'\x00')
        # if the value was initially larger, we need to crop it to the required width
        return res[:width_bytes]
    elif isinstance(value, (CFloatBase, VectorRegister)):
        # we merge both floatbase and vectorregister
        # for both we just use to_bytes and pad with zeros
        res = value.to_bytes()
        res = res.ljust(width_bytes, b'\x00') # pad with zeros if the float/vector is smaller than the required width
        return res[:width_bytes]
    elif isinstance(value, bytes):
        # for bytes, we either pad with zeros or crop to fit the required width
        if len(value) < width_bytes:
            # if it's bytes but shorter than the required width, pad with zeros
            return value.ljust(width_bytes, b'\x00')
        else:
            return value[:width_bytes]
    elif isinstance(value, Collection):
        # for a list, recursively convert each element to bytes and concatenate
        # this is needed for example for easy assignments to vectors
        res = b""
        for part in value:
            res += _convert_value_to_bytes(part, width_bytes // len(value))
        return res
    else:
        # for any other type, raise an error as we don't know how to convert it to bytes for register assignment
        raise TypeError(f"Cannot convert value of type {type(value)} to bytes for register assignment")
    

T_Reg = TypeVar('T_Reg', bound=CNumBase | VectorRegister)

class StandardRegister(Generic[T_Reg]):
    """
    Descriptor for Standard Registers.
    Used for property access to registers like registers.rax, registers.eax, etc.
    """
    def __init__(self, dict_name: str, first_byte: int, length: int, reg_type: type[T_Reg]):
        """
        Initializes the descriptor.
        Requires the name in the standard_regs dictionary, the first and last byte of the register in that struct, and the type of the register (Int64, Int32, etc.).
        """
        self.struct_name: str = dict_name
        self.first_byte: int = first_byte
        self.length: int = length
        self.reg_type: type[T_Reg] = reg_type

    def __get__(self, instance: Registers | None, owner: type) -> T_Reg:
        """
        Getter for the descriptor.
        Returns the value of the register.
        """
        if instance is None:
            # disallow access to the descriptor through the class as it doesn't make sense
            raise AttributeError("Can only access registers through an instance")
        instance._debugger._ensure_running()
        # get the bytes from the dict using slicing
        reg_bytes = instance.standard_regs[self.struct_name][self.first_byte : self.first_byte + self.length]
        return self.reg_type.from_bytes(reg_bytes) # convert to the right number type

    def __set__(self, instance: Registers, value: RegisterSettableTypes) -> None:
        """
        Setter for the descriptor.
        Sets the value of the register, converting it to bytes and writing it to the debugged process using os_interaction.
        """
        self.set_value(instance, value, trigger_updates=True)

    def set_value(self, instance: Registers, value: RegisterSettableTypes, trigger_updates: bool = True) -> None:
        """
        A function to set the value of the register (with an option to not trigger callbacks).
        """
        instance._debugger._ensure_running()
        value_bytes = _convert_value_to_bytes(value, self.reg_type.size) # convert to bytes using the helper method
        full_reg_value = bytearray(instance.standard_regs[self.struct_name]) # change to bytearray for editing
        full_reg_value[self.first_byte : self.first_byte + self.length] = value_bytes
        instance.standard_regs[self.struct_name] = bytes(full_reg_value) # change back to bytes and assign to the dict
        # write the modified register struct back to the debugged process using os_interaction
        modified_regs_dict = {self.struct_name: instance.standard_regs[self.struct_name]}
        os_interaction.set_standard_regs(instance._debugger.child_pid, modified_regs_dict)
        if trigger_updates:
            instance._debugger.update_callbacks.trigger()


class ExtendedRegister(Generic[T_Reg]):
    """
    Descriptor for Extended Registers.
    Used for property access to registers like registers.xmm0, registers.ymm0, etc.
    """
    def __init__(self, act_names: list[str], reg_type: type[T_Reg]):
        """
        Initializes the descriptor.
        Requires the list of names in the extended_regs dictionary that compose the register.
        """
        self.act_names: list[str] = act_names
        self.reg_type: type[T_Reg] = reg_type
        self._reg_name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        """
        A special method that is called when the descriptor is assigned to a class attribute.
        We use it to save the name of the register for giving to vector registers.
        """
        self._reg_name = name

    def __get__(self, instance: Registers | None, owner: type) -> T_Reg:
        """
        Getter for the descriptor.
        Returns the value of the register.
        """
        if instance is None:
            # disallow access to the descriptor through the class as it doesn't make sense
            raise AttributeError("Can only access registers through an instance")
        instance._debugger._ensure_running()
        # combine the various parts and check if it really exists
        exists = True
        reg_bytes = b""
        for act_name in self.act_names:
            if act_name not in instance.extended_regs:
                exists = False
                break
            reg_bytes += instance.extended_regs[act_name]
        if not exists:
            raise ValueError(f"Register {self._reg_name} not available")
        # initialization for VectorRegister is different as it needs the parent instance and name
        if issubclass(self.reg_type, VectorRegister):
            return self.reg_type.from_bytes(reg_bytes, instance, self._reg_name)
        else:
            return self.reg_type.from_bytes(reg_bytes)

    def __set__(self, instance: Registers, value: RegisterSettableTypes) -> None:
        """
        Setter for the descriptor.
        Sets the value of the register, converting it to bytes and writing it to the debugged process using os_interaction.
        """
        self.set_value(instance, value, trigger_updates=True)

    def set_value(self, instance: Registers, value: RegisterSettableTypes, trigger_updates: bool = True) -> None:
        """
        A function to set the value of the register (with an option to not trigger callbacks).
        """
        instance._debugger._ensure_running()
        value_bytes = _convert_value_to_bytes(value, self.reg_type.size) # convert to bytes using the helper method
        # iterate over every part and write the corresponding part of the value bytes to the matching register
        modified_regs_dict: dict[str, bytes] = {}
        for i, act_name in enumerate(self.act_names):
            low_byte = i * (len(value_bytes) // len(self.act_names))
            high_byte = (i + 1) * (len(value_bytes) // len(self.act_names))
            part_bytes = value_bytes[low_byte : high_byte]
            # modify both the cached value and the dict we use in os_interaction
            instance.extended_regs[act_name] = part_bytes
            modified_regs_dict[act_name] = part_bytes
        os_interaction.set_extended_regs(instance._debugger.child_pid, modified_regs_dict)
        if trigger_updates:
            instance._debugger.update_callbacks.trigger()

class Registers:
    """
    Represents the registers of the debugged process.
    Can read and write registers using the following syntax:
    registers[reg_name] / registers.reg_name -> accesses the value of the register with the given name.
    Can also use registers.get(reg_name) and registers.set(reg_name, value) for more explicit access.
    Vector registers (ymm / xmm) are returned in the VectorRegister format.
    see help of VectorRegister for more details and supported operations on vector registers.
    """
    # definition of all registers as descriptors
    # standard regs
    rax = StandardRegister("rax", 0, 8, Int64)
    eax = StandardRegister("rax", 0, 4, Int32)
    ax = StandardRegister("rax", 0, 2, Int16)
    al = StandardRegister("rax", 0, 1, Int8)
    ah = StandardRegister("rax", 1, 1, Int8)

    rbx = StandardRegister("rbx", 0, 8, Int64)
    ebx = StandardRegister("rbx", 0, 4, Int32)
    bx = StandardRegister("rbx", 0, 2, Int16)
    bl = StandardRegister("rbx", 0, 1, Int8)
    bh = StandardRegister("rbx", 1, 1, Int8)

    rcx = StandardRegister("rcx", 0, 8, Int64)
    ecx = StandardRegister("rcx", 0, 4, Int32)
    cx = StandardRegister("rcx", 0, 2, Int16)
    cl = StandardRegister("rcx", 0, 1, Int8)
    ch = StandardRegister("rcx", 1, 1, Int8)

    rdx = StandardRegister("rdx", 0, 8, Int64)
    edx = StandardRegister("rdx", 0, 4, Int32)
    dx = StandardRegister("rdx", 0, 2, Int16)
    dl = StandardRegister("rdx", 0, 1, Int8)
    dh = StandardRegister("rdx", 1, 1, Int8)

    rsi = StandardRegister("rsi", 0, 8, Int64)
    esi = StandardRegister("rsi", 0, 4, Int32)
    si = StandardRegister("rsi", 0, 2, Int16)

    rdi = StandardRegister("rdi", 0, 8, Int64)
    edi = StandardRegister("rdi", 0, 4, Int32)
    di = StandardRegister("rdi", 0, 2, Int16)

    rsp = StandardRegister("rsp", 0, 8, Int64)
    esp = StandardRegister("rsp", 0, 4, Int32)
    sp = StandardRegister("rsp", 0, 2, Int16)

    rbp = StandardRegister("rbp", 0, 8, Int64)
    ebp = StandardRegister("rbp", 0, 4, Int32)
    bp = StandardRegister("rbp", 0, 2, Int16)

    rip = StandardRegister("rip", 0, 8, Int64)
    eip = StandardRegister("rip", 0, 4, Int32)
    ip = StandardRegister("rip", 0, 2, Int16)

    r8 = StandardRegister("r8", 0, 8, Int64)
    r9 = StandardRegister("r9", 0, 8, Int64)
    r10 = StandardRegister("r10", 0, 8, Int64)
    r11 = StandardRegister("r11", 0, 8, Int64)
    r12 = StandardRegister("r12", 0, 8, Int64)
    r13 = StandardRegister("r13", 0, 8, Int64)
    r14 = StandardRegister("r14", 0, 8, Int64)
    r15 = StandardRegister("r15", 0, 8, Int64)

    cs = StandardRegister("cs", 0, 8, Int64)
    ss = StandardRegister("ss", 0, 8, Int64)
    ds = StandardRegister("ds", 0, 8, Int64)
    es = StandardRegister("es", 0, 8, Int64)
    fs = StandardRegister("fs", 0, 8, Int64)
    gs = StandardRegister("gs", 0, 8, Int64)

    eflags = StandardRegister("eflags", 0, 8, Int64)
    fs_base = StandardRegister("fs_base", 0, 8, Int64)
    gs_base = StandardRegister("gs_base", 0, 8, Int64)
    orig_rax = StandardRegister("orig_rax", 0, 8, Int64)

    # extended registers
    fcw = ExtendedRegister(["fcw"], Int16)
    fsw = ExtendedRegister(["fsw"], Int16)
    ftw = ExtendedRegister(["ftw"], Int8)
    fop = ExtendedRegister(["fop"], Int16)
    fip = ExtendedRegister(["fip"], Int64)
    fdp = ExtendedRegister(["fdp"], Int64)
    mxcsr = ExtendedRegister(["mxcsr"], Int32)
    mxcsr_mask = ExtendedRegister(["mxcsr_mask"], Int32)

    st0 = ExtendedRegister(["st_mm0"], Float80)
    st1 = ExtendedRegister(["st_mm1"], Float80)
    st2 = ExtendedRegister(["st_mm2"], Float80)
    st3 = ExtendedRegister(["st_mm3"], Float80)
    st4 = ExtendedRegister(["st_mm4"], Float80)
    st5 = ExtendedRegister(["st_mm5"], Float80)
    st6 = ExtendedRegister(["st_mm6"], Float80)
    st7 = ExtendedRegister(["st_mm7"], Float80)

    mm0 = ExtendedRegister(["st_mm0"], Vector64)
    mm1 = ExtendedRegister(["st_mm1"], Vector64)
    mm2 = ExtendedRegister(["st_mm2"], Vector64)
    mm3 = ExtendedRegister(["st_mm3"], Vector64)
    mm4 = ExtendedRegister(["st_mm4"], Vector64)
    mm5 = ExtendedRegister(["st_mm5"], Vector64)
    mm6 = ExtendedRegister(["st_mm6"], Vector64)
    mm7 = ExtendedRegister(["st_mm7"], Vector64)

    xmm0 = ExtendedRegister(["xmm0"], Vector128)
    xmm1 = ExtendedRegister(["xmm1"], Vector128)
    xmm2 = ExtendedRegister(["xmm2"], Vector128)
    xmm3 = ExtendedRegister(["xmm3"], Vector128)
    xmm4 = ExtendedRegister(["xmm4"], Vector128)
    xmm5 = ExtendedRegister(["xmm5"], Vector128)
    xmm6 = ExtendedRegister(["xmm6"], Vector128)
    xmm7 = ExtendedRegister(["xmm7"], Vector128)
    xmm8 = ExtendedRegister(["xmm8"], Vector128)
    xmm9 = ExtendedRegister(["xmm9"], Vector128)
    xmm10 = ExtendedRegister(["xmm10"], Vector128)
    xmm11 = ExtendedRegister(["xmm11"], Vector128)
    xmm12 = ExtendedRegister(["xmm12"], Vector128)
    xmm13 = ExtendedRegister(["xmm13"], Vector128)
    xmm14 = ExtendedRegister(["xmm14"], Vector128)
    xmm15 = ExtendedRegister(["xmm15"], Vector128)

    ymm0 = ExtendedRegister(["xmm0", "ymm0_h"], Vector256)
    ymm1 = ExtendedRegister(["xmm1", "ymm1_h"], Vector256)
    ymm2 = ExtendedRegister(["xmm2", "ymm2_h"], Vector256)
    ymm3 = ExtendedRegister(["xmm3", "ymm3_h"], Vector256)
    ymm4 = ExtendedRegister(["xmm4", "ymm4_h"], Vector256)
    ymm5 = ExtendedRegister(["xmm5", "ymm5_h"], Vector256)
    ymm6 = ExtendedRegister(["xmm6", "ymm6_h"], Vector256)
    ymm7 = ExtendedRegister(["xmm7", "ymm7_h"], Vector256)
    ymm8 = ExtendedRegister(["xmm8", "ymm8_h"], Vector256)
    ymm9 = ExtendedRegister(["xmm9", "ymm9_h"], Vector256)
    ymm10 = ExtendedRegister(["xmm10", "ymm10_h"], Vector256)
    ymm11 = ExtendedRegister(["xmm11", "ymm11_h"], Vector256)
    ymm12 = ExtendedRegister(["xmm12", "ymm12_h"], Vector256)
    ymm13 = ExtendedRegister(["xmm13", "ymm13_h"], Vector256)
    ymm14 = ExtendedRegister(["xmm14", "ymm14_h"], Vector256)
    ymm15 = ExtendedRegister(["xmm15", "ymm15_h"], Vector256)

    def __init__(self, debugger: Debugger) -> None:
        self._debugger = debugger
        self._refresh_registers()

    def _refresh_registers(self) -> None:
        """
        An internal method to refresh the cached register values from the debugged process.
        Should be called after every movement of the debugged process to ensure the register values are up to date.
        """
        self._debugger._ensure_running()
        self.standard_regs: dict[str, bytes] = os_interaction.get_standard_regs(self._debugger.child_pid)
        self.extended_regs: dict[str, bytes] = os_interaction.get_extended_regs(self._debugger.child_pid)

    def get(self, reg_name: str) -> CNumBase | VectorRegister:
        """
        Gets the register with the given name.
        """
        self._debugger._ensure_running()
        try:
            return getattr(self, reg_name) # use the getattr method to get the register from the descriptor attribute
        except AttributeError:
            raise KeyError(reg_name) # if the descriptor didn't find the register, we raise a KeyError for consistency with dict-like access
    
    def set(self, reg_name: str, value: RegisterSettableTypes, trigger_updates: bool = True) -> None:
        """
        Sets the register with the given name to the given value.
        """
        self._debugger._ensure_running()
        try:
            desc = vars(type(self))[reg_name] # get the descriptor for the register using vars on the class
            if not isinstance(desc, (StandardRegister, ExtendedRegister)):
                raise KeyError(reg_name) # if it's not a descriptor, it's not a register we can set, so we raise a KeyError
            desc.set_value(self, value, trigger_updates=False) # use the set_value method of the descriptor to set the value without triggering updates (as we will trigger them after)
        except AttributeError:
            raise KeyError(reg_name)
        if trigger_updates:
            self._debugger.update_callbacks.trigger()
    
    def __getitem__(self, key: str) -> CNumBase | VectorRegister:
        """
        Square bracket access to registers.
        Returns the register with the given name, same as get method.
        """
        return self.get(key)
    
    def __setitem__(self, key: str, value: RegisterSettableTypes) -> None:
        """
        Square bracket assignment to registers.
        Sets the register with the given name to the given value, same as set method.
        """
        self.set(key, value)