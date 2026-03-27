import os
import pty
import termios
from breakpoint import Breakpoints
from memory import Memory
import ptrace
from registers import Registers

class Debugger:
    def __init__(self, child_pid, child_pty):
        self.child_pid = child_pid
        self.child_pty = child_pty
        self.breakpoints = Breakpoints(child_pid)
        self.memory = Memory(child_pid)
        self.registers = Registers(child_pid)
    
    @staticmethod
    def _start_as_child(file_name : str):
        # disable pty echo
        attrs = termios.tcgetattr(0)
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(0, termios.TCSANOW, attrs)
        # start ptrace on this process
        ptrace.traceme()
        # execve file_name
        os.execve(file_name, [file_name], {})

    @staticmethod
    def start_and_debug(file_name : str):
        child_pid, pty_fd = pty.fork()
        if child_pid == 0: # running as child
            Debugger._start_as_child(file_name)
        # running as parent
        os.wait() # wait for child to start execve, raising a signal
        res = Debugger(child_pid, pty_fd)
        return res
    
    from movement_functions import single_step, continue_execution, next, finish, _handle_signal