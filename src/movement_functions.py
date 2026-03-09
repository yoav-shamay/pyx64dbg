import ptrace

def step(self):
    rip = self.standard_regs["rip"]
    if rip in self.breakpoints.get_breakpoints():
        self.breakpoints.step_from_breakpoint(rip)
    else:
        ptrace.single_step(self.child_pid)

def cont(self):
    rip = self.standard_regs["rip"]
    if rip in self.breakpoints.get_breakpoints():
        self.breakpoints.step_from_breakpoint(rip)
    ptrace.cont(self.child_pid)

def next(self):
    # TODO implement next, which steps over function calls
    pass

def fin(self):
    # TODO implemetn fin, which steps out of the current function
    pass