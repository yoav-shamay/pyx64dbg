import os
import pty
import termios
from pyx64dbg.breakpoint import Breakpoints
from pyx64dbg.callback_list import CallbackList
from pyx64dbg.memory import Memory
import pyx64dbg.ptrace as ptrace
from pyx64dbg.stdio_tube import StdioTube
from pyx64dbg.registers import Registers
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from pyx64dbg.process_exited_error import ProcessExitedError
from pyx64dbg.parse_elf import ELFFileParser
from pyx64dbg.symbols import Symbols

from pyx64dbg.stack import Stack


class Debugger:
    def __init__(
        self,
        child_pid,
        child_pty,
        file_path=None,
    ):
        self.child_pid = child_pid
        self.child_pty = child_pty

        self.process_exited = False
        self.error_signal = None
        self.exit_code = None
        self.exit_callbacks = CallbackList() # callbacks for when the process exits
        self.stop_callbacks = CallbackList() # callbacks for when the process stops (finishes running instructions)
        self.update_callbacks = CallbackList() # callbacks for when any of the debugger state updates
        self.busy_callbacks = CallbackList() # callbacks for when the debugger starts movement, and can't process operations as it waits for the process to finish
        self.stopped_signal = None

        self.breakpoints = Breakpoints(child_pid, self._ensure_running, self.update_callbacks.trigger)
        self.memory = Memory(child_pid, self.breakpoints, self._ensure_running, self.update_callbacks.trigger)
        self.registers = Registers(child_pid, self._ensure_running, self.update_callbacks.trigger)
        self.stack = Stack(self.memory, self.registers, self._ensure_running)
        if child_pty is not None:
            self.stdio = StdioTube(child_pty)
        else:
            self.stdio = None

        self._cs = Cs(CS_ARCH_X86, CS_MODE_64)
        self._cs.detail = True

        if file_path is None:
            # if file path isn't provided, default to determining it from procfs (/proc/<pid>/exe)
            self.file_path = f"/proc/{child_pid}/exe"
        else:
            self.file_path = file_path

        with ELFFileParser(self.file_path) as elf_parser:
            symbol_list = elf_parser.get_elf_symbols()
            entry_offset = elf_parser.get_entry_point()

        self._init_base_address_and_ld_Base(entry_offset)
        self.symbols = Symbols(symbol_list, self.base_address)

        # run until the program entry, so the linker finishes execution
        self.breakpoints.add_breakpoint(self.base_address + entry_offset)
        self.continue_execution()
        self.breakpoints.remove_breakpoint(self.base_address + entry_offset)

        # init shared objects dictionary, after getting ld base
        self.shared_objects = {}
        shared_object_list = self._get_shared_objects()
        for shared_object in shared_object_list:
            self.shared_objects[shared_object.name] = shared_object

        self._init_address_to_symbol_mapping()

    @staticmethod
    def _start_as_child(file_name: str, redirect_stdio_to_pty: bool, disable_pty_echo: bool, argv: list):
        if redirect_stdio_to_pty:
            if disable_pty_echo:
                attrs = termios.tcgetattr(0)
                attrs[3] &= ~termios.ECHO
                termios.tcsetattr(0, termios.TCSANOW, attrs)
        # start ptrace on this process
        ptrace.traceme()
        # execve file_name with the given argv - run the process
        os.execve(file_name, [file_name] + argv, {})

    @staticmethod
    def start_and_debug(file_name: str, redirect_stdio_to_pty=True, disable_pty_echo = True, argv=[]):
        if redirect_stdio_to_pty:
            # fork the process and create a new pty for the child, which will be used to redirect the child's stdio to the terminal, allowing the user to interact with the child process through the terminal.
            master_fd, slave_fd = pty.openpty()
            child_pid = os.fork()
            if child_pid == 0:  # running as child
                os.close(master_fd)  # close the master fd in the child, as it's only used by the parent
                os.dup2(slave_fd, 0)  # redirect stdin to the slave fd of the pty
                os.dup2(slave_fd, 1)  # redirect stdout to the slave fd of the pty
                os.dup2(slave_fd, 2)  # redirect stderr to the slave fd of the pty
                os.close(slave_fd)  # close the slave fd in the child, as it's now duplicated to stdio
            else:
                os.close(slave_fd)  # close the slave fd in the parent, as it's only used by the child
                pty_fd = master_fd
        else:
            child_pid = os.fork()
            pty_fd = None
        if child_pid == 0:  # running as child
            Debugger._start_as_child(file_name, redirect_stdio_to_pty, disable_pty_echo, argv)
        # running as parent
        os.wait()  # wait for child to start execve, raising a signal
        res = Debugger(child_pid, pty_fd)
        return res

    def _ensure_running(self):
        if self.process_exited:
            raise ProcessExitedError(exit_code=self.exit_code, signal=self.error_signal)

    def _init_address_to_symbol_mapping(self):
        self.address_to_symbol = {}
        sym_classes = [self.symbols]
        for so in self.shared_objects.values():
            sym_classes.append(so.symbols)
        for sym_class in sym_classes:
            for name, address in sym_class.functions.items():
                self.address_to_symbol[address] = name
            for name, address in sym_class.objects.items():
                self.address_to_symbol[address] = name

    def kill_process(self):
        self._ensure_running()
        self.busy_callbacks.trigger() # Trigger the busy callback as we wait for the process
        ptrace.kill(self.child_pid)
        _, status = (
            os.wait()
        )  # wait for child to raise a signal, which should be from killing the process
        self._handle_signal(status)
        self.update_callbacks.trigger()

    def surpass_signal(self):
        """
        Surpasses the current signal, allowing the process to continue execution without handling the signal.
        """
        self._ensure_running()
        if self.stopped_signal is None:
            raise ValueError("Not currently stopped by a signal")
        self.stopped_signal = None
        self.update_callbacks.trigger()
    
   

    from pyx64dbg.movement_functions import (
        single_step,
        continue_execution,
        next,
        finish,
        _handle_signal,
        _step_from_breakpoint,
        _notify_update_and_stop
    )
    from pyx64dbg.memory_functions import (
        read_instruction,
        read_number,
        write_number,
        read_c_string,
    )
    from pyx64dbg.get_mappings import (
        _init_base_address_and_ld_Base,
        _get_shared_objects,
        _get_auxv,
        _get_program_header_address,
        _get_program_header_entry_count,
        _get_dynamic_section_address,
        _get_r_debug_address,
        _get_linkmap_address,
    )