from __future__ import annotations
import ctypes
from typing import Generic, TypeVar, Any

CT = TypeVar("CT", bound=ctypes._SimpleCData)

class CFloat(Generic[CT]):
    """
    Base class for C-style floating point types.
    Enforces precision clamping via ctypes storage.
    Supports arithmetic and comparisons with automatic type promotion.
    """
    type: type[CT]      # ctypes type (c_float, c_double, c_longdouble)
    priority: int = 0   # For type promotion
    size: int = 0       # Size in bytes
    is_signed = True   # Floats are always signed

    def __init__(self, value: float | int | CFloat[Any] | bytes):
        if isinstance(value, CFloat):
            self.num = self.type(value.num.value)
        elif isinstance(value, bytes):
            self.num = self.type()
            ctypes.memmove(ctypes.addressof(self.num), value, self.size)
        else:
            self.num = self.type(value)

    def _fix_type(self, other: Any) -> float | None:
        if hasattr(other, "num"):
            return float(other.num.value)
        if isinstance(other, (int, float)):
            return float(other)
        return NotImplemented

    def _choose_result_type(self, other: Any) -> type[CFloat]:
        if hasattr(other, "priority"):
            return self.__class__ if self.priority >= other.priority else other.__class__
        return self.__class__

    # --- Arithmetic ---

    def __add__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        return self._choose_result_type(other)(self.num.value + rhs)

    def __radd__(self, other):
        return self.__add__(other)

    def __iadd__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        self.num.value += rhs
        return self

    def __sub__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        return self._choose_result_type(other)(self.num.value - rhs)

    def __rsub__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented: return NotImplemented
        return self._choose_result_type(other)(lhs - self.num.value)

    def __isub__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        self.num.value -= rhs
        return self

    def __mul__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        return self._choose_result_type(other)(self.num.value * rhs)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __imul__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        self.num.value *= rhs
        return self

    def __truediv__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        if rhs == 0.0: raise ZeroDivisionError("float division by zero")
        return self._choose_result_type(other)(self.num.value / rhs)

    def __rtruediv__(self, other):
        lhs = self._fix_type(other)
        if lhs is NotImplemented: return NotImplemented
        return self._choose_result_type(other)(lhs / self.num.value)

    def __itruediv__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        self.num.value /= rhs
        return self

    def __neg__(self):
        return self.__class__(-self.num.value)

    def __abs__(self):
        return self.__class__(abs(self.num.value))

    # --- Comparisons ---

    def __eq__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return False
        return self.num.value == rhs

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        return self.num.value < rhs

    def __le__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        return self.num.value <= rhs

    def __gt__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        return self.num.value > rhs

    def __ge__(self, other):
        rhs = self._fix_type(other)
        if rhs is NotImplemented: return NotImplemented
        return self.num.value >= rhs

    # --- Conversion & Helpers ---

    def __float__(self):
        return float(self.num.value)

    def __int__(self):
        return int(self.num.value)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.num.value})"

    def __str__(self):
        return str(self.num.value)

    @classmethod
    def from_bytes(cls, data: bytes):
        obj = cls.type()
        # Copy the bytes into the ctypes object memory, ensuring we get the exact hardware representation
        ctypes.memmove(ctypes.addressof(obj), data, cls.size)
        return cls(obj.value)

    def to_bytes(self) -> bytes:
        cls = self.__class__
        # Get the raw bytes from the ctypes object memory, which gives us the exact hardware representation
        res = ctypes.string_at(ctypes.addressof(self.num), cls.size)
        return res