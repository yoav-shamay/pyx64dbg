from typing import Type, Any, Union, Iterable
from number_types import Float32, Float64, Int16, UInt16, Int8, UInt32, Int32, UInt64, Int64, UInt8


class VectorView:
    """
    A proxy that allows indexing, slicing, and assignment for vector lanes.
    """

    def __init__(self, parent_vec: "VectorRegister", cls: Type[Any]):
        self._vec = parent_vec
        self._cls = cls
        self._step = cls.size
        self._count = self._vec.size // self._step

    def __getitem__(self, idx: Union[int, slice]):
        if isinstance(idx, slice):
            # Return a list of objects for the given slice, recursively using __getitem__ for each index in the slice
            return [self[i] for i in range(*idx.indices(self._count))]

        # Standard integer indexing
        if idx < 0:
            # Handle negative indexing
            idx += self._count
        if idx >= self._count or idx < 0:
            raise IndexError(f"Index {idx} out of range")

        start = idx * self._step
        return self._cls.from_bytes(self._vec._data[start : start + self._step])

    def __setitem__(self, idx: Union[int, slice], value: Any):
        updated_data = bytearray(self._vec._data)

        if isinstance(idx, slice):
            indices = range(*idx.indices(self._count))
            # Ensure value is an iterable when slicing
            if not isinstance(value, Iterable):
                raise TypeError("Can only assign an iterable to a slice")

            for i, val in zip(indices, value):
                self._update_buffer(updated_data, i, val)
        else:
            # Standard integer indexing
            if idx < 0:
                idx += self._count
            if idx >= self._count or idx < 0:
                raise IndexError(f"Index {idx} out of range")
            self._update_buffer(updated_data, idx, value)

        # Apply the update back to the main register buffer
        self._vec._data = bytes(updated_data)

        # Trigger the update back to the Registers object (and thus ptrace)
        self._vec._trigger_update()

    def _update_buffer(self, buffer: bytearray, idx: int, value: Any):
        """Helper to convert a value to bytes and write to the buffer at a specific lane."""
        if not isinstance(value, self._cls):
            value = self._cls(value)

        new_bytes = value.to_bytes()
        start = idx * self._step
        buffer[start : start + self._step] = new_bytes

    def __len__(self):
        return self._count

    def __repr__(self):
        return str(list(self))


class VectorRegister:
    """
    Class for representing vector registers (xmm, ymm, zmm) with support for lane-wise access and modification.
     - Provides properties for different views (f32, f64, i8, u8, i16, u16, u32, i32, u64, i64) that return VectorView objects for lane access.
     They act as a list of the correspending type
     - Allows scalar access to the lowest lane for floats (sf32, sf64).
    """
    size = None # to be defined in subclasses
    def __init__(self, data: bytes, parent_regs: Any, name: str):
        self._data = data
        self._parent = parent_regs
        self._name = name
        self.size = len(data)

    def _trigger_update(self):
        # Calls the parent Registers.set(name, bytes)
        self._parent.set(self._name, self._data)

    @property
    def f32(self):
        return VectorView(self, Float32)

    @property
    def f64(self):
        return VectorView(self, Float64)

    @property
    def i8(self):
        return VectorView(self, Int8)

    @property
    def u8(self):
        return VectorView(self, UInt8)
    
    @property
    def i16(self):
        return VectorView(self, Int16)

    @property
    def u16(self):
        return VectorView(self, UInt16)

    @property
    def u32(self):
        return VectorView(self, UInt32)

    @property
    def i32(self):
        return VectorView(self, Int32)

    @property
    def u64(self):
        return VectorView(self, UInt64)

    @property
    def i64(self):
        return VectorView(self, Int64)

    # --- Scalar Views (lowest lane only) ---
    @property
    def sf32(self):
        """Scalar Single (float32) - lowest 32 bits"""
        return self.f32[0]

    @sf32.setter
    def sf32(self, value):
        self.f32[0] = value

    @property
    def sf64(self):
        """Scalar Double (float64) - lowest 64 bits"""
        return self.f64[0]

    @sf64.setter
    def sf64(self, value):
        self.f64[0] = value

    def __repr__(self):
        # Default view for the console, should just show the raw bytes in hex
        # subviews can be used for more detailed access
        return f"Vector{self.size}({self._data.hex()})"

    @classmethod
    def from_bytes(cls, data: bytes, parent_regs: Any):
        return cls(data, parent_regs)
    
    def to_bytes(self) -> bytes:
        return self._data

class Vector256(VectorRegister):
    size = 32

class Vector128(VectorRegister):
    size = 16

class Vector64(VectorRegister):
    size = 8
