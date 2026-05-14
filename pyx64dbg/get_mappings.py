"""
Utility functions for obtaining offsets for the executable and linked shared objects.
Used for PIE and ASLR support, and for getting the loaded shared objects and their addresses.
Obtained by parsing the auxiliary vector, program headers, dynamic section and linker r_debug struct of the debugged process.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from pyx64dbg.number_types import UInt16, UInt32, UInt64
from pyx64dbg.shared_object import SharedObject

if TYPE_CHECKING:
    from pyx64dbg.debugger import Debugger

# constants for various offsets and sizes used in parsing the auxiliary vector, program headers, dynamic section, r_debug struct and link_map struct to get the shared objects and their addresses.
AUXV_ENTRY_SIZE = 16
AUXV_ENTRY_TYPE_OFFSET = 0
AUXV_ENTRY_TYPE_SIZE = 8
AUXV_ENTRY_VALUE_OFFSET = 8
AUXV_ENTRY_VALUE_SIZE = 8

AT_ENTRY = UInt64(9)
AT_BASE = UInt64(7)

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

VDSO_NAME = "linux-vdso.so.1"


def get_auxv(child_pid: int) -> dict[UInt64, UInt64]:
    """
    A helper method to get the auxiliary vector of the debugged process.
    Reads it from /proc/<pid>/auxv and parses it into a dictionary mapping from entry types to entry values.
    """
    # read /proc/<pid>/auxv
    file_path = f"/proc/{child_pid}/auxv"
    with open(file_path, "rb") as f:
        auxv_content = f.read()
    # parse it to a dictionary
    auxv: dict[UInt64, UInt64] = {}
    for i in range(0, len(auxv_content), AUXV_ENTRY_SIZE):
        entry_type_bytes = auxv_content[
            i
            + AUXV_ENTRY_TYPE_OFFSET : i
            + AUXV_ENTRY_TYPE_OFFSET
            + AUXV_ENTRY_TYPE_SIZE
        ]
        entry_value_bytes = auxv_content[
            i
            + AUXV_ENTRY_VALUE_OFFSET : i
            + AUXV_ENTRY_VALUE_OFFSET
            + AUXV_ENTRY_VALUE_SIZE
        ]
        # parse both as UInt64, as they are 8-byte numbers.
        entry_type = UInt64.from_bytes(entry_type_bytes)
        entry_value = UInt64.from_bytes(entry_value_bytes)
        auxv[entry_type] = entry_value
    return auxv

def get_entry_address(auxv: dict[UInt64, UInt64]) -> UInt64:
    """
    A helper method to get the entry point address of the debugged process from its auxiliary vector.
    Reads the AT_ENTRY entry from the auxiliary vector, which gives the offset of the entry point from the base address.
    """
    return auxv[AT_ENTRY]

def get_ld_base(auxv: dict[UInt64, UInt64]) -> UInt64 | None:
    """
    A helper method to get the ld base of the executable in the debugged process from its auxiliary vector.
    Reads the AT_BASE entry from the auxiliary vector.
    Returns None for static-linked binaries, as they don't have a ld.
    """
    if AT_BASE in auxv and auxv[AT_BASE] != 0: # if the entry isn't present or zero, it's a static-linked binary
        return auxv[AT_BASE]
    else:
        return None

def _get_program_header_address(debugger: Debugger) -> UInt64:
    """
    Returns the address of the program header table of the main executable in its virtual address space.
    Requires the debugger object with initialized base address.
    Reads it from the E_PHOFF field in the ELF header (which is at a fixed offset from the base address)
    """
    e_phoff_address = (
        debugger.base_address + E_PHOFF_OFFSET
    )  # program header table address in the elf header
    e_phoff_value = debugger.memory.read_number(e_phoff_address, UInt64)
    # as e_phoff value is always an offset, even for non-PIE binaries, we use the base address
    return e_phoff_value + debugger.base_address


def _get_program_header_entry_count(debugger: Debugger) -> int:
    """
    Returns the number of entries in the program header table of the main executable.
    Requires the debugger object with initialized base address.
    Reads it from the E_PHNUM field in the ELF header (which is at a fixed offset from the base address)
    """
    e_phnum_address = (
        debugger.base_address + E_PHNUM_OFFSET
    )  # number of program headers in the elf header
    e_phnum_value = debugger.memory.read_number(e_phnum_address, UInt16)
    return int(e_phnum_value)


def _get_dynamic_section_address(debugger: Debugger) -> UInt64:
    """
    Returns the address of the dynamic section of the main executable in its virtual address space.
    Requires the debugger object with initialized base address.
    To find it, we to parse the program headers and find the one with type PT_DYNAMIC.
    Then we read the offset of the dynamic section from this entry.
    Raises an exception if it fails to find a program header with type PT_DYNAMIC (shouldn't happen in a properly running process).
    """
    # get the program header address and entry count from the previous helper functions
    program_header_address = _get_program_header_address(debugger)
    program_header_entry_count = _get_program_header_entry_count(debugger)
    # loop over each entry in the program header table
    for i in range(program_header_entry_count):
        entry_address = program_header_address + i * PROGRAM_HEADER_ENTRY_SIZE
        entry_type = debugger.memory.read_number(
            entry_address + PROGRAM_HEADER_ENTRY_TYPE_OFFSET, UInt32
        )
        if entry_type == PT_DYNAMIC:
            # PT_DYNAMIC entry, its value is the offset of the dynamic section.
            dynamic_section_address = debugger.memory.read_number(
                entry_address + PROGRAM_HEADER_ENTRY_VALUE_OFFSET, UInt64
            )  # offset of the dynamic section in the elf header
            # add it to the load bias to obtain the absolute address (as it's already absolute for non-PIE binaries)
            return dynamic_section_address + debugger.load_bias
    raise RuntimeError("Cannot find dynamic section in program headers")


def _get_r_debug_address(debugger: Debugger) -> UInt64:
    """
    Returns the address of the r_debug struct used by the linker to store information about the loaded shared objects.
    Requires the debugger object with initialized base address.
    To find it, we first get the address of the dynamic section using the previous helper function.
    Then we loop over the entries in the dynamic section until we find the one with type DT_DEBUG.
    The value of this entry is the address of the r_debug struct.
    Raises an exception if it fails to find a DT_DEBUG entry in the dynamic section (shouldn't happen in a properly running process).
    """
    dynamic_section_address = _get_dynamic_section_address(debugger)
    # loop over entries until reaching DT_DEBUG or DT_NULL (end of entries)
    cur_entry_address = dynamic_section_address
    while True:
        entry_type = debugger.memory.read_number(
            cur_entry_address + DYNAMIC_SECTION_ENTRY_TYPE_OFFSET, UInt64
        )
        if entry_type == DT_DEBUG:
            r_debug_address = debugger.memory.read_number(
                cur_entry_address + DYNAMIC_SECTION_ENTRY_VALUE_OFFSET, UInt64
            )  # value of the DT_DEBUG entry is the address of the r_debug struct (absolute)
            return r_debug_address
        elif entry_type == DT_NULL:  # end of dynamic section entries
            raise RuntimeError("Cannot find DT_DEBUG entry in dynamic section")
        cur_entry_address += DYNAMIC_SECTION_ENTRY_SIZE  # move to the next entry


def _get_linkmap_address(debugger: Debugger) -> UInt64:
    """
    Returns the address of the link_map struct, which is the head of a linked list of loaded shared objects used by the linker.
    Requires the debugger object with initialized base address.
    To find it, we first get the address of the r_debug struct using the previous helper function.
    Then we read the address of the link_map struct from the r_debug struct, which is at a fixed offset in the struct.
    """
    r_debug_address = _get_r_debug_address(debugger)
    linkmap_address = debugger.memory.read_number(
        r_debug_address + R_DEBUG_LINKMAP_OFFSET, UInt64
    )  # address of the linked list of shared objects is at offset 0x18 in the r_debug struct
    return linkmap_address


def get_shared_objects(debugger: Debugger) -> list[SharedObject]:
    """
    Returns a list of shared objects loaded in the debugged process.
    Requires the debugger object with initialized base address.
    Returns a list of SharedObject instances.
    To do this, we first get the address of the link_map struct using the previous helper function.
    Then we loop over the linked list of link_map structs, where each struct represents a loaded shared object.
    We read the name and base address of each shared object from the struct.
    We skip the main executable and VDSO (as they aren't real shared objects).
    """
    linkmap_address = _get_linkmap_address(debugger)
    shared_objects: list[SharedObject] = []
    # the end of the linked list is indicated by a null pointer
    while (linkmap_address != 0):
        shared_object_base = debugger.memory.read_number(
            linkmap_address + LINKMAP_BASE_OFFSET, UInt64
        )
        shared_object_name_address = debugger.memory.read_number(
            linkmap_address + LINKMAP_NAME_OFFSET, UInt64
        )
        shared_object_name = debugger.memory.read_c_string(
            shared_object_name_address
        ).decode()
        # ignore the main executable, which has an empty name, and the VDSO, which isn't a real shared object
        if shared_object_name != "" and shared_object_name != VDSO_NAME:
            shared_object = SharedObject(shared_object_base, shared_object_name)
            shared_objects.append(shared_object)
        # move to the next link_map struct in the linked list
        linkmap_address = debugger.memory.read_number(
            linkmap_address + LINKMAP_NEXT_OFFSET, UInt64
        )

    return shared_objects
