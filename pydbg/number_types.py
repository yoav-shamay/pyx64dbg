"""
C-like number types for the debugger.
Available types:
- Int8, UInt8 / Char, UChar
- Int16, UInt16 / Short, UShort
- Int32, UInt32 / Int, UInt
- Int64, UInt64 / Long, ULong
"""

import ctypes
from cint import CInt
from pydbg.cfloat import CFloat

# integer types

class Int8(CInt[ctypes.c_int8]):
    type = ctypes.c_int8
    priority = 1
    is_signed = True
    size = 1

class UInt8(CInt[ctypes.c_uint8]):
    type = ctypes.c_uint8
    priority = 2
    is_signed = False
    size = 1

class Int16(CInt[ctypes.c_int16]):
    type = ctypes.c_int16
    priority = 3
    is_signed = True
    size = 2

class UInt16(CInt[ctypes.c_uint16]):
    type = ctypes.c_uint16
    priority = 4
    is_signed = False
    size = 2

class Int32(CInt[ctypes.c_int32]):
    type = ctypes.c_int32
    priority = 5
    is_signed = True
    size = 4

class UInt32(CInt[ctypes.c_uint32]):
    type = ctypes.c_uint32
    priority = 6
    is_signed = False
    size = 4

class Int64(CInt[ctypes.c_int64]):
    type = ctypes.c_int64
    priority = 7
    is_signed = True
    size = 8

class UInt64(CInt[ctypes.c_uint64]):
    type = ctypes.c_uint64
    priority = 8
    is_signed = False
    size = 8

# common aliases
Char = Int8
UChar = UInt8
Short = Int16
UShort = UInt16
Int = Int32
UInt = UInt32
Long = Int64
ULong = UInt64

class Float32(CFloat[ctypes.c_float]):
    type = ctypes.c_float
    priority = 10  # Higher than ints
    size = 4

class Float64(CFloat[ctypes.c_double]):
    type = ctypes.c_double
    priority = 11
    size = 8

class Float80(CFloat[ctypes.c_longdouble]):
    type = ctypes.c_longdouble
    priority = 12
    size = 10

# Common aliases
Float = Float32
Double = Float64
LongDouble = Float80