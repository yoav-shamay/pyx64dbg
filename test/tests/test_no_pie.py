from __future__ import annotations

from pyx64dbg.debugger import Debugger

EXECUTABLE_ADDRESS = "./test/executables/non_pie/test_non_pie"

def test_no_pie_execution():
    """
    Test the execution of a non-PIE binary, and check that we receive the expected output at the end.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.control.continue_execution()
    assert dbg.stdio.recvall() == b"Hello, World!\r\n"

def test_no_pie_base_address():
    """
    Test that the base address of a non-PIE binary is 0x400000, and that the load bias is 0
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    assert dbg.base_address == 0x400000 # the default base address for non-PIE binaries is 0x400000
    assert dbg.load_bias == 0
    dbg.control.kill_process() # kill the process to avoid leaving orphan process

def test_no_pie_breakpoint():
    """
    Test that we can set a breakpoint at the beginning of main in a non-PIE binary.
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
    dbg.control.kill_process() # kill the process once we finished the test to avoid leaving orphan process

def test_no_pie_modification():
    """
    Test that memory modifications work normally.
    This test ensures that the general debugger operations work the same, there's no need to test every single operation.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.breakpoints.add_breakpoint(dbg.shared_objects["libc.so.6"].symbols.puts) # set a breakpoint at puts
    dbg.control.continue_execution()
    dbg.memory.write_bytes(dbg.registers.rdi, b"Modified!\x00") # modify the string argument to puts
    dbg.control.continue_execution()
    assert dbg.stdio.recvall() == b"Modified!\r\n" # check that we received the modified string
