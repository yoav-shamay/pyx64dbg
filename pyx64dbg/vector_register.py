from typing import Type, Any, Union, Iterable
from pyx64dbg.number_types import Float32, Float64, Int16, UInt16, Int8, UInt32, Int32, UInt64, Int64, UInt8


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

    def __iter__(self):
        """Allows list(vector_view) and 'for x in vector_view' to work efficiently."""
        for i in range(self._count):
            yield self[i]

    def __eq__(self, other):
        """Allows comparison with other VectorViews, lists, or tuples."""
        # 1. Check if the other object is a list-like container
        if not isinstance(other, (VectorView, list, tuple)):
            return NotImplemented
        
        # 2. Length check is a fast fail
        if len(self) != len(other):
            return False
        
        # 3. Element-wise comparison
        # This will use the __eq__ of your Int32/Float64 classes
        return all(s == o for s, o in zip(self, other))


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

    @f32.setter
    def f32(self, value : Iterable[Float32 | float | int]):
        self.f32[:] = value # delegate to the slice setter for the f32 view

    @property
    def f64(self):
        return VectorView(self, Float64)

    @f64.setter
    def f64(self, value : Iterable[Float64 | float | int]):
        self.f64[:] = value # delegate to the slice setter for the f64 view
    
    @property
    def i8(self):
        return VectorView(self, Int8)

    @i8.setter
    def i8(self, value : Iterable[Int8 | int]):
        self.i8[:] = value # delegate to the slice setter for the i8 view

    @property
    def u8(self):
        return VectorView(self, UInt8)
    
    @u8.setter
    def u8(self, value : Iterable[UInt8 | int]):
        self.u8[:] = value # delegate to the slice setter for the u8 view
    
    @property
    def i16(self):
        return VectorView(self, Int16)
    
    @i16.setter
    def i16(self, value : Iterable[Int16 | int]):
        self.i16[:] = value # delegate to the slice setter for the i16 view

    @property
    def u16(self):
        return VectorView(self, UInt16)
    
    @u16.setter
    def u16(self, value : Iterable[UInt16 | int]):
        self.u16[:] = value # delegate to the slice setter for the u16 view

    @property
    def u32(self):
        return VectorView(self, UInt32)

    @u32.setter
    def u32(self, value : Iterable[UInt32 | int]):
        self.u32[:] = value # delegate to the slice setter for the u32 view

    @property
    def i32(self):
        return VectorView(self, Int32)

    @i32.setter
    def i32(self, value : Iterable[Int32 | int]):
        self.i32[:] = value # delegate to the slice setter for the i32 view

    @property
    def u64(self):
        return VectorView(self, UInt64)

    @u64.setter
    def u64(self, value : Iterable[UInt64 | int]):
        self.u64[:] = value # delegate to the slice setter for the u64 view

    @property
    def i64(self):
        return VectorView(self, Int64)

    @i64.setter
    def i64(self, value : Iterable[Int64 | int]):
        self.i64[:] = value # delegate to the slice setter for the i64 view

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
