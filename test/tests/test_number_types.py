import pytest
from pyx64dbg.number_types import (
    Int8, Int16, Int32, Int64, 
    UInt8, UInt16, UInt32, UInt64,
    Float32, Float64, Float80
)
import math

# --- Helpers to mimic C behavior for test expectations ---

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
    "cls, num1, num2, overflow_num_1, overflow_num_2",
    [
        (Int8, -10, 3, 120, 10),
        (Int16, -1000, 3, 32000, 1000),
        (Int32, -100000, 3, 2_147_483_640, 10),
        (Int64, -1_000_000_000, 3, 9_223_372_036_854_775_800, 10),
        (UInt8, 250, 10, 250, 10),
        (UInt16, 65000, 10, 65000, 1000),
        (UInt32, 4_000_000_000, 100, 4_000_000_000, 300_000_000),
        (UInt64, 10_000_000_000, 100, 18_000_000_000_000_000_000, 1_000_000_000_000_000_000),
    ]
)
def test_integer_behavior(cls, num1, num2, overflow_num_1, overflow_num_2):
    a = cls(num1)
    b = cls(num2)
    bits = cls.size * 8
    signed = cls.is_signed

    # Basic Arithmetic (Checking against C-style helpers)
    assert int(a + b) == c_wrap(num1 + num2, bits, signed)
    assert int(a - b) == c_wrap(num1 - num2, bits, signed)
    assert int(a * b) == c_wrap(num1 * num2, bits, signed)
    assert int(a // b) == c_div(num1, num2)
    assert int(a % b) == c_mod(num1, num2)

    # Bitwise (Python shifts don't wrap, so we must wrap the expectation)
    assert int(a << 2) == c_wrap(num1 << 2, bits, signed)
    assert int(a >> 2) == c_wrap(num1 >> 2, bits, signed)
    assert int(a & b) == (num1 & num2)
    assert int(a | b) == (num1 | num2)
    assert int(a ^ b) == (num1 ^ num2)

    # Comparison
    assert (a > b) == (num1 > num2)
    assert (a < b) == (num1 < num2)
    assert a == a
    assert (a != b) == (num1 != num2)
    assert (a >= b) == (num1 >= num2)
    assert (a <= b) == (num1 <= num2)
    assert a <= a
    assert a >= a

    # Overflow verification
    d = cls(overflow_num_1)
    e = cls(overflow_num_2)
    res = d + e
    assert int(res) == c_wrap(overflow_num_1 + overflow_num_2, bits, signed)
    assert isinstance(res, cls)

def test_priority():
    # 1. Same size, Signed + Unsigned -> Unsigned wins
    res1 = UInt32(1) + Int32(1)
    assert isinstance(res1, UInt32)
    assert res1 == UInt32(2)
    res2 = Int8(1) + UInt8(1)
    assert isinstance(res2, UInt8)
    assert res2 == UInt8(2)

    # 2. Different size -> Larger size wins
    res3 = Int8(1) + Int32(1)
    assert isinstance(res3, Int32)
    assert res3 == Int32(2)
    
    # 3. Signed Higher Rank vs Unsigned Lower Rank -> Signed Higher Rank wins
    res3 = UInt16(65535) + Int32(1)
    assert isinstance(res3, Int32)
    assert res3 == Int32(65536)
    res4 = UInt32(1) + Int64(1)
    assert isinstance(res4, Int64)
    assert res4 == Int64(2)

    # 4. Float Promotion
    res5 = UInt64(1) + Float32(1.0)
    assert isinstance(res5, Float32)
    assert float(res5) == pytest.approx(2.0)
    res6 = Float32(1.0) + Float64(1.0)
    assert isinstance(res6, Float64)
    assert float(res6) == pytest.approx(2.0)

def test_different_type_comparison():
    assert Int32(-1) == Int64(-1)
    assert UInt8(255) > Int8(120)
    assert Float32(0.5) == 0.5
    assert Float32(0.1) < Float64(0.2)
    assert Int16(-1) < UInt16(1)


@pytest.mark.parametrize("cls, val1, val2", [
    (Float32, 0.1, 0.2),
    (Float64, 0.1, 0.2),
    (Float80, 0.1, 0.2),
])
def test_float_arithmetic(cls, val1, val2):
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
    assert float(abs(cls(-5.5))) == pytest.approx(5.5)

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
    num = cls(val)
    raw = num.to_bytes()
    assert len(raw) == cls.size
    assert cls.from_bytes(raw) == num

def test_float_division_by_zero():
    with pytest.raises(ZeroDivisionError):
        _ = Float32(1.0) / 0.0

def test_float_specials():
    inf = Float32(float('inf'))
    nan = Float32(float('nan'))
    
    assert math.isinf(float(inf))
    assert math.isnan(float(nan))
    
    # Operations with inf
    assert math.isinf(float(inf + 1.0))

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
    result = cls.from_bytes(bytes_val)
    assert result == expected
    # Ensure it's not just a Python int/float but our custom wrapper
    assert isinstance(result, cls)