import pyx64dbg.ptrace as ptrace
import os
from capstone import CS_GRP_CALL
import signal
from pyx64dbg.cint import CInt
from pyx64dbg.utils import change_first_byte


def _handle_signal(self, status, stepped=False):
    if os.WIFEXITED(status):
        self.process_exited = True
        self.exit_code = os.WEXITSTATUS(status)
        self.error_signal = None
        self.stopped_signal = None
        if self.exit_callback is not None:
            self.exit_callback()
    elif os.WIFSIGNALED(status):
        self.process_exited = True
        self.exit_code = None
        self.error_signal = os.WTERMSIG(status)
        self.stopped_signal = None
        if self.exit_callback is not None:
            self.exit_callback()
    elif os.WIFSTOPPED(status):
        # if the process was stopped by a signal, only SIGTRAP is treated as a stepping/breakpoint stop
        self.registers._refresh_registers() # refresh registers after movement
        triggered_signal = os.WSTOPSIG(status)
        if triggered_signal == signal.SIGTRAP:
            self.stopped_signal = None
            if not stepped: # if we just continued, we have hit a breakpoint
                self.registers.rip -= 1 #  so move the instruction pointer back to point to the breakpoint instruction
        else:
            self.stopped_signal = triggered_signal
            if self.stop_callback is not None:
                self.stop_callback()
    else:
        raise Exception("Unexpected status after ptrace movement: " + str(status))
    
    
def _step_from_breakpoint(self, address : CInt | int):
    address = int(address) # convert to int if it's a CInt
    original_byte = self.breakpoints.original_bytes[address]
    breakpoint_word = ptrace.peekdata(self.child_pid, address)
    non_breakpoint_word = change_first_byte(breakpoint_word, original_byte)
    ptrace.pokedata(self.child_pid, address, non_breakpoint_word)
    if self.stopped_signal is not None:
        # if we are currently stopped by a signal, we need to pass it to ptrace to continue execution, otherwise the process will just be stopped again by the same signal without executing any instructions
        ptrace.single_step(self.child_pid, signal=self.stopped_signal)
        self.stopped_signal = None
    else:
        ptrace.single_step(self.child_pid)
    _, status = os.wait() # wait for child to raise a signal, which should be from single stepping
    self._handle_signal(status, stepped=True)
    if self.process_exited:
        # if the process exited while we were stepping from the breakpoint, we shouldn't try to restore the breakpoint, as it will cause an error
        return
    ptrace.pokedata(self.child_pid, address, breakpoint_word)


def single_step(self):
    """
    Steps a single instruction.
    """
    self._ensure_running()
    rip = int(self.registers["rip"])
    if rip in self.breakpoints.get_breakpoints():
        self._step_from_breakpoint(rip)
    else:
        if self.stopped_signal is not None:
            # if we are currently stopped by a signal, we need to pass it to ptrace to continue execution, otherwise the process will just be stopped again by the same signal without executing any instructions
            ptrace.single_step(self.child_pid, signal=self.stopped_signal)
            self.stopped_signal = None
        else:
            ptrace.single_step(self.child_pid)
        _, status = os.wait() # wait for child to raise a signal, which can be from hitting a breakpoint or exiting
        self._handle_signal(status, stepped=True)
    self._on_update()

def continue_execution(self):
    """
    Continues execution until the next breakpoint or exit.
    """
    self._ensure_running()
    rip = int(self.registers["rip"])
    if rip in self.breakpoints.get_breakpoints():
        self._step_from_breakpoint(rip)
        if self.stopped_signal is not None or self.process_exited:
            # if we are currently stopped by a signal or the process exited, we shouldn't continue execution, as the process is already stopped/exited, and continuing would cause an error
            self._on_update()
            return
    if self.stopped_signal is not None:
        # if we are currently stopped by a signal, we need to pass it to ptrace to continue execution, otherwise the process will just be stopped again by the same signal without executing any instructions
        ptrace.cont(self.child_pid, signal=self.stopped_signal)
        self.stopped_signal = None
    else:
        ptrace.cont(self.child_pid)
    _, status = os.wait() # wait for child to raise a signal, which can be from hitting a breakpoint or exiting
    self._handle_signal(status)
    self._on_update()

def next(self):
    """
    Steps over to the next instruction, stepping over function calls.
    """
    self._ensure_running()
    rip = int(self.registers["rip"])
    cur_instruction = self.read_instruction(rip)
    if CS_GRP_CALL in cur_instruction.groups:
        # if the instruction is a call, set a temporary breakpoint on the next instruction and continue until hitting it (or other breakpoints)
        next_instruction_address = cur_instruction.address + cur_instruction.size
        if next_instruction_address in self.breakpoints.get_breakpoints():
            # if there is already a breakpoint on the next instruction, skip adding the temporary breakpoint
            self.continue_execution()
            return
        self.breakpoints.add_breakpoint(next_instruction_address)
        self.continue_execution()
        if self.process_exited:
            # if the process exited while we were stepping over, we shouldn't try to remove the breakpoint, as it will cause an error
            return
        self.breakpoints.remove_breakpoint(next_instruction_address)
    else:
        # if the instruction isn't a call, just single step
        self.single_step()


def finish(self):
    """
    Steps out of the current function.
    """
    self._ensure_running()
    current_frame = self.stack.current_frame()
    return_address = int(current_frame.saved_rip)
    if return_address in self.breakpoints.get_breakpoints():
        # if there is already a breakpoint on the return address, skip adding the temporary breakpoint
        self.continue_execution()
        return
    self.breakpoints.add_breakpoint(return_address)
    self.continue_execution()
    if self.process_exited:
        # if the process exited while we were stepping out, we shouldn't try to remove the breakpoint, as it will cause an error
        return
    self.breakpoints.remove_breakpoint(return_address)