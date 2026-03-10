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