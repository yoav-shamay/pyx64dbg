from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Collection,
    Iterator,
    Self,
    Type,
    Any,
    TypeVar,
    Iterable,
    Optional,
    overload,
)
from pyx64dbg.number_types import (
    CIntBase,
    CNumBase,
    Float32,
    Float64,
    Int16,
    UInt16,
    Int8,
    UInt32,
    Int32,
    UInt64,
    Int64,
    UInt8,
)

if TYPE_CHECKING:
    from pyx64dbg.registers import Registers


T = TypeVar("T", bound=CNumBase)

num_types_constructible = int | float | CNumBase | bytes


class VectorView[T]:
    """
    A proxy that allows indexing, slicing, and assignment to a VectorRegister as if it were a list of a specific type.
    """

    def __init__(self, parent_vec: VectorRegister, cls: Type[T]) -> None:
        """
        Initializes a VectorView for a specific number type (e.g., Float32, Int16) on a parent VectorRegister.
         - parent_vec: The VectorRegister this view is associated with.
         - cls: The class of the number type
        """
        self._vec: VectorRegister = parent_vec
        self._cls: Type[T] = cls
        self._step: int = cls.size
        self._count: int = self._vec.size // self._step

    # overloads for __getitem__ to indicate return type difference based on slice / number
    @overload
    def __getitem__(self, idx: int | CIntBase) -> T: ...
    @overload
    def __getitem__(self, idx: slice) -> list[T]: ...

    def __getitem__(self, idx: int | CIntBase | slice) -> T | list[T]:
        """
        Square bracket access for the view.
        Supports both integer indexing and slicing.
        Returns a CNum for single index access, or a list of CNums for slice access.
        """
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

    # overloads for __setitem__ to allow both single value and iterable assignment, based on slice / number
    @overload
    def __setitem__(
        self, idx: int | CIntBase, value: num_types_constructible
    ) -> None: ...
    @overload
    def __setitem__(
        self, idx: slice, value: Iterable[num_types_constructible]
    ) -> None: ...

    def __setitem__(
        self,
        idx: int | CIntBase | slice,
        value: Iterable[num_types_constructible] | num_types_constructible,
    ) -> None:
        """
        Square bracket assignment for the view.
        Supports both integer indexing and slicing.
        For single index assignment, value can be an int, float, or CNum, which will be converted to the appropriate type and then to bytes.
        For slice assignment, value should be an iterable of the assignable types.
        """
        # convert the data to bytearray for editing
        updated_data = bytearray(self._vec._data)

        if isinstance(idx, slice):
            indices = range(
                *idx.indices(self._count)
            )  # use range with slice.indices, which handles negative-indices and other cases properly
            # Ensure value is an iterable when slicing
            if not isinstance(
                value, Iterable
            ):  # verify that the value is an iterable, as we expect for slice assignment
                raise TypeError("Can only assign an iterable to a slice")

            if len(value) != len(indices):
                raise ValueError(
                    f"Attempting to assign {len(value)} values to slice of length {len(indices)}"
                )

            for i, val in zip(indices, value):
                self._update_buffer(updated_data, i, val)
        else:
            # Standard integer indexing
            if idx < 0:  # negative indexing support
                idx += self._count
            if idx >= self._count or idx < 0:
                raise IndexError(f"Index {idx} out of range")
            self._update_buffer(updated_data, idx, value)

        # Apply the update back to the main register buffer
        self._vec._data = bytes(updated_data)

        # Trigger the update back to the Registers object (and thus ptrace)
        self._vec._trigger_update()

    def _update_buffer(
        self, buffer: bytearray, idx: int | CIntBase, value: num_types_constructible
    ) -> None:
        """
        Helper to convert a value to bytes and write to the buffer at a specific index.
        """
        value_cls = self._cls(
            value
        )  # Convert to the appropriate CNum type (handles int, float, CNum and bytes inputs)
        new_bytes = value_cls.to_bytes()  # convert to bytes for writing to the buffer
        start = idx * self._step
        buffer[start : start + self._step] = new_bytes

    def __len__(self) -> int:
        """
        Returns the number of elements in the view
        """
        return self._count

    def __repr__(self) -> str:
        """
        Returns a string representation of the view, showing it as a list of the values.
        """
        return str(list(self))

    def __iter__(self) -> Iterator[T]:
        """
        Returns an iterator over the elements in the view, allowing iteration in for loops and other contexts.
        """
        for i in range(self._count):
            yield self[i]

    def __eq__(self, other: Iterable[Any]) -> bool:
        """
        Allows comparison with other collection of numbers, comparing element-wise.
        """
        # Check if the other object isn't Collection (has length and is iterable), otherwise we can't compare
        if not isinstance(other, Collection):
            return NotImplemented

        # Length check is a fast fail
        if len(self) != len(other):
            return False

        # Element-wise comparison
        # This will use the __eq__ of your Int32/Float64 classes
        return all(s == o for s, o in zip(self, other))


class VectorRegister:
    """
    Class for representing vector registers (xmm, ymm, zmm).
    Allows to view it as arrays of different types.
     - Provides properties for different views (for all number types) that return VectorView objects for list-like access.
     They act as a list of the corresponding type
     - Allows scalar access to the lowest index for floats (sf32, sf64).
    """

    size: int | None = None  # to be defined in subclasses

    def __init__(
        self,
        data: bytes,
        parent_regs: Optional["Registers"] = None,
        name: Optional[str] = None,
    ) -> None:
        """
        Constructs a VectorRegister with the given bytes data.
        For internal updates, parent_regs and name should be provided so that changes there trigger a proper ptrace update.
        """
        self._data: bytes = data
        self._parent: Registers | None = parent_regs
        self._name: str | None = name

    def _trigger_update(self) -> None:
        """
        A helper method to trigger an update back to the parent Registers object.
        Should be called when the internal data is updated to ensure the change gets propagated to the debugged process via ptrace.
        """
        if self._parent is not None:
            # Calls the parent Registers.set(name, bytes)
            self._parent.set(self._name, self._data)

    @property
    def f32(self) -> VectorView[Float32]:
        """
        Returns a VectorView for the vector register, with Float32 type.
        """
        return VectorView(self, Float32)

    @f32.setter
    def f32(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from Float32 array.
        """
        self.f32[:] = value  # delegate to the slice setter for the f32 view

    @property
    def f64(self) -> VectorView[Float64]:
        """
        Returns a VectorView for the vector register, with Float64 type.
        """
        return VectorView(self, Float64)

    @f64.setter
    def f64(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from Float64 array.
        """
        self.f64[:] = value  # delegate to the slice setter for the f64 view

    @property
    def i8(self) -> VectorView[Int8]:
        """
        Returns a VectorView for the vector register, with Int8 type.
        """
        return VectorView(self, Int8)

    @i8.setter
    def i8(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from Int8 array.
        """
        self.i8[:] = value  # delegate to the slice setter for the i8 view

    @property
    def u8(self) -> VectorView[UInt8]:
        """
        Returns a VectorView for the vector register, with UInt8 type.
        """
        return VectorView(self, UInt8)

    @u8.setter
    def u8(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from UInt8 array.
        """
        self.u8[:] = value  # delegate to the slice setter for the u8 view

    @property
    def i16(self) -> VectorView[Int16]:
        """
        Returns a VectorView for the vector register, with Int16 type.
        """
        return VectorView(self, Int16)

    @i16.setter
    def i16(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from Int16 array.
        """
        self.i16[:] = value  # delegate to the slice setter for the i16 view

    @property
    def u16(self) -> VectorView[UInt16]:
        """
        Returns a VectorView for the vector register, with UInt16 type.
        """
        return VectorView(self, UInt16)

    @u16.setter
    def u16(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from UInt16 array.
        """
        self.u16[:] = value  # delegate to the slice setter for the u16 view

    @property
    def u32(self) -> VectorView[UInt32]:
        """
        Returns a VectorView for the vector register, with UInt32 type.
        """
        return VectorView(self, UInt32)

    @u32.setter
    def u32(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from UInt32 array.
        """
        self.u32[:] = value  # delegate to the slice setter for the u32 view

    @property
    def i32(self) -> VectorView[Int32]:
        """
        Returns a VectorView for the vector register, with Int32 type.
        """
        return VectorView(self, Int32)

    @i32.setter
    def i32(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from Int32 array.
        """
        self.i32[:] = value  # delegate to the slice setter for the i32 view

    @property
    def u64(self) -> VectorView[UInt64]:
        """
        Returns a VectorView for the vector register, with UInt64 type.
        """
        return VectorView(self, UInt64)

    @u64.setter
    def u64(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from UInt64 array.
        """
        self.u64[:] = value  # delegate to the slice setter for the u64 view

    @property
    def i64(self) -> VectorView[Int64]:
        """
        Returns a VectorView for the vector register, with Int64 type.
        """
        return VectorView(self, Int64)

    @i64.setter
    def i64(self, value: Iterable[num_types_constructible]) -> None:
        """
        Sets the values from Int64 array.
        """
        self.i64[:] = value  # delegate to the slice setter for the i64 view

    # Scalar Views (lowest index only)
    @property
    def sf32(self) -> Float32:
        """
        Scalar Single access for float32 - lowest 32 bits as Float32
        """
        return self.f32[0]

    @sf32.setter
    def sf32(self, value: num_types_constructible) -> None:
        """
        Sets the Scalar Single (lowest 32 bits) from a Float32 value.
        """
        self.f32[0] = value

    @property
    def sf64(self) -> Float64:
        """
        Scalar Double access for float64 - lowest 64 bits as Float64
        """
        return self.f64[0]

    @sf64.setter
    def sf64(self, value: num_types_constructible) -> None:
        """
        Sets the Scalar Double (lowest 64 bits) from a Float64 value.
        """
        self.f64[0] = value

    def __repr__(self):
        """
        Returns a string representation of the vector register.
        Shows the type and the raw bytes in hex for simplicity.
        Access subviews for more detailed representations.
        """
        return f"Vector{self.size}({self._data.hex()})"

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        parent_regs: Optional["Registers"] = None,
        name: Optional[str] = None,
    ) -> Self:
        """
        Constructs a VectorRegister from bytes, with an optional parent Registers reference for updates.
        """
        return cls(data, parent_regs, name)

    def to_bytes(self) -> bytes:
        """
        Converts the VectorRegister back to bytes, which is just the internal data.
        """
        return self._data


class Vector256(VectorRegister):
    """
    A class representing a 256-bit vector register.
    """

    size = 32


class Vector128(VectorRegister):
    """
    A class representing a 128-bit vector register.
    """

    size = 16


class Vector64(VectorRegister):
    """
    A class representing a 64-bit vector register.
    """

    size = 8
