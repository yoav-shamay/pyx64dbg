from __future__ import annotations

from pyx64dbg.debugger import Debugger

EXECUTABLE_ADDRESS = "./test/executables/extended_registers/test_extended_registers"

def test_read_ymm():
    """
    Tests reading ymm registers in the debugged process.
    We stop at various points in the program where ymm0 is modified (when the values are loaded and when they are added).
    Each time, we check that the values are correct.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x6a) # breakpoint right before the first assignment to ymm0
    dbg.stdio.sendline("0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15") # send numbers 0-15 as input
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x6a
    dbg.control.single_step() # assignment to ymm0
    # check if ymm0 contains the first 8 numbers (0-7)
    assert dbg.registers.ymm0.i32 == [0, 1, 2, 3, 4, 5, 6, 7]
    dbg.control.single_step() # addition
    # check if ymm0 now contains the sums of the first 8 numbers and the last 8 numbers (0+8, 1+9, ..., 7+15)
    assert dbg.registers.ymm0.i32 == [8, 10, 12, 14, 16, 18, 20, 22]
    dbg.control.kill_process()

def test_write_ymm():
    """
    Tests writing to ymm registers in the debugged process.
    We set a breakpoint right before the first assignment to ymm0, send input, and then modify the value in ymm0.
    We check that the modified value is correctly written and that further reads show the same value.
    We also check that the values the program prints at the end are based on the modified values in ymm0.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x6a) # breakpoint right before the first assignment to ymm0
    dbg.stdio.sendline("0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15") # send numbers 0-15 as input
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x6a
    dbg.control.single_step() # assignment to ymm0
    # overwrite ymm0 with the numbers 16-23
    dbg.registers.ymm0.i32 = [16, 17, 18, 19, 20, 21, 22, 23]
    # check that ymm0 contains the new values
    assert dbg.registers.ymm0.i32 == [16, 17, 18, 19, 20, 21, 22, 23]
    dbg.control.single_step() # addition, which should now add the last 8 numbers (8-15) to the new values in ymm0 (16-23)
    # check if ymm0 now contains the sums of the new values in ymm0 and the last 8 numbers (16+8, 17+9, ..., 23+15)
    assert dbg.registers.ymm0.i32 == [24, 26, 28, 30, 32, 34, 36, 38]
    dbg.control.continue_execution() # continue execution to the end
    # receive the results printed at the end, which should be the new values in ymm0 after the addition (24-38)
    res = dbg.stdio.recvline().strip()
    assert res == b"24 26 28 30 32 34 36 38" # check that the output is the sum based on the new values