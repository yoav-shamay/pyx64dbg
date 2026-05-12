from pyx64dbg.debugger import Debugger
from pyx64dbg.number_types import Int64

EXECUTABLE_ADDRESS = "./test/executables/basic_crackme/test_basic_crackme"
CRACKME_SOL = 687113069

def test_execute_wrong():
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.stdio.sendline("0")
    dbg.control.continue_execution()
    dbg.stdio.recvuntil(b"Enter password: ") # receive prompt
    assert dbg.stdio.recvall() == b"Wrong!\r\n"
    
def test_execute_correct():
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    dbg.stdio.sendline(str(CRACKME_SOL))
    dbg.control.continue_execution()
    dbg.stdio.recvuntil(b"Enter password: ") # receive prompt
    assert dbg.stdio.recvall() == b"Correct!\r\n"

def test_breakpoint():
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main)
    assert dbg.breakpoints.get_breakpoints() == {main}
    dbg.control.continue_execution()
    assert dbg.registers.rip == main
    dbg.breakpoints.remove_breakpoint(main)
    assert dbg.breakpoints.get_breakpoints() == set()

def test_next():
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
    dbg = Debugger.start_and_debug(EXECUTABLE_ADDRESS)
    main = dbg.symbols["main"]
    dbg.breakpoints.add_breakpoint(main + 0x44) # breakpoint right before the call to printf
    dbg.control.continue_execution()
    assert dbg.registers.rip == main + 0x44
    dbg.control.single_step() # step into the call to printf, which is the next instruction, and should take us into the plt stub for printf
    assert dbg.registers.rip == dbg.symbols.printf_plt # we should be at the printf plt stub
    dbg.control.kill_process()

def test_memory_read_write():
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
    # write a new number and check it
    dbg.memory.write_number(read_num_address, CRACKME_SOL, 8)
    read_num_after_write = dbg.memory.read_number(read_num_address, Int64)
    assert read_num_after_write == CRACKME_SOL
    dbg.control.continue_execution()
    dbg.stdio.recvuntil(b"Enter password: ") # receive prompt
    assert dbg.stdio.recvall() == b"Correct!\r\n" # check that the modified number was used and we received the correct answer

def test_stack_frame():
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