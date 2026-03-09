from breakpoint import Breakpoints
import ptrace

class Debugger:
    def __init__(self, child_pid, child_pty):
        self.child_pid = child_pid
        self.breakpoints = Breakpoints(ptrace)
        self.child_pty = child_pty