from number_types import Int64, UInt16, UInt32, UInt64
import ptrace
from shared_object import SharedObject

AUXV_ENTRY_SIZE = 16
AUXV_ENTRY_TYPE_OFFSET = 0
AUXV_ENTRY_VALUE_OFFSET = 8

AT_ENTRY = Int64(9)
AT_BASE = Int64(7)

PT_DYNAMIC = 2

E_PHOFF_OFFSET = 0x20
E_PHNUM_OFFSET = 0x38

PROGRAM_HEADER_ENTRY_SIZE = 0x38
PROGRAM_HEADER_ENTRY_TYPE_OFFSET = 0x0
PROGRAM_HEADER_ENTRY_VALUE_OFFSET = 0x10

DYNAMIC_SECTION_ENTRY_SIZE = 0x10
DYNAMIC_SECTION_ENTRY_TYPE_OFFSET = 0x0
DYNAMIC_SECTION_ENTRY_VALUE_OFFSET = 0x8
DT_DEBUG = 21

R_DEBUG_LINKMAP_OFFSET = 0x8

LINKMAP_BASE_OFFSET = 0x0
LINKMAP_NAME_OFFSET = 0x8
LINKMAP_NEXT_OFFSET = 0x18

DT_NULL = 0

VDSO_NAME = b"linux-vdso.so.1"

def _get_auxv(self):
    file_path = f"/proc/{self.child_pid}/auxv"
    with open(file_path, "rb") as f:
        auxv_content = f.read()
    auxv = {}
    for i in range(0, len(auxv_content), AUXV_ENTRY_SIZE):
        entry_type_bytes = auxv_content[i + AUXV_ENTRY_TYPE_OFFSET : i + AUXV_ENTRY_TYPE_OFFSET + 8]
        entry_value_bytes = auxv_content[i + AUXV_ENTRY_VALUE_OFFSET : i + AUXV_ENTRY_VALUE_OFFSET + 8]
        entry_type = UInt64.from_bytes(entry_type_bytes)
        entry_value = UInt64.from_bytes(entry_value_bytes)
        auxv[entry_type] = entry_value
    return auxv


def _init_base_address_and_ld_Base(self, entry_offset):
    auxv = self._get_auxv()
    if AT_ENTRY in auxv:
        self.base_address = auxv[AT_ENTRY] - entry_offset
    else:
        raise Exception("Cannot find base address from auxiliary vector")
    if AT_BASE in auxv:
        self.ld_base = auxv[AT_BASE]
    else:
        raise Exception("Cannot find ld base address from auxiliary vector")

def _get_program_header_address(self, base_address):
    e_phoff_address = base_address + E_PHOFF_OFFSET # program header table address in the elf header
    e_phoff_value = self.read_number(e_phoff_address, UInt64)
    return e_phoff_value + base_address

def _get_program_header_entry_count(self, base_address):
    e_phnum_address = base_address + E_PHNUM_OFFSET # number of program headers in the elf header
    e_phnum_value = self.read_number(e_phnum_address, UInt16)
    return e_phnum_value

def _get_dynamic_section_address(self, base_address):
    program_header_address = self._get_program_header_address(base_address)
    program_header_entry_count = self._get_program_header_entry_count(base_address)
    for i in range(program_header_entry_count):
        entry_address = program_header_address + i * PROGRAM_HEADER_ENTRY_SIZE # size of each program header entry in 64-bit elf
        entry_type = self.read_number(entry_address + PROGRAM_HEADER_ENTRY_TYPE_OFFSET, UInt32)
        if entry_type == PT_DYNAMIC:
            dynamic_section_address = self.read_number(entry_address + PROGRAM_HEADER_ENTRY_VALUE_OFFSET, UInt64) # offset of the dynamic section in the elf header
            return dynamic_section_address + base_address
    raise Exception("Cannot find dynamic section in program headers")

def _get_r_debug_address(self, base_address):
    dynamic_section_address = self._get_dynamic_section_address(base_address)
    i = 0
    while True:
        entry_address = dynamic_section_address + i * DYNAMIC_SECTION_ENTRY_SIZE # size of each dynamic section entry in 64-bit elf
        entry_type = self.read_number(entry_address + DYNAMIC_SECTION_ENTRY_TYPE_OFFSET, UInt64)
        if entry_type == DT_DEBUG:
            r_debug_address = self.read_number(entry_address + DYNAMIC_SECTION_ENTRY_VALUE_OFFSET, UInt64) # value of the DT_DEBUG entry is the address of the r_debug struct
            return r_debug_address
        elif entry_type == DT_NULL: # end of dynamic section entries
            raise Exception("Cannot find DT_DEBUG entry in dynamic section")
        i += 1

def _get_linkmap_address(self, base_address):
    r_debug_address = self._get_r_debug_address(base_address)
    linkmap_address = self.read_number(r_debug_address + R_DEBUG_LINKMAP_OFFSET, UInt64) # address of the linked list of shared objects is at offset 0x18 in the r_debug struct
    return linkmap_address


def _get_shared_objects(self):
    """
    Parse the linker r_debug to get a list of shared objects and their addresses.
    """
    linkmap_address = self._get_linkmap_address(self.base_address)
    shared_objects = []
    while linkmap_address != 0:
        shared_object_base = self.read_number(linkmap_address + LINKMAP_BASE_OFFSET, UInt64)
        shared_object_name_address = self.read_number(linkmap_address + LINKMAP_NAME_OFFSET, UInt64)
        shared_object_name = self.read_c_string(shared_object_name_address)
        # ignore the main executable, which has an empty name, and the VDSO, which isn't a real shared object
        if shared_object_name != b"" and shared_object_name != VDSO_NAME:
            shared_object = SharedObject(shared_object_base, shared_object_name)
            shared_objects.append(shared_object)
        # move to the next link_map struct in the linked list
        linkmap_address = self.read_number(linkmap_address + LINKMAP_NEXT_OFFSET, UInt64) 
    
    return shared_objects
