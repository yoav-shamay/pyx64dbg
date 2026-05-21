from __future__ import annotations

import os
import pty
import termios
from typing import Never, Optional
from pyx64dbg.utils import validate_file
from pyx64dbg.breakpoint import Breakpoints
from pyx64dbg.callback_list import CallbackList
from pyx64dbg.memory import Memory
from pyx64dbg.number_types import UInt64
import pyx64dbg.os_interaction as os_interaction
from pyx64dbg.shared_object import SharedObject
from pyx64dbg.stdio_tube import StdioTube
from pyx64dbg.registers import Registers
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from pyx64dbg.process_exited_error import ProcessExitedError
from pyx64dbg.parse_elf import ELFFileParser
from pyx64dbg.symbols import Symbols
from pyx64dbg.control import Control
from pyx64dbg.stack import Stack
from pyx64dbg.get_mappings import get_entry_address, get_ld_base, get_shared_objects


class Debugger:
    """
    The main debugger class, which manages a single debugged process.
    This class provides methods for controlling the execution of the process, reading/writing memory and registers, managing breakpoints, handling signals, accessing STDIO, and more.
    Allows to start a process from a given file.
    """
    def __init__(
        self,
        child_pid: int,
        child_pty: Optional[int] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """
        Initializes the Debugger object with the given child process ID.
        Optionally takes a child PTY file descriptor for redirecting the child's stdio, and a file path for the debugged executable (if not provided, it will be determined from /proc/<pid>/exe).
        """
        
        self.child_pid: int = child_pid
        self.child_pty: Optional[int] = child_pty

        self.process_exited: bool = False
        self.error_signal: Optional[int] = None
        self.exit_code: Optional[int] = None
        self.exit_callbacks: CallbackList[[]] = CallbackList() # callbacks for when the process exits
        self.stop_callbacks: CallbackList[[]] = CallbackList() # callbacks for when the process stops (finishes running instructions)
        self.update_callbacks: CallbackList[[]] = CallbackList() # callbacks for when any of the debugger state updates
        self.busy_callbacks: CallbackList[[]] = CallbackList() # callbacks for when the debugger starts movement, and can't process operations as it waits for the process to finish
        self.stopped_signal: Optional[int] = None

        self.breakpoints: Breakpoints = Breakpoints(self)
        self.memory: Memory = Memory(self)
        self.registers: Registers = Registers(self)
        self.stack: Stack = Stack(self)
        self.control = Control(self)
        self._stdio: Optional[StdioTube] = None
        if child_pty is not None: # if we are given a child PTY, assign the stdio tube to it.
            self._stdio: Optional[StdioTube] = StdioTube(child_pty)

        self._cs: Cs = Cs(CS_ARCH_X86, CS_MODE_64)
        self._cs.detail = True

        if file_path is None:
            # if file path isn't provided, default to determining it from procfs (/proc/<pid>/exe)
            self.file_path: str = f"/proc/{child_pid}/exe"
        else:
            self.file_path: str = file_path

        with ELFFileParser(self.file_path) as elf_parser:
            symbol_list = elf_parser.get_elf_symbols()
            entry_offset = elf_parser.get_entry_point_offset()
            self.is_pie: bool = elf_parser.is_pie()
            if not self.is_pie:
                # for non-PIE binaries, we can determine the base address from the ELF file, as it's fixed
                self.base_address: UInt64 = UInt64(elf_parser.get_load_base_address())
                # if it's a non-PIE binary, all the symbols and addresses are based on the fixed load address, so the offset is 0
                # Otherwise, they are based on the base address we deduced
                # This offset between the actual load address and symbol address is called "load bias"
                self.load_bias: UInt64 = UInt64(0)
        auxv = os_interaction.get_auxv(self.child_pid)
        if self.is_pie:
            # for PIE binaries, we need to deduce the base address from the entry point address and the entry offset
            entry_address = get_entry_address(auxv)
            self.base_address: UInt64 = entry_address - entry_offset
            self.load_bias: UInt64 = self.base_address
        self.entry_address: UInt64 = self.load_bias + entry_offset
        self.ld_base: UInt64 | None = get_ld_base(auxv)
        self.symbols: Symbols = Symbols(symbol_list, self.load_bias) # symbols are based on load bias
        self.shared_objects: dict[str, SharedObject] = {} # set shared objects to empty for now, as the refresh might fail
        # init shared objects dictionary
        try:
            self.refresh_shared_objects()
        except RuntimeError:
            # The linker might not have loaded yet, in which case we will get an exception.
            # Just do nothing in this case.
            pass
        self._init_address_to_symbol_mapping() # anyway initialize the address to symbol mapping, even if there aren't shared objects

    @staticmethod
    def _start_as_child(file_name: str, argv: list[str]) -> Never:
        """
        An internal method that runs as the child process.
        Runs the provided file with the provided arguments using execve.
        Runs ptrace with PTRACE_TRACEME to allow tracing this process.
        """
        # run ptrace with PTRACE_TRACEME to allow tracing this process
        os_interaction.traceme()
        # execve file_name with the given argv and existing environment - run the process
        os.execve(file_name, argv, os.environ)

    @staticmethod
    def start_and_debug(file_name: str, redirect_stdio_to_pty: bool = True, disable_pty_echo: bool = True, argv: Optional[list[str]] = None) -> Debugger:
        """
        Starts and debugs the specified file and returns a Debugger instance.
        Options:
        redirect_stdio_to_pty: whether to redirect the child's stdio to a new PTY, allowing interacting with the stdio through the API (or the pty directly).
        If false, will stay the stdio of the parent process (used in the interactive console).
        disable_pty_echo: whether to disable echo on the PTY if redirecting stdio to a PTY.
        Usually set for the API, we don't want the code to recieve echoed input.
        argv - a list of arguments to pass to the process (not including the file name, which is passed separately)
        """
        # validate file before forking
        validate_file(file_name)
        # handle argv - if it's None we treat it as no arguments, and add the file name in the beginning of the arguments list
        if argv is None:
            argv = [file_name]
        else:
            argv = [file_name] + argv
        pty_fd = None
        if redirect_stdio_to_pty:
            # if we want to redirect stdio to a PTY, we first open a PTY
            master_fd, slave_fd = pty.openpty()
            child_pid = os.fork()
            if child_pid == 0:  # running as child
                # setup the PTY instead of the STDIO
                os.close(master_fd)  # close the master fd in the child, as it's only used by the parent
                os.dup2(slave_fd, 0)  # redirect stdin to the slave fd of the pty
                os.dup2(slave_fd, 1)  # redirect stdout to the slave fd of the pty
                os.dup2(slave_fd, 2)  # redirect stderr to the slave fd of the pty
                os.close(slave_fd)  # close the slave fd in the child, as it's now duplicated to stdio
                if disable_pty_echo:
                    # disable echo on the PTY if we want to.
                    # Usually set for the API, we don't want the code to recieve echoed input.
                    attrs = termios.tcgetattr(0)  # get current terminal attributes
                    attrs[3] = attrs[3] & ~termios.ECHO  # disable ECHO flag in local modes
                    termios.tcsetattr(0, termios.TCSANOW, attrs)  # set the modified attributes immediately
            else: # running as parent
                os.close(slave_fd)  # close the slave fd in the parent, as it's only used by the child
                pty_fd = master_fd
        else:
            # if we don't want, we just fork and do nothing else
            child_pid = os.fork()
        if child_pid == 0:  # If running as child, do the initialization and execve in the _start_as_child method
            Debugger._start_as_child(file_name, argv)
            # this function runs execve, which means its execution doesn't continue after calling the function
        # running as parent
        os.waitpid(child_pid, 0)  # wait for child to start execve, raising a signal
        res = Debugger(child_pid, pty_fd, file_path=file_name) # create a debugger instance
        if res.ld_base is not None:
            # run until the program entry, so the linker finishes execution
            # only if there's a dynamic linker (the binary isn't statically linked)
            res.breakpoints.add_breakpoint(res.entry_address)
            res.control.continue_execution()
            res.breakpoints.remove_breakpoint(res.entry_address)
        # refresh shared objects, as the linker loads them during its execution
        res.refresh_shared_objects()
        return res

    @property
    def stdio(self) -> StdioTube:
        """
        Returns the StdioTube object for interacting with the debugged process's stdio.
        Raises an exception if the stdio wasn't redirected to a PTY when starting the debugger, as in this case we won't have a StdioTube.
        """
        if self._stdio is None:
            raise ValueError("Stdio wasn't redirected to a PTY")
        return self._stdio
    
    def refresh_shared_objects(self) -> None:
        """
        Refreshes the list of shared objects in the debugger.
        Should be called if a new shared object was dynamically loaded after initialization
        """
        if self.ld_base is None:
            # if we don't have an ld base, which is the case for static linked binaries, we don't have shared objects
            return
        self.shared_objects: dict[str, SharedObject] = {}
        shared_object_list = get_shared_objects(self)
        for shared_object in shared_object_list:
            self.shared_objects[shared_object.name] = shared_object

        self._init_address_to_symbol_mapping()

    def _ensure_running(self) -> None:
        """
        An internal method to ensure the process is still running before performing any operations.
        Raises a ProcessExitedError if the process has exited, with the relevant exit code and signal information.
        Should be called at the start of any public method that requires the process to be running.
        """
        if self.process_exited:
            raise ProcessExitedError(exit_code=self.exit_code, signal=self.error_signal)

    def _init_address_to_symbol_mapping(self) -> None:
        """
        Initializes the address_to_symbol dictionary, which maps between address and symbol names for easy lookup.
        Uses function / object symbols from the main executable and all shared objects to populate the mapping.
        """
        self.address_to_symbol: dict[UInt64, str] = {}
        sym_classes = [self.symbols]
        for so in self.shared_objects.values():
            sym_classes.append(so.symbols)
        for sym_class in sym_classes:
            for name, address in sym_class.functions.items():
                self.address_to_symbol[address] = name
            for name, address in sym_class.objects.items():
                self.address_to_symbol[address] = name
    
    def _on_exit(self) -> None:
        """
        An internal method that should be called when the process exits.
        Triggers the exit callbacks and closes the pty if it exists.
        """
        if self.child_pty is not None:
            self.stdio.close_pty()
        self.exit_callbacks.trigger()