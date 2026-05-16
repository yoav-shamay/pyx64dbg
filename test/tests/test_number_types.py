from __future__ import annotations
import sys

import pytest
from pyx64dbg.number_types import (
    Int8, Int16, Int32, Int64, 
    UInt8, UInt16, UInt32, UInt64,
    Float32, Float64, Float80
)
import math

sys.set_int_max_str_digits(0) # some numbers are too big to display in strings for pytest

# Helpers to mimic C behavior for test expectations

def c_wrap(val, size_bits, is_signed):
    """
    Wraps a Python int to simulate C integer overflow.
    """
    mask = (1 << size_bits) - 1
    wrapped = val & mask
    if is_signed:
        sign_bit = 1 << (size_bits - 1)
        if wrapped & sign_bit:
            return wrapped - (1 << size_bits)
    return wrapped

def c_div(a, b):
    """
    C-style truncation division.
    """
    res = abs(a) // abs(b)
    if (a < 0) ^ (b < 0):
        return -res
    return res

def c_mod(a, b):
    """
    C-style modulus (result has same sign as dividend).
    """
    res = abs(a) % abs(b)
    return -res if a < 0 else res

@pytest.mark.parametrize(
    "cls, num1, num2,",
    [
        (Int8, -10, 3),
        (Int8, 120, 7),
        (Int16, -1000, 3),
        (Int16, 32000, 1000),
        (Int32, -100000, 3),
        (Int32, 2 ** 31 - 1, 10),
        (Int32, -2 ** 31, -1),
        (Int64, -1_000_000_000, 3),
        (Int64, 2 ** 63 - 1, 1000),
        (UInt8, 2, 3),
        (UInt8, 250, 10),
        (UInt16, 65000, 10),
        (UInt16, 65000, 1000),
        (UInt32, 4_000_000_000, 100),
        (UInt32, 4_000_000_000, 300_000_000),
        (UInt64, 10_000_000_000, 100),
        (UInt64, 18_000_000_000_000_000_000, 1_000_000_000_000_000_000)
    ]
)
def test_integer_behavior(cls, num1, num2):
    """
    Tests general integer behavior (all operators) on a bunch of cases in all integer classes.
    Checks both overflow and non-overflow cases.
    """
    a = cls(num1)
    b = cls(num2)
    bits = cls.size * 8
    signed = cls.is_signed

    # Basic Arithmetic (Checking against C-style helpers)
    assert int(a + b) == c_wrap(num1 + num2, bits, signed)
    assert int(a - b) == c_wrap(num1 - num2, bits, signed)
    assert int(a * b) == c_wrap(num1 * num2, bits, signed)
    if num2 != 0 and (num2 != -1 or num1 != -2**(bits-1)): # avoid division overflow case
        assert int(a // b) == c_div(num1, num2)
        assert int(a % b) == c_mod(num1, num2)
    assert int(-a) == c_wrap(-num1, bits, signed)
    assert int(-b) == c_wrap(-num2, bits, signed)

    # Bitwise (Python shifts don't wrap, so we must wrap the expectation)
    assert int(a << 2) == c_wrap(num1 << 2, bits, signed)
    assert int(a >> 2) == c_wrap(num1 >> 2, bits, signed)
    assert int(a & b) == (num1 & num2)
    assert int(a | b) == (num1 | num2)
    assert int(a ^ b) == (num1 ^ num2)
    assert int(~a) == c_wrap(~num1, bits, signed)
    assert int(~b) == c_wrap(~num2, bits, signed)

    # Comparison
    assert (a > b) == (num1 > num2)
    assert (a < b) == (num1 < num2)
    assert a == a
    assert (a != b) == (num1 != num2)
    assert (a >= b) == (num1 >= num2)
    assert (a <= b) == (num1 <= num2)
    assert a <= a
    assert a >= a
    # check abs
    assert int(abs(a)) == c_wrap(abs(num1), bits, signed)
    assert int(abs(-a)) == c_wrap(abs(c_wrap(-num1, bits, signed)), bits, signed) # we need to do this as negation can cause a wrap and if the number is the minimum negative abs can cause a wrap
    assert int(abs(b)) == c_wrap(abs(num2), bits, signed)
    assert int(abs(-b)) == c_wrap(abs(c_wrap(-num2, bits, signed)), bits, signed) # we need to do this as negation can cause a wrap and if the number is the minimum negative abs can cause a wrap

@pytest.mark.parametrize("cls_higher, cls_lower, val1, val2", [
    # Same size, Signed + Unsigned -> Unsigned wins
    (UInt32, Int32, 1, 1),
    (UInt8, Int8, 1, 1),
    # Different size, Larger size wins
    (Int32, Int8, 1, 1),
    # Signed Higher Rank vs Unsigned Lower Rank -> Signed Higher Rank wins
    (Int32, UInt16, 1, 65535),
    (Int64, UInt32, 1, 1),
    # Float Promotion
    (Float32, UInt64, 1.0, 1),
    (Float64, Float32, 1.0, 1.0),
])
def test_priority(cls_higher, cls_lower, val1, val2):
    """
    Tests that the priority rules for operations between different types are followed correctly.
    """
    a = cls_higher(val1)
    b = cls_lower(val2)

    # Test that the result of an operation between a and b has the type of cls_higher
    assert isinstance(a + b, cls_higher)
    assert a + b == a + cls_higher(b) # check that it doesn't overflow based on lower class
    assert isinstance(b + a, cls_higher)
    assert b + a == a + b # as we already verified a + b value we can compare to it
    assert isinstance(a - b, cls_higher)
    assert a - b == a - cls_higher(b)
    assert isinstance(b - a, cls_higher)
    assert b - a == cls_higher(b) - a

def test_different_type_comparison():
    """
    Tests comparison between different types, which should follow the same priority rules as arithmetic operations.
    """
    assert Int32(-1) == Int64(-1)
    assert UInt8(255) > Int8(120)
    assert Float32(0.5) == 0.5
    assert Float32(0.1) < Float64(0.2)
    assert Int16(-1) > UInt16(1) # as UInt16 has higher priority, this would evaluate to 0xffff > 1 which is true
    assert Int32(-1) < UInt16(1) # this time Int32 has higher priority, so this would evaluate to -1 < 1 which is true


@pytest.mark.parametrize("cls, val1, val2", [
    (Float32, 0.1, 0.2),
    (Float64, 0.1, 0.2),
    (Float80, 0.1, 0.2),
])
def test_float_arithmetic(cls, val1, val2):
    """
    Tests arithmetic and comparison operations on floating point types, and checks that they behave approximately as expected.
    """
    a = cls(val1)
    b = cls(val2)
    
    # Test basic arithmetic
    assert float(a + b) == pytest.approx(val1 + val2)
    assert float(a - b) == pytest.approx(val1 - val2)
    assert float(a * b) == pytest.approx(val1 * val2)
    assert float(a / b) == pytest.approx(val1 / val2)

    assert a == a
    assert a <= a
    assert a >= a
    assert (a != b) == (val1 != val2)
    assert (a < b) == (val1 < val2)
    assert (a > b) == (val1 > val2)
    assert (a <= b) == (val1 <= val2)
    assert (a >= b) == (val1 >= val2)
    
    # Test unary
    assert float(-a) == pytest.approx(-val1)
    # test abs
    assert float(abs(-a)) == pytest.approx(abs(-float(a)))

@pytest.mark.parametrize("cls, val", [
    (Float32, 3.14159),
    (Float64, 3.141592653589793),
    (Float80, 0.1),
    (Int8, -128),
    (Int16, -32768),
    (Int32, -2147483648),
    (Int64, -9223372036854775808),
    (UInt8, 255),
    (UInt16, 65535),
    (UInt32, 4294967295),
    (UInt64, 18446744073709551615),
])
def test_number_types_bytes_roundtrip(cls, val):
    """
    Test the roundtrip of from_bytes and to_bytes on cases for all number types (floats and integers, signed and unsigned)
    """
    num = cls(val)
    raw = num.to_bytes()
    assert len(raw) == cls.size
    assert cls.from_bytes(raw) == num

@pytest.mark.parametrize("cls, val", [
    (Int8, 0),
    (Int16, 0),
    (Int32, 0),
    (Int64, 0),
    (UInt8, 0),
    (UInt16, 0),
    (UInt32, 0),
    (UInt64, 0),
])
def test_division_by_zero(cls, val):
    """
    Tests that division by zero raises a ZeroDivisionError.
    """
    with pytest.raises(ZeroDivisionError):
        _ = cls(val) / 0

@pytest.mark.parametrize("cls", [Float32, Float64, Float80])
def test_float_specials(cls):
    """
    Tests the behavior of infinities and NaN on all float types and operations between them
    """
    inf = cls(float('inf'))
    nan = cls(float('nan'))
    ninf = cls(float('-inf'))
    
    assert math.isinf(float(inf))
    assert math.isnan(float(nan))
    assert math.isinf(float(ninf)) and float(ninf) < 0
    
    # Operations with inf
    assert float(inf + 1.0) == float('inf')
    assert float(ninf + 1.0) == float('-inf')
    assert float(inf + inf) == float('inf')
    assert float(ninf + ninf) == float('-inf')
    # comparisions
    assert nan != nan
    assert inf == inf
    assert ninf == ninf
    assert inf != ninf
    # operations that should result in nan
    assert math.isnan(float(inf + nan))
    assert math.isnan(float(ninf + nan))
    assert math.isnan(float(inf * 0.0))
    assert math.isnan(float(ninf * 0.0))
    assert math.isnan(float(inf / inf))
    assert math.isnan(float(ninf / ninf))
    assert math.isnan(float(inf / ninf))
    assert math.isnan(float(ninf / inf))
    assert math.isnan(float(inf + ninf))
    assert math.isnan(float(ninf + inf))
    assert math.isnan(float(inf - inf))
    assert math.isnan(float(ninf - ninf))

@pytest.mark.parametrize("cls, bytes_val, expected", [
    # Signed Integers
    (Int8,  b"\xff", -1),
    (Int8,  b"\x80", -128),
    (Int16, b"\x00\x80", -32768),
    (Int16, b"\xff\xff", -1),
    (Int32, b"\x00\x00\x00\x80", -2147483648),
    (Int32, b"\xfe\xff\xff\xff", -2),
    (Int64, b"\x00\x00\x00\x00\x00\x00\x00\x80", -9223372036854775808),
    (Int64, b"\xff\xff\xff\xff\xff\xff\xff\xff", -1),

    # Unsigned Integers
    (UInt8,  b"\xff", 255),
    (UInt8,  b"\x80", 128),
    (UInt16, b"\x00\x80", 32768),
    (UInt16, b"\xff\xff", 65535),
    (UInt32, b"\xff\xff\xff\xff", 4294967295),
    (UInt64, b"\xff\xff\xff\xff\xff\xff\xff\xff", 18446744073709551615),

    # Floating Point
    # 1.0 in Float32: 0x3f800000
    (Float32, b"\x00\x00\x80\x3f", 1.0),
    # -2.0 in Float32: 0xc0000000
    (Float32, b"\x00\x00\x00\xc0", -2.0),
    # 1.0 in Float64: 0x3ff0000000000000
    (Float64, b"\x00\x00\x00\x00\x00\x00\xf0\x3f", 1.0),
    # 0.5 in Float64: 0x3fe0000000000000
    (Float64, b"\x00\x00\x00\x00\x00\x00\xe0\x3f", 0.5),
    
    # 1.0 in Float80: 0x3fff8000000000000000
    (Float80, b"\x00\x00\x00\x00\x00\x00\x00\x80\xff\x3f", 1.0),
    # 2.0 in Float80: 0x40008000000000000000
    (Float80, b"\x00\x00\x00\x00\x00\x00\x00\x80\x00\x40", 2.0),
])

def test_from_bytes(cls, bytes_val, expected):
    """
    Tests that from_bytes works correctly based on an hardcoded representations.
    """
    result = cls.from_bytes(bytes_val)
    assert result == expected
    # Ensure it' returns the correct class
    assert isinstance(result, cls)

def test_float80_precision():
    """
    Test that float80 is more precise than standard python float by comparing difference of close values.
    The numbers should be close enough that they are indistinguishable in Float32 and Float64, but different in Float80.
    """
    base = Float80(1.0)
    small_increment = Float80(1e-18)
    a = base + small_increment
    b = base + small_increment * 2
    diff = b - a
    tolerance = 1e-19 # we need to define custom tolerance as pytest.approx will consider 0 and 1e-18 to be approximately equal. This is small enough to not have false-positives.
    assert float(diff) == pytest.approx(float(small_increment), abs=tolerance)

def test_overflow_in_initialization():
    """
    Tests that initializing with a value that overflows correctly wraps around, instead of raising an error or something else.
    """
    assert int(Int8(128)) == -128
    assert int(Int8(-129)) == 127
    assert int(UInt8(257)) == 1
    assert int(Int64(2 ** 63 + 5)) == -2 ** 63 + 5
    assert float(Float32(1e40)) == float('inf')  # Overflow to infinity for floats
    assert float(Float32(-1e40)) == float('-inf')
    assert float(Float80(1e500)) == float('inf')
    assert float(Float80(-1e500)) == float('-inf')


def test_truthiness():
    """
    Tests that __bool__ protocol correctly handles 0, 0.0, and non-zeros
    """
    assert not bool(Int32(0))
    assert bool(Int32(-1))
    assert not bool(Float64(0.0))
    assert bool(Float64(0.5))

def test_shift_wrapping():
    """
    Tests that shifting beyond bitwidth wraps gracefully instead of UB
    """
    assert int(Int8(1) << 8) == 0 # masking for int8 and int16 are still 31
    assert int(Int16(1) << 16) == 0
    assert int(Int32(1) << 33) == 2
    assert int(Int64(1) << 66) == 4
    assert int(UInt32(1) << 33) == 2
    assert int(UInt64(1) << 66) == 4

def test_inplace_promotion():
    """
    Tests that in-place operations do not promote, unlike normal operations.
    """
    a = Int32(1)
    a += Float32(2.5)
    assert isinstance(a, Int32)
    assert int(a) == 3

    b = UInt16(100)
    b *= Float64(2.5)
    assert isinstance(b, UInt16)
    assert int(b) == 250

def test_division_overflow_exception():
    """
    Tests that division overflow raises an exception instead of UB
    """
    with pytest.raises(OverflowError):
        _ = Int32(-2**31) // -1
    with pytest.raises(OverflowError):
        _ = Int64(-2**63) // -1

# possible operations for the below test
div = lambda a, b: a / b
add = lambda a, b: a + b

@pytest.mark.parametrize("cls, val1, val2, result, operator", [
    (Float32, 0.0, 0.0, float('nan'), div),
    (Float64, 0.0, 0.0, float('nan'), div),
    (Float80, 0.0, 0.0, float('nan'), div),
    (Float32, 1.0, 0.0, float('inf'), div),
    (Float64, 1.0, 0.0, float('inf'), div),
    (Float80, 1.0, 0.0, float('inf'), div),
    (Float32, -1.0, 0.0, float('-inf'), div),
    (Float64, -1.0, 0.0, float('-inf'), div),
    (Float80, -1.0, 0.0, float('-inf'), div),
    (Float32, 2e38, 2e38, float('inf'), add),
    (Float64, 1e308, 1e308, float('inf'), add),
    (Float80, 10 ** 4932, 10 ** 4932, float('inf'), add), # too big to fit in float, we need to use an int
    (Float32, -2e38, -2e38, float('-inf'), add),
    (Float64, -1e308, -1e308, float('-inf'), add),
    (Float80, -(10 ** 4932), -(10 ** 4932), float('-inf'), add),
])
def test_special_float_result(cls, val1, val2, result, operator):
    """
    Tests operations with normal numbers that result in special float values (inf and nan) to ensure they are handled correctly.
    """
    a = cls(val1)
    b = cls(val2)
    # check that a and b are normal
    assert not math.isnan(float(a)) # as nan != nan, for nan test we convert to float and check with math.isnan
    assert not math.isnan(float(b))
    assert a != float('inf') and a != float('-inf')
    assert b != float('inf') and b != float('-inf')
    res = operator(a, b)
    if math.isnan(result): # nan != nan so we can't compare it
        assert math.isnan(float(res))
    else: # inf == inf so we can compare directly
        assert res == result

def test_inf_initialization():
    """
    Test that initializing floats with too big numbers result in infinity (and same for -inf)
    """
    assert float(Float32(1e40)) == float('inf')
    assert float(Float64(10 ** 309)) == float('inf')
    assert float(Float80(10 ** 4939)) == float('inf')
    assert float(Float32(-1e40)) == float('-inf')
    assert float(Float64(-(10 ** 309))) == float('-inf')
    assert float(Float80(-(10 ** 4939))) == float('-inf')

def test_long_double_to_string():
    """
    Test that long double can be converted to string without showing inf
    """
    assert str(Float80(10 ** 1000)) == "1e+1000"
    assert str(Float80(-(10 ** 1000))) == "-1e+1000"