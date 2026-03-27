import ptrace
import os
from capstone import CS_GRP_CALL
import signal

def _handle_signal(self, status, stepped=False):
    if os.WIFEXITED(status):
        pass # TODO handle exit, maybe setting a flag and printing in interactive mode
    elif os.WIFSTOPPED(status):
        self.registers._refresh_registers() # refresh registers after movement
        triggered_signal = os.WSTOPSIG(status)
        if triggered_signal == signal.SIGTRAP:
            if not stepped: # if we just continued, we have hit a breakpoint
                self.registers.rip -= 1 #  so move the instruction pointer back to point to the breakpoint instruction
        elif triggered_signal != signal.SIGTRAP:
            pass # TODO handle other signals, setting a flag and maybe printing a message in interactive mode
    else:
        raise Exception("Unexpected status after ptrace movement: " + str(status))


def single_step(self):
    rip = int(self.registers["rip"])
    if rip in self.breakpoints.get_breakpoints():
        self.breakpoints.step_from_breakpoint(rip)
    else:
        ptrace.single_step(self.child_pid)
    _, status = os.wait() # wait for child to raise a signal, which can be from hitting a breakpoint or exiting
    self._handle_signal(status, stepped=True)

def continue_execution(self):
    rip = int(self.registers["rip"])
    if rip in self.breakpoints.get_breakpoints():
        self.breakpoints.step_from_breakpoint(rip)
    ptrace.cont(self.child_pid)
    _, status = os.wait() # wait for child to raise a signal, which can be from hitting a breakpoint or exiting
    self._handle_signal(status)

def next(self):
    rip = int(self.registers["rip"])
    cur_instruction = self.memory.read_instruction(rip)
    if CS_GRP_CALL in cur_instruction.groups:
        # if the instruction is a call, set a temporary breakpoint on the next instruction and continue until hitting it (or other breakpoints)
        next_instruction_address = cur_instruction.address + cur_instruction.size
        if next_instruction_address in self.breakpoints.get_breakpoints():
            # if there is already a breakpoint on the next instruction, skip adding the temporary breakpoint
            self.continue_execution()
            return
        self.breakpoints.add_breakpoint(next_instruction_address)
        self.continue_execution()
        self.breakpoints.remove_breakpoint(next_instruction_address)
    else:
        # if the instruction isn't a call, just single step
        self.single_step()


def finish(self):
    # TODO implement finish, which steps out of the current function
    pass