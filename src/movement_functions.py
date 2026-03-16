import ptrace
import os

def step(self):
    rip = self.registers["rip"]
    if rip in self.breakpoints.get_breakpoints():
        self.breakpoints.step_from_breakpoint(rip)
    else:
        ptrace.single_step(self.child_pid)
    os.wait() # wait for child to raise a signal, which can be from hitting a breakpoint or exiting
    self.registers._refresh_registers()

def cont(self):
    rip = self.registers["rip"]
    if rip in self.breakpoints.get_breakpoints():
        self.breakpoints.step_from_breakpoint(rip)
    ptrace.cont(self.child_pid)
    os.wait() # wait for child to raise a signal, which can be from hitting a breakpoint or exiting
    self.registers._refresh_registers()

def next(self):
    # TODO implement next, which steps over function calls
    pass

def finish(self):
    # TODO implement finish, which steps out of the current function
    pass