from __future__ import annotations
import os
from PySide6.QtCore import QObject, Signal, Slot
import capstone
from pyx64dbg.CLI.ipython_cli import IPythonCLI
from pyx64dbg.debugger import Debugger
from pyx64dbg.interactive_console import console_functions
from pyx64dbg.interactive_console.interactive_console import InteractiveConsole
from pyx64dbg.number_types import UInt64, CNumBase
from pyx64dbg.symbols import Symbol
from typing import Any, Callable, Optional, ParamSpec, TypeVar
import sys
from pyx64dbg.GUI.debugger_state import DebuggerState
from typing import Optional
import asyncio
from pyx64dbg.vector_register import VectorRegister
import nest_asyncio
P = ParamSpec('P') # parametes of a callable
R = TypeVar('R') # return type of a callable

class DebuggerWorker(QObject):
    """
    A worker that manages the debugger and interactive console.
    Should run on a separate thread from the GUI to allow blocking debugger operations without freezing the GUI.
    It communicates with the GUI through signals and slots.
    The interactive_console object lives in the same thread as the debugger, so all
    interactive console operations are thread-safe with debugger operations.
    """
    # signals might be emitted twice in a row, in case of updates from multiple conditions.
    # All connected slots should take this in consideration.
    
    # Signal emitted when the process starts
    process_started = Signal()

    # Signal emitted when the debugger isn't busy (process is stopped)
    debugger_ready = Signal()

    # Signal emitted when the process exits
    process_exited = Signal()

    # Signal emitted when the debugger is busy, when waiting for the process (used to disable GUI controls)
    debugger_busy = Signal()

    # Signal emitted when the debugger state updates and the GUI should refresh views
    state_update = Signal(DebuggerState)

    # When a new file is selected
    file_selected = Signal()
    
    def __init__(self):
        super().__init__()
        self.debugger: Debugger | None = None
        self._file_name: str | None = None
        self._ipython_cli: IPythonCLI | None = None
        self._interactive_console: InteractiveConsole | None = None
    
    @Slot()
    def start_asyncio_loop(self) -> None:
        """
        Creates and starts the asyncio event loop for the debugger thread.
        Called after the thread starts.
        """
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        nest_asyncio.apply(self._loop) # as IPython creates an event loop, we need to use nest_asyncio to allow nested event loops
        self._loop.run_forever()
    
    def set_file_name(self, file_name: str) -> None:
        """
        Sets the file name to debug.
        Called from the GUI thread when a file is selected.
        """
        if self.debugger is not None: # if there's a process running, we should stop it before switching to a new file
            self.stop_debugging()

        self._file_name = file_name
        # update the file in the interactive console as well if it exists
        if self._interactive_console:
            console_functions.select_file(self._interactive_console, file_name, trigger_callbacks = False) # don't trigger the signal, as we emit it manaully (for consistency)
        self.file_selected.emit()  # emit the signal to update the GUI

    def setup_shell(self, pty_slave_fd: int):
        """
        Function to setup the IPython shell for the interactive console.
        Uses the IPythonCLI class to manage the shell, and redirects the stdio to the provided PTY slave fd.
        """
        # redirect stdio to the PTY
        os.dup2(pty_slave_fd, sys.stdin.fileno())
        os.dup2(pty_slave_fd, sys.stdout.fileno())
        os.dup2(pty_slave_fd, sys.stderr.fileno())
        # start the IPython shell
        self._ipython_cli = IPythonCLI(use_external_pty = True) # we use an external PTY for STDIO
        self._interactive_console = self._ipython_cli.interactive_console
        # register the interactive console callbacks to synchronize state and emit signals for the GUI
        self._interactive_console.file_select_callbacks.add(self._on_console_file_select)
        self._interactive_console.new_debugger_object_callbacks.add(self._new_console_debugger_object)
        self._interactive_console.system_msg_printer = self._system_msg_printer # set the system message wrapper to wrap system messages in the console
        # start the IPython CLI (blocking call for this function, has to be last, but doesn't block the asyncio loop itself)
        self._ipython_cli.start_console(register_exit_handler=False) # we don't want to register the exit handler as we handle it ourselves in the GUI
    
    def _system_msg_printer(self, msg: str) -> None:
        """
        Prints console system messages.
        Makes sure to print the message in its own line, make it colored and that the prompt is correctly redrawn after it.
        """
        # ansi codes for the cursor
        CARRIAGE_RETURN = "\r"
        CLEAR_LINE = "\x1b[2K"
        YELLOW = "\x1b[33m"
        RESET = "\x1b[0m"
        # replace the text in the current line with the message, print it in yellow, and move to the next line
        sequence = f"{CARRIAGE_RETURN}{CLEAR_LINE}{YELLOW}{msg}{RESET}\n"
        print(sequence, end='') # print the message, without extra newline as already included in the sequence
        self._ipython_cli.shell.pt_app.app.invalidate() # force the IPython shell to redraw to show the prompt correctly afterwards
    
    def _new_console_debugger_object(self, debugger: Debugger | None) -> None:
        """
        Callback - called when a new debugger object is created in the interactive console, when a process starts / exits
        Updates the internal state to synchronize with the console and emits signals to update the GUI.
        """
        self.debugger = debugger
        if debugger is not None: # process started
            self._setup_debugger_callbacks()
            self.process_started.emit() # trigger process start callbacks
            self._on_debugger_update() # trigger a state update, as a new process also means a new state
        # if the process exited the debugger already triggered the exit callbacks, so we don't need to trigger them again here.
    
    def _setup_debugger_callbacks(self) -> None:
        """
        Setups all the callbacks for the various debugger states (process stop, process exit, state update, busy state).
        Uses the callbacks on this file which emits the signals for the GUI to update accordingly.
        """
        self.debugger.exit_callbacks.add(self._on_process_exit)
        self.debugger.stop_callbacks.add(self._on_process_stop)
        self.debugger.update_callbacks.add(self._on_debugger_update)
        self.debugger.busy_callbacks.add(self._on_debugger_busy)
    
    def _on_console_file_select(self, file_name: str) -> None:
        """
        Callback - called when a file is selected in the interactive console.
        Updates the internal state to synchronize with the console
        """
        self._file_name = file_name
        self.file_selected.emit()  # emit the signal to update the GUI
    
    def _on_process_exit(self) -> None:
        """
        Callback - called when the debugged process exits.
        Emits the matching signal.
        """
        self.process_exited.emit()
    
    def _on_process_stop(self) -> None:
        """
        Callback - when the debugged process stops, which means it isn't busy.
        Emits the debugger_ready signal.
        """
        self.debugger_ready.emit()
    
    def _on_debugger_update(self) -> None:
        """
        Callback - when the debugger state updates (or called manually after process start).
        Emits the state_update signal with the new state for the GUI to update views.
        """
        if self.debugger is None or self.debugger.process_exited:
            # if process already exited, we should do nothing
            # process exited might not be updated in the state yet if the update callback was triggered before the exit callback
            # So we checked both the debugger being None and the exit code being not None
            return 
        debugger_state = DebuggerState(self.debugger)
        self.state_update.emit(debugger_state)
    
    def _on_debugger_busy(self) -> None:
        """
        Callback - when the debugger is busy, which means we are waiting for the process to hit a breakpoint or finish.
        Emits the debugger_busy signal.
        """
        self.debugger_busy.emit()

    def start_debugging(self) -> None:
        """
        Starts debugging the process with the currently selected file.
        """
        # first check if we actually have a file selected.
        if self._file_name is None:
            raise ValueError("No file selected to debug.")
        # start debugging the process
        # we want pty echo so the user actually sees what he types in the console
        self.debugger = Debugger.start_and_debug(self._file_name, redirect_stdio_to_pty=True, disable_pty_echo=False) 
        # setup callbacks for the new debugger object
        self._setup_debugger_callbacks()
        # sync the state of the interactive console with the new debugger
        self._interactive_console.update_debugger(self.debugger)
        self.process_started.emit() # emit the process started signal to update the GUI
        self._on_debugger_update() # trigger a state update, as a new process also means a new state
    
    def stop_debugging(self) -> None:
        """
        Stops the debugged process if it is running.
        """
        if self.debugger:
            # kill the process if running
            self.debugger.control.kill_process()
    
    def on_process_kill(self) -> None:
        """
        Function to handle external kill signals.
        If we think the process is running, updates the debugger to be None and emits the exit signals.
        The exit signal needs to be emitted as it might not happen while the debugger is waiting and triggering callbacks.
        """
        if self.debugger:
            # if we have a debugger, we think the process is running
            self.debugger = None
            self._interactive_console.update_debugger(None) # sync the state of the interactive console
            self.process_exited.emit() # emit the process exited signal to update the GUI
    
    def handle_exit(self) -> None:
        """
        Function to handle the exit of the main application.
        Exits the asyncio loop to allow the thread to exit.
        """
        self._loop.stop()
    
    def read_instructions(self, address : int, amt : int) -> list[capstone.CsInsn]:
        """
        Reads instructions from the debugger.
        """
        return self.debugger.memory.read_instruction(address, instruction_cnt=amt)

    def read_memory(self, start : int, end : int) -> bytes:
        """
        Reads a range of memory from the debugger.
        Reads [start, end)
        """
        return self.debugger.memory[start:end]

    def get_address_to_symbol_mapping(self) -> dict[UInt64, str]:
        """
        Gets the address to symbol mapping from the debugger, used for symbol resolution in the GUI.
        """
        return self.debugger.address_to_symbol

    def get_pty_fd(self) -> int:
        """
        Gets the pty file descriptor from the debugger, used for redirecting the process stdio to the terminal widget.
        """
        # we always initialize the debugger with redirect_stdio_to_pty=True so we can assume the child_pty isn't None
        return self.debugger.child_pty
    
    def single_step(self):
        """
        Steps one instruction in the debugger.
        """
        self.debugger.control.single_step()
    
    def evaluate_expression(self, expression: str) -> Any:
        """
        Evaluates an expression in the context of the debugged process using the interactive console shell.
        Returns the result of the evaluation, or None if no interactive shell is active.
        """
        if self._ipython_cli:
            return self._ipython_cli.shell.ev(expression)
        return None
    
    def add_breakpoint(self, address: int):
        """
        Adds a breakpoint at the specified address.
        """
        self.debugger.breakpoints.add_breakpoint(address)

    def remove_breakpoint(self, address: int):
        """
        Removes a breakpoint at the specified address.
        """
        self.debugger.breakpoints.remove_breakpoint(address)
    
    def continue_execution(self):
        """
        Call continue_execution on the debugger.
        """
        self.debugger.control.continue_execution()
    
    def next_instruction(self):
        """
        Call next on the debugger.
        """
        self.debugger.control.next()
    
    def finish(self):
        """
        Call finish on the debugger.
        """
        self.debugger.control.finish()

    def get_register(self, register: str) -> CNumBase | VectorRegister:
        """
        Gets the value of a register from the debugged process.
        """
        return self.debugger.registers.get(register)
    
    def set_register(self, register: str, value: Any) -> None:
        """
        Sets the value of a register in the debugged process.
        """
        self.debugger.registers.set(register, value)
    
    def update_vector_register(self, reg_name: str, view_name: str, index: Optional[int], new_value: Any) -> None:
        """
        Updates a vector register view with a new value.
        If index is provided, updates the corresponding array view (e.g. ymm0.f32[i]).
        Otherwise, updates the single view (e.g. ymm0.sf32).
        """
        if self.debugger:
            reg = self.debugger.registers.get(reg_name)
            if index is not None: # if index is provided, get the attribute and update at index
                arr = getattr(reg, view_name) # use getattr to get the specific view from the register.
                arr[index] = new_value
            else:
                setattr(reg, view_name, new_value) # otherwise use setattr to update the single view directly

    
    def get_all_symbols(self) -> list[Symbol]:
        """
        Gets all symbols from the debugger, used for populating the symbols view in the GUI.
        """
        return self.debugger.symbols.symbols

    def call_from_another_thread(self, func: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> None:
        """
        Utility function to call a method in the debugger thread from another thread (e.g. the GUI thread).
        Doesn't wait for the result.
        """
        call_func = lambda: func(*args, **kwargs)
        # use call_soon_threadsafe to schedule the function to be called in the debugger thread's event loop
        self._loop.call_soon_threadsafe(call_func)
    
    def call_async(self, method : Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> asyncio.Future[R]:
        """
        Executes a method in the debugger thread asynchronously.
        Returns an asyncio.Future that can be awaited in the GUI thread.
        """
        loop = asyncio.get_running_loop() # The GUI thread's loop (not this thread's loop) is where the future needs to be created
        future = loop.create_future()

        def execute():
            try:
                # execute the method and set the result in the future
                result = method(*args, **kwargs)
                loop.call_soon_threadsafe(future.set_result, result)
            except Exception as e:
                # if there's an exception, set it in the future to be raised in the GUI thread
                loop.call_soon_threadsafe(future.set_exception, e)

        if self._loop and self._loop.is_running():
            # Safely schedule the synchronous function on the worker's asyncio loop
            self._loop.call_soon_threadsafe(execute)
            
        return future
