from __future__ import annotations

from pyx64dbg.debugger import Debugger

EXECUTABLE_ADDRESS = "./test/executables/static_linked/test_static_linked"

def test_static_linked_execution():
    """
    Test the execution of a statically linked binary, and check that we receive the expected output at the end.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.control.continue_execution()
    assert dbg.stdio.recvall() == b"Hello, World!\r\n"

def test_static_linked_breakpoint():
    """
    Test that we can set a breakpoint at the beginning of main in a statically linked binary.
    Ensures the rip after stopping is correct, and that it appears in the breakpoint set.
    Also checks that removing this breakpoint works and it no longer appears in the breakpoint set.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main)
    assert dbg.breakpoints.get_breakpoints() == {main}
    dbg.control.continue_execution()
    assert dbg.registers.rip == main
    dbg.breakpoints.remove_breakpoint(main)
    assert dbg.breakpoints.get_breakpoints() == set()
    dbg.control.kill_process() # kill the process to avoid leaving orphan process

def test_static_linked_shared_objects_and_ld_base():
    """
    Test that the shared objects dictionary is empty for a statically linked binary, as it doesn't have shared objects.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    assert dbg.shared_objects == {} # for a statically linked binary, there are no shared objects, so the dictionary should be empty
    assert dbg.ld_base == None # verify that there's no linker
    dbg.control.kill_process() # kill the process to avoid leaving orphan process

def test_static_linked_modification():
    """
    Test that memory modifications work normally in a statically linked binary.
    This test ensures that the general debugger operations work the same, there's no need to test every single operation.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.breakpoints.add_breakpoint(dbg.symbols["puts"]) # set a breakpoint at puts
    dbg.control.continue_execution()
    dbg.memory.write_bytes(dbg.registers.rdi, b"Modified!\x00") # modify the string argument to puts
    dbg.control.continue_execution()
    assert dbg.stdio.recvall() == b"Modified!\r\n" # check that we received the modified string