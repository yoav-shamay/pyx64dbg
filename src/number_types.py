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

# integer types

class Int8(CInt[ctypes.c_int8]):
    type = ctypes.c_int8
    priority = 1
    is_signed = True
    size = 8

class UInt8(CInt[ctypes.c_uint8]):
    type = ctypes.c_uint8
    priority = 2
    is_signed = False
    size = 8

class Int16(CInt[ctypes.c_int16]):
    type = ctypes.c_int16
    priority = 3
    is_signed = True
    size = 16

class UInt16(CInt[ctypes.c_uint16]):
    type = ctypes.c_uint16
    priority = 4
    is_signed = False
    size = 16

class Int32(CInt[ctypes.c_int32]):
    type = ctypes.c_int32
    priority = 5
    is_signed = True
    size = 32

class UInt32(CInt[ctypes.c_uint32]):
    type = ctypes.c_uint32
    priority = 6
    is_signed = False
    size = 32

class Int64(CInt[ctypes.c_int64]):
    type = ctypes.c_int64
    priority = 7
    is_signed = True
    size = 64

class UInt64(CInt[ctypes.c_uint64]):
    type = ctypes.c_uint64
    priority = 8
    is_signed = False
    size = 64

# common aliases
Char = Int8
UChar = UInt8
Short = Int16
UShort = UInt16
Int = Int32
UInt = UInt32
Long = Int64
ULong = UInt64

signed_integers_by_width = {
    8: Int8,
    16: Int16,
    32: Int32,
    64: Int64,
}

unsigned_integers_by_width = {
    8: UInt8,
    16: UInt16,
    32: UInt32,
    64: UInt64,
}