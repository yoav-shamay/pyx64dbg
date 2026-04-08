import os
import pty
import termios
from breakpoint import Breakpoints
from memory import Memory
import ptrace
from registers import Registers
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from process_exited_error import ProcessExitedError

from stack import Stack

class Debugger:
    def __init__(self, child_pid, child_pty, exit_callback=None, stop_callback=None):
        self.child_pid = child_pid
        self.child_pty = child_pty

        self.process_exited = False
        self.error_signal = None
        self.exit_code = None
        self.exit_callback = exit_callback
        self.stop_callback = stop_callback
        self.stopped_signal = None
        
        self.breakpoints = Breakpoints(child_pid, self._ensure_running)
        self.memory = Memory(child_pid, self.breakpoints, self._ensure_running)
        self.registers = Registers(child_pid, self._ensure_running)
        self.stack = Stack(self.memory, self.registers, self._ensure_running)

        self.cs = Cs(CS_ARCH_X86, CS_MODE_64)
        self.cs.detail = True

    
    @staticmethod
    def _start_as_child(file_name : str, redirect_stdio_to_pty : bool, argv : list):
        if redirect_stdio_to_pty:
            # disable pty echo
            attrs = termios.tcgetattr(0)
            attrs[3] &= ~termios.ECHO
            termios.tcsetattr(0, termios.TCSANOW, attrs)
        # start ptrace on this process
        ptrace.traceme()
        # execve file_name with the given argv - run the process
        os.execve(file_name, [file_name] + argv, {})

    @staticmethod
    def start_and_debug(file_name : str, redirect_stdio_to_pty=True, argv=[]):
        if redirect_stdio_to_pty:
            # fork the process and create a new pty for the child, which will be used to redirect the child's stdio to the terminal, allowing the user to interact with the child process through the terminal.
            child_pid, pty_fd = pty.fork()
        else:
            child_pid = os.fork()
            pty_fd = None
        if child_pid == 0: # running as child
            Debugger._start_as_child(file_name, redirect_stdio_to_pty, argv)
        # running as parent
        os.wait() # wait for child to start execve, raising a signal
        res = Debugger(child_pid, pty_fd)
        return res
    
    def _ensure_running(self):
        if self.process_exited:
            raise ProcessExitedError(exit_code=self.exit_code, signal=self.error_signal)
    
    def kill_process(self):
        self._ensure_running()
        ptrace.kill(self.child_pid)
        _, status = os.wait() # wait for child to raise a signal, which should be from killing the process
        self._handle_signal(status)
    
    from movement_functions import single_step, continue_execution, next, finish, _handle_signal
    from memory_functions import read_instruction, read_number, write_number