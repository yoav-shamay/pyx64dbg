from __future__ import annotations

from pyx64dbg.debugger import Debugger
from pyx64dbg.number_types import Int64
import signal

EXECUTABLE_ADDRESS = "./test/executables/basic_crackme/test_basic_crackme"
CRACKME_SOL = 687113069

def test_execute_wrong():
    """
    Test the execution of the crackme with wrong input, and check that we receive the "Wrong!" message at the end.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.stdio.sendline("0")
    dbg.control.continue_execution()
    dbg.stdio.recvuntil(b"Enter password: ") # receive prompt
    assert dbg.stdio.recvall() == b"Wrong!\r\n"
    
def test_execute_correct():
    """
    Test the execution of the crackme with correct input, and check that we receive the "Correct!" message at the end.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.stdio.sendline(str(CRACKME_SOL))
    dbg.control.continue_execution()
    dbg.stdio.recvuntil(b"Enter password: ") # receive prompt
    assert dbg.stdio.recvall() == b"Correct!\r\n"

def test_breakpoint():
    """
    Test that we can set a breakpoint at the beginning of main.
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
    # set and remove a breakpoint to see that it functions normally (at printf, which should be called in the beginning)
    dbg.breakpoints.add_breakpoint(dbg.shared_objects["libc.so.6"].symbols.printf)
    dbg.breakpoints.remove_breakpoint(dbg.shared_objects["libc.so.6"].symbols.printf)
    dbg.stdio.sendline("1234")
    dbg.control.continue_execution()
    dbg.stdio.recvuntil(b"Enter password: ") # receive prompt
    assert dbg.stdio.recvall() == b"Wrong!\r\n" # check that we received the "Wrong!" message, indicating the process run normally

def test_next():
    """
    Test the operation of the next movement command, which should step over function calls.
    We set a breakpoint right before a call to printf, and then use next to step over it.
    Checks that printf is actually executed and that the RIP is correct after stepping over.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x44) # breakpoint right before the call to printf
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x44
    dbg.control.next() # step over the call to printf, which is the next instruction, and
    assert dbg.registers.rip == main + 0x49 # address of the next instruction
    assert dbg.stdio.recvall() == b"Enter password: " # check that we received the prompt, this means printf has executed
    dbg.control.kill_process() # kill the process once we finished the test to avoid leaving orphan process

def test_single_step():
    """
    Tests the operation of the single step movement command, which should step into function calls.
    We set a breakpoint right before a call to printf, and then use single step to step into it.
    Checks that we are actually in the printf function and that the RIP is correct after stepping in.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x44) # breakpoint right before the call to printf
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x44
    dbg.control.single_step() # step into the call to printf, which is the next instruction, and should take us into the plt stub for printf
    assert dbg.registers.rip == dbg.symbols.printf_plt # we should be at the printf plt stub
    dbg.control.kill_process()

def test_memory_read_write_number():
    """
    Tests reading and writing numbers to memory in the debugged process.
    We set a breakpoint right after a call to scanf, which reads input into a stack variable.
    We then read the value that was read by scanf, check that it's correct, write a new value to that memory location, and check that the new value is correct.
    We change the value to be the correct password, and we continue to check that we get the "Correct!" message.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x64) # breakpoint right after the call to scanf
    dbg.stdio.sendline("123\n") # send input for scanf, which will be read into a stack variable
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x64
    # get the read number
    read_num_address = dbg.registers.rbp - 0x10
    read_num = dbg.memory.read_number(read_num_address, Int64)
    assert read_num == 123
    assert dbg.memory[read_num_address:read_num_address+8] == Int64(123).to_bytes() # test byte reading as well
    # write a new number and check it
    dbg.memory.write_number(read_num_address, CRACKME_SOL, 8)
    read_num_after_write = dbg.memory.read_number(read_num_address, Int64)
    assert read_num_after_write == CRACKME_SOL
    dbg.control.continue_execution()
    dbg.stdio.recvuntil(b"Enter password: ") # receive prompt
    assert dbg.stdio.recvall() == b"Correct!\r\n" # check that the modified number was used and we received the correct answer

def test_stack_frame():
    """
    Tests the stack frame functionality of the debugger.
    We stop inside the libc puts function which is called in the end.
    We check the saved_rip and the saved_rbp of the current frame, and the rbp of the next frame.
    We also check reading memory from the stack using the previous frame, and check that it contains the expected value.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0xe1) # breakpoint right before the call to puts on correct
    dbg.stdio.sendline(str(CRACKME_SOL)) # send correct input for scanf, which will be read into a stack variable
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0xe1
    # continue until reaching puts itself
    dbg.breakpoints.add_breakpoint(dbg.shared_objects["libc.so.6"].symbols.puts)
    dbg.control.continue_execution()
    # step three times to skip prologue - endbr64 ; push rbp; mov rbp, rsp
    dbg.control.single_step()
    dbg.control.single_step()
    dbg.control.single_step()
    current_frame = dbg.stack.current_frame()
    assert current_frame.saved_rip == main + 0xe6 # right after the call to puts
    cur_rbp = current_frame.rbp
    saved_rbp = current_frame.saved_rbp
    assert cur_rbp == saved_rbp - 0x30 # expected difference - main is 0x20, and 0x10 for saved rbp and return address
    next_frame = dbg.stack[1]
    assert next_frame.rbp == saved_rbp
    assert next_frame.rbp - next_frame.rsp == 0x20 # test expected difference between rbp and rsp in main
    assert next_frame[-0x10:-0x8] == 0x1337.to_bytes(8, byteorder="little") # result should be 0x1337 after the computations
    dbg.control.kill_process()

def test_register_write():
    """
    Tests writing to registers in the debugged process.
    We set a breakpoint right before a cmp instruction that compares the computed value to the correct password.
    We then modify the value in rax to be the correct password.
    We test that further .rax reads show the modified value, and we continue execution to check that we get the "Correct!" message.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0xcf) # breakpoint right before the cmp
    dbg.stdio.sendline(b"0") # send wrong input
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0xcf
    dbg.registers.rax = 0x1337
    assert dbg.registers.rax == 0x1337
    dbg.control.continue_execution()
    dbg.stdio.recvuntil(b"Enter password: ") # receive prompt
    assert dbg.stdio.recvall() == b"Correct!\r\n" # check that modifying rax caused the cmp to succeed and we received the correct answer

def test_finish():
    """
    Tests the finish movement command, which should step out of the current function.
    We set a breakpoint right before a call to printf, and then use finish to step out of the current function.
    We check that it indeed prints the prompt and that the rip in the end is correct.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    printf = dbg.shared_objects["libc.so.6"].symbols.printf
    dbg.breakpoints.add_breakpoint(printf) # breakpoint at the libc printf function
    dbg.control.continue_execution()
    assert dbg.registers.rip == printf
    # step 4 times to get past the prologue of the function (printf has 4 instructions in its prologue)
    dbg.control.single_step()
    dbg.control.single_step()
    dbg.control.single_step()
    dbg.control.single_step()
    dbg.control.finish() # step out of printf
    assert dbg.registers.rip == main + 0x49 # right after printf
    assert dbg.stdio.recvall() == b"Enter password: " # check that we received the prompt which means printf ran
    dbg.control.kill_process()   

def test_signal_passing():
    """
    Test that we intercept when the process is stopped by a signal and can pass it to the process to continue execution.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.registers.rip = 0 # trigger an error and cause a SIGSEGV
    dbg.control.single_step() # single step to trigger the signal
    assert dbg.stopped_signal == signal.SIGSEGV
    dbg.control.single_step() # pass the signal and single step again
    assert dbg.process_exited # assert that the process exited after passing the signal to the process
    assert dbg.error_signal == signal.SIGSEGV # assert that the exit signal is the signal we triggered
    assert dbg.exit_code == -signal.SIGSEGV # assert that the exit code is -signal number, which is the python convention for exit codes on signals

def test_signal_surpassion():
    """
    Test that we can intercept and surpass a signal passed to the process.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.registers.rip = 0 # trigger an error and cause a SIGSEGV
    dbg.control.single_step() # single step to trigger the signal
    assert dbg.stopped_signal == signal.SIGSEGV
    dbg.control.surpass_signal() # surpass the signal
    assert not dbg.stopped_signal # assert that we are no longer stopped on the signal
    dbg.registers.rip = dbg.entry_address # return the process to normal execution
    dbg.stdio.sendline("1234")
    dbg.control.continue_execution() # continue execution to the end
    dbg.stdio.recvuntil(b"Enter password: ") # receive prompt
    assert dbg.stdio.recvall() == b"Wrong!\r\n" # check that we received the "Wrong!" message, indicating the process run normally

def test_base_address():
    """
    Test that the reported base address and load bias of the debugged process are correct.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main_offset = 0x1179 # offset of main in the binary, obtained from readelf manually
    assert dbg.base_address + main_offset == dbg.symbols["main"] # check that the base address plus the offset of main equals the address of main, verifying the base address is correct
    assert dbg.load_bias == dbg.base_address # verify that load bias equals the base address, the behavior fro PIE binaries
    dbg.control.kill_process() # kill the process to avoid leaving orphan process

def test_existing_breakpoints():
    """
    Test that existing breakpoints (CC instructions) in the debugged process aren't confused with the breakpoints set by the debugger.
    """
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main)
    dbg.memory[main] = 0xCC # write a CC instruction at the address of main, simulating an existing breakpoint instruction
    dbg.control.continue_execution() # we should hit the breakpoint of the debugger, not the one we manually wrote
    assert dbg.registers.rip == main
    assert dbg.stopped_signal == None # no stopped signal, the breakpoint we manually set isn't triggered yet
    dbg.control.single_step() # single step, we should hit the breakpoint we just wrote
    assert dbg.registers.rip == main + 1 # Check that rip was actually incremented, meaning this instruction actually executed
    assert dbg.stopped_signal == signal.SIGTRAP # check that we actually stopped on a trap signal
    dbg.control.surpass_signal() # surpass the signal to continue execution
    dbg.memory[main + 1] = 0xCC # try to write a breakpoint on an address that we don't set a breakpoint on
    dbg.control.continue_execution() # continue execution, we should hit the breakpoint we just wrote
    assert dbg.registers.rip == main + 2 # Check that rip was actually incremented
    assert dbg.stopped_signal == signal.SIGTRAP # check that we actually stopped on a trap signal
    dbg.control.kill_process() # kill the process to avoid leaving orphan process