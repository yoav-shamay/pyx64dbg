SECOND_BYTE_MASK = 0xFF00
FIRST_BYTE_MASK = 0xFF

def get_first_byte(word):
    return word & FIRST_BYTE_MASK

def change_first_byte(word, new_first_byte):
    return new_first_byte | (word & SECOND_BYTE_MASK)

def split_bytes(word):
    return [word & FIRST_BYTE_MASK, (word & SECOND_BYTE_MASK) >> 8]

def create_word(first_byte, second_byte):
    return first_byte | (second_byte << 8)

def get_bits_range(value, start_bit, num_bits):
    mask = (1 << num_bits) - 1
    return (value >> start_bit) & mask

def set_bits_range(value, start_bit, num_bits, new_value):
    mask = ((1 << num_bits) - 1) << start_bit
    return (value & ~mask) | ((new_value << start_bit) & mask)

def signed_to_unsigned(value, num_bits):
    if value < 0:
        value += 1 << num_bits
    return value

def unsigned_to_signed(value, num_bits):
    if value >= 1 << (num_bits - 1):
        value -= 1 << num_bits
    return value

def in_range(value, num_bits, signed):
    if signed:
        return -(1 << (num_bits - 1)) <= value < (1 << (num_bits - 1))
    else:
        return 0 <= value < (1 << num_bits)