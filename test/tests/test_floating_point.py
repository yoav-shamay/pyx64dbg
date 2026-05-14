from __future__ import annotations

from pyx64dbg.debugger import Debugger
import pytest
from pyx64dbg.number_types import Float32, Float64, Float80

EXECUTABLE_ADDRESS = "./test/executables/floating_point/test_fp"


def test_xmm_floating_point_reading():
    """
    Tests reading floating point values in xmm registers in the debugged process.
    We stop at various points in the program where xmm0 and xmm1 are modified (when the values are loaded and when they are added).
    Each time, we check that the values are correct.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x74) # breakpoint right before the first assignment to xmm1
    dbg.stdio.sendline("0.1 0.2")
    dbg.stdio.sendline("0.3 0.4")
    dbg.stdio.sendline("0.5 0.6")
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x74
    dbg.control.single_step() # assignment to xmm1
    assert float(dbg.registers.xmm1.sf32) == pytest.approx(0.1)
    dbg.control.single_step() # assignment to xmm0
    assert float(dbg.registers.xmm0.sf32) == pytest.approx(0.2)
    dbg.control.single_step() # addition
    assert float(dbg.registers.xmm0.sf32) == pytest.approx(0.3)
    dbg.control.single_step() # saving to memory
    assert float(dbg.memory.read_number(dbg.registers.rbp - 0x5c, Float32)) == pytest.approx(0.3)
    dbg.control.single_step() # assignment to xmm1
    assert float(dbg.registers.xmm1.sf64) == pytest.approx(0.3)
    dbg.control.single_step() # assignment to xmm0
    assert float(dbg.registers.xmm0.sf64) == pytest.approx(0.4)
    dbg.control.single_step() # addition
    assert float(dbg.registers.xmm0.sf64) == pytest.approx(0.7)
    dbg.control.single_step() # saving to memory
    assert float(dbg.memory.read_number(dbg.registers.rbp - 0x48, Float64)) == pytest.approx(0.7) 
    dbg.control.kill_process()   

def test_xmm_floating_point_saving():
    """
    Tests writing to xmm registers in the debugged process.
    We stop before assignment to xmm1 at various points, and modify the value.
    We then check that the modified value is correctly written and that further reads show the same value.
    We also check the final results printed at the end, which should be based on the modified values in xmm0 and xmm1.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x74) # breakpoint right before the first assignment to xmm1
    dbg.stdio.sendline("0.1 0.2")
    dbg.stdio.sendline("0.3 0.4")
    dbg.stdio.sendline("0.5 0.6")
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x74
    dbg.control.single_step() # assignment to xmm1
    dbg.registers.xmm1.sf32 = 0.2 # overwrite xmm1 to 0.2, see if the result changes
    assert float(dbg.registers.xmm1.sf32) == pytest.approx(0.2)
    dbg.control.single_step() # assignment to xmm0
    dbg.control.single_step() # addition
    dbg.control.single_step() # saving to memory
    dbg.control.single_step() # assignment to xmm1
    dbg.registers.xmm1.sf64 = 0.4 # overwrite xmm1 to 0.4, see if the result changes
    assert float(dbg.registers.xmm1.sf64) == pytest.approx(0.4)
    dbg.control.continue_execution() # continue execution to the end
    dbg.stdio.recvuntil(b"=") # receive until the equals sign, then read the result
    res1 = float(dbg.stdio.recvline().strip())
    dbg.stdio.recvuntil(b"=")
    res2 = float(dbg.stdio.recvline().strip())
    assert res1 == pytest.approx(0.4)
    assert res2 == pytest.approx(0.8)

def test_st_floating_point_reading():
    """
    Tests reading floating point values in st registers in the debugged process.
    We stop at various points in the program where st0/st1 are modified (when the values are pushed to the stack and added).
    Each time, we check that the values are correct.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x9a) # breakpoint right before the first assignment to st0
    dbg.stdio.sendline("0.1 0.2")
    dbg.stdio.sendline("0.3 0.4")
    dbg.stdio.sendline("0.5 0.6")
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x9a
    dbg.control.single_step() # assignment to st0
    assert float(dbg.registers.st0) == pytest.approx(0.5)
    dbg.control.single_step() # insertion of the next operand
    assert float(dbg.registers.st0) == pytest.approx(0.6)
    assert float(dbg.registers.st1) == pytest.approx(0.5)
    dbg.control.single_step() # addition
    assert float(dbg.registers.st0) == pytest.approx(1.1)
    dbg.control.single_step() # saving to memory
    assert float(dbg.memory.read_number(dbg.registers.rbp - 0x20, Float80)) == pytest.approx(1.1)
    dbg.control.kill_process()   

def test_st_floating_point_saving():
    """
    Tests writing to st registers in the debugged process.
    We set a breakpoint right before the first assignment to st0, send input, and then modify the value in st0.
    We check that the modified value is correctly written and that further reads show the same value.
    We also check that the values the program prints at the end are based on the modified values in st0.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x9a) # breakpoint right before the first assignment to st0
    dbg.stdio.sendline("0.1 0.2")
    dbg.stdio.sendline("0.3 0.4")
    dbg.stdio.sendline("0.5 0.6")
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x9a
    dbg.control.single_step() # assignment to st0
    dbg.registers.st0 = 0.6 # overwrite st0 to 0.6, see if the result changes
    assert float(dbg.registers.st0) == pytest.approx(0.6)
    dbg.control.single_step() # insertion of the next operand
    dbg.control.single_step() # addition
    dbg.control.single_step() # saving to memory
    dbg.control.continue_execution() # continue execution to the end
    # skip the lines with the first 2 results
    dbg.stdio.recvline()
    dbg.stdio.recvline()
    dbg.stdio.recvuntil(b"=") # receive until the equals sign, then read the result
    res = float(dbg.stdio.recvline().strip())
    assert res == pytest.approx(1.2)