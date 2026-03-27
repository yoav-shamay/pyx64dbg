FIRST_BYTE_MASK = 0xFF
WORD_SIZE = 8

def get_first_byte(word):
    return word & FIRST_BYTE_MASK

def change_first_byte(word, new_first_byte):
    return new_first_byte | (word & ~FIRST_BYTE_MASK)

def change_byte_prefix(word, pref, byte_cnt):
    mask = (1 << (byte_cnt * 8)) - 1
    return pref | (word & ~mask)

def split_bytes(word, byte_cnt=WORD_SIZE):
    return list(word.to_bytes(byte_cnt, byteorder='little'))

def create_word(byte_list):
    return int.from_bytes(byte_list, byteorder='little')

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