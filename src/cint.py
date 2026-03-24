import ctypes
from typing import Generic, TypeVar

CT = TypeVar("CT", bound=ctypes._SimpleCData)

def _c_divide(num1, num2):
    # C integer division truncates towards zero, while Python's truncates towards negative infinity
    if num2 == 0:
        raise ZeroDivisionError("division by zero")
    elif (num1 < 0) == (num2 < 0):
        return num1 // num2
    else:
        return -(abs(num1) // abs(num2))
    
def _c_mod(num1, num2):
    # C modulus operator returns the remainder of the division, which can be negative if num1 is negative
    if num2 == 0:
        raise ZeroDivisionError("modulo by zero")
    if num1 >= 0:
        return num1 % num2
    else:
        return -((-num1) % num2)

class CInt(Generic[CT]):
    """
    Base class for C-style integer types.
    Generic over a ctypes type (e.g., ctypes.c_int32) that defines the underlying C type.
    Supports arithmetic and bitwise operations, as well as comparisons, with proper type promotion.
    """
    type: type[CT] # ctypes type, should be set by subclasses
    priority: int = None  # Priority for type promotion, should be set by subclasses
    is_signed : bool = None # Indicates whether the type is signed, should be set by subclasses
    size : int = None # Size in bytes, should be set by subclasses

    def __init__(self, value: int | "CInt[CT]"):
        if isinstance(value, CInt):
            value = int(value)
        self.num = self.type(value)

    def _fix_type(self, other) -> int:
        if isinstance(other, CInt):
            return int(other)
        if isinstance(other, int):
            return other
        return NotImplemented
    
    def _choose_result_type(self, other):
        if isinstance(other, CInt):
            return self.__class__ if self.priority >= other.priority else other.__class__
        return self.__class__

    def __add__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(self.num.value + rhs)

    def __radd__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(lhs + self.num.value)

    def __iadd__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        self.num.value += rhs
        return self

    
    def __sub__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(self.num.value - rhs)

    def __rsub__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(lhs - self.num.value)

    def __isub__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        self.num.value -= rhs
        return self
    
    def __mul__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(self.num.value * rhs)
    
    def __rmul__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(lhs * self.num.value)
    
    def __imul__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        self.num.value *= rhs
        return self
    
    def __floordiv__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        result = _c_divide(self.num.value, rhs)
        return result_type(result)
    
    def __rfloordiv__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        result = _c_divide(lhs, self.num.value)
        return result_type(result)
    
    def __ifloordiv__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result = _c_divide(self.num.value, rhs)
        self.num.value = result
        return self
    
    def __mod__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        result = _c_mod(self.num.value, rhs)
        return result_type(result)
    
    def __rmod__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        result = _c_mod(lhs, self.num.value)
        return result_type(result)

    def __imod__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result = _c_mod(self.num.value, rhs)
        self.num.value = result
        return self
    
    def __lshift__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        return self.__class__(self.num.value << rhs)
    
    def __ilshift__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        self.num.value <<= rhs
        return self
    
    def __rshift__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        return self.__class__(self.num.value >> rhs)
    
    def __irshift__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        self.num.value >>= rhs
        return self
    
    def __and__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(self.num.value & rhs)
    
    def __rand__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(lhs & self.num.value)

    def __iand__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        self.num.value &= rhs
        return self
    
    def __or__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(self.num.value | rhs)
    
    def __ror__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(lhs | self.num.value)
    
    def __ior__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        self.num.value |= rhs
        return self
    
    def __xor__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(self.num.value ^ rhs)
    
    def __rxor__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented:
            return NotImplemented
        result_type = self._choose_result_type(other)
        return result_type(lhs ^ self.num.value)
    
    def __ixor__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        self.num.value ^= rhs
        return self
    
    def __neg__(self):
        return self.__class__(-self.num.value)
    
    def __invert__(self):
        return self.__class__(~self.num.value)
    
    def __eq__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        return self.num.value == rhs
    
    def __ne__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        return self.num.value != rhs
    
    def __lt__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        return self.num.value < rhs
    
    def __le__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        return self.num.value <= rhs
    
    def __gt__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        return self.num.value > rhs
    
    def __ge__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented:
            return NotImplemented
        return self.num.value >= rhs

    def __int__(self):
        return self.num.value
    
    def __repr__(self):
        return f"{self.__class__.__name__}({self.num.value})"
    
    def __str__(self):
        return str(self.num.value)
    
    def __bool__(self):
        return self.num.value != 0
    
    def __index__(self):
        return self.num.value
    
    @classmethod
    def from_bytes(cls, bytes_data : bytes, byteorder='little'):
        int_value = int.from_bytes(bytes_data, byteorder=byteorder, signed=cls.is_signed)
        return cls(int_value)
    
    def to_bytes(self, byteorder='little'):
        size = self.size
        return self.num.value.to_bytes(size, byteorder=byteorder, signed=self.is_signed)
