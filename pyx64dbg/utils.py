FIRST_BYTE_MASK = 0xFF

def get_first_byte(word):
    return word & FIRST_BYTE_MASK

def change_first_byte(word, new_first_byte):
    return new_first_byte | (word & ~FIRST_BYTE_MASK)