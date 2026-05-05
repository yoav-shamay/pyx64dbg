from __future__ import annotations
from PySide6.QtCore import QObject, Signal, QEventLoop, QTimer
import capstone
from pyx64dbg.debugger import Debugger
from pyx64dbg.interactive_console.interactive_console import InteractiveConsole
from typing import Optional
from ipykernel.kernelapp import IPKernelApp
import sys
from ipykernel.eventloops import enable_gui
from pyx64dbg.GUI.debugger_state import DebuggerState
from typing import Optional
import asyncio

class KernelApplication(QObject):
    """
    A thread-safe implementation of a Qt application including an event loop for the IPython kernel.
    The IPython kernel tries to attach itself to the main Qt application.
    however due to the fact that the kernel is running in a separate thread from the GUI,
    we need to create a separate event loop for it to allow it to receive signals and execute code while the kernel is running.
    This class provides an implementation of an application that the kernel IPython application can attach to.
    This works safely when run on a different thread.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Create a local event loop parented to this object (in the worker thread)
        self.qt_event_loop = QEventLoop(self)

    def exit(self):
        """An exit method that the kernel uses to shut down."""
        self.qt_event_loop.quit()

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

    # After kernel finishes initialization
    kernel_initialized = Signal(object)

    # When a new file is selected
    file_selected = Signal()
    
    def __init__(self):
        super().__init__()
        self.debugger: Optional[Debugger] = None
        self.interactive_console: Optional[InteractiveConsole] = None
        self.kernel_app = None
        self.file_name = None
    
    def set_file_name(self, file_name: str):
        """
        Slot to set the file name to debug. Called from the GUI thread when a file is selected.
        """
        if self.debugger is not None: # if there's a process running, we should stop it before switching to a new file
            self.stop_debugging()

        self.file_name = file_name
        # update the file in the interactive console as well if it exists
        if self.interactive_console:
            self.interactive_console.select_file(file_name, trigger_callbacks = False) # don't trigger the signal, as we emit it manaully (for consistency)
        self.file_selected.emit()  # emit the signal to update the GUI

    def setup_kernel(self):
        """
        Function to setup the IPython kernel for the interactive console.
        Emits the kernel_initialized signal with the connection information once the kernel is ready.
        """
        self.kernel_app = IPKernelApp.instance()
        # initialize with the --quiet flag to prevent initialization messages printing to the console.
        self.kernel_app.initialize(["--quiet"])
        # make the kernel not register signal handlers as it isn't the main thread and it can't by overriding the functions it calls to do it.
        self.kernel_app.kernel.pre_handler_hook = lambda: None
        self.kernel_app.kernel.post_handler_hook = lambda: None
        # save the connection dict, that will later be emitted to the GUI to connect the console widget to the kernel
        self.kernel_connection_dict = self.kernel_app.get_connection_info()
        # set the kernel's application to a custom application that has an event loop, allowing the kernel to operate on a qt event loop
        self.kernel_app.kernel.app = KernelApplication()
        # use enable_gui to make the IPython kernel event loop compatible with Qt, allowing the worker to receive signals while the kernel is running.
        enable_gui('qt6', self.kernel_app.kernel)

        self.shell = self.kernel_app.kernel.shell
        
        self.shell.autocall = 2 # autocall - call functions without parenthesis
        self.shell.show_rewritten_input = False # don't show the input twice when autocall is triggered
        #TODO enable back, currently disabled for debugging
        #self.shell.showtraceback = self._show_simple_error # override default IPython traceback to show simpler error messages in the console widget

        # initialize the interactive console object and set up callbacks for synchronization with the worker state
        
        self.interactive_console = InteractiveConsole(
            redirect_stdio_to_pty=True,
            disable_pty_echo=False, # we want pty echo so the user actually sees what he types in the console
        )
        self.interactive_console.update_aliases_callbacks.add(self._update_shell_aliases)
        self.interactive_console.new_debugger_object_callbacks.add(self._new_console_debugger_object)
        self.interactive_console.file_select_callbacks.add(self._on_console_file_select)
        # push initial aliases
        self.shell.push(self.interactive_console.get_aliases())
        # emit signal that kernel is initialized and pass the connection information to the GUI
        # do it in a QTimer single shot to ensure it is emitted after the kernel finishes initialization and starts the event loop
        QTimer.singleShot(0, lambda: self.kernel_initialized.emit(self.kernel_connection_dict))
        # start the kernel app (blocking call, should be last)
        self.kernel_app.start()

    def _update_shell_aliases(self, aliases: dict):
        """
        Callback - called when the aliases in the interactive console need to be updated (process start / stop)
        """
        self.shell.push(aliases)

    def _show_simple_error(self, *args, **kwargs):
        """
        Override for IPython's default traceback to show simpler error messages in the console widget, showing only the exception type and message without the full stack trace.
        """
        exc_type, exc_value, _ = sys.exc_info()
        if exc_type:
            self.interactive_console.print_error(exc_type.__name__, exc_value)
    
    def _new_console_debugger_object(self, debugger: Debugger):
        """
        Callback - called when a new debugger object is created in the interactive console, when a process starts / exits
        Updates the internal state to synchronize with the console and emits signals to update the GUI.
        """
        self.debugger = debugger
        if debugger is not None: # process started
            self._setup_debugger_callbacks()
            self.process_started.emit()
            self._on_debugger_update() # trigger a state update, as a new process also means a new state
    
    def _setup_debugger_callbacks(self):
        """
        Setups all the callbacks for the various debugger states (process stop, process exit, state update, busy state).
        Uses the callbacks on this file which emits the signals for the GUI to update accordingly.
        """
        self.debugger.exit_callbacks.add(self._on_process_exit)
        self.debugger.stop_callbacks.add(self._on_process_stop)
        self.debugger.update_callbacks.add(self._on_debugger_update)
        self.debugger.busy_callbacks.add(self._on_debugger_busy)
    
    def _on_console_file_select(self, file_name: str):
        """
        Callback - called when a file is selected in the interactive console.
        Updates the internal state to synchronize with the console
        """
        self.file_name = file_name
        self.file_selected.emit()  # emit the signal to update the GUI
    
    def _on_process_exit(self):
        self.process_exited.emit()
    
    def _on_process_stop(self):
        self.debugger_ready.emit()
    
    def _on_debugger_update(self):
        if self.debugger is None:
            return # if process already exited, we should do nothing
        debugger_state = DebuggerState(self.debugger)
        self.state_update.emit(debugger_state)
    
    def _on_debugger_busy(self):
        self.debugger_busy.emit()

    def start_debugging(self):
        # start debugging the process
        # we want pty echo so the user actually sees what he types in the console
        self.debugger = Debugger.start_and_debug(self.file_name, redirect_stdio_to_pty=True, disable_pty_echo=False) 
        # setup callbacks for the new debugger object
        self._setup_debugger_callbacks()
        # sync the state of the interactive console with the new debugger
        self.interactive_console.update_debugger(self.debugger)
        self.process_started.emit()
        self._on_debugger_update() # trigger a state update, as a new process also means a new state
    
    def stop_debugging(self):
        if self.debugger:
            # kill the process if running
            self.debugger.kill_process()
            # call the function to update the state and emit the exit signal
            self.on_process_kill()
    
    def on_process_kill(self):
        """
        Slot to handle external kill signals.
        If we think the process is running, updates the debugger to be None and emits the exit signals.
        The exit signal needs to be emitted as it might not happen while the debugger is waiting and triggering callbacks.
        """
        if self.debugger:
            # if we have a debugger, we think the process is running
            self.debugger = None
            self.interactive_console.update_debugger(None)
            self.process_exited.emit()
    
    def handle_exit(self):
        """
        Slot to handle the exit of the debugger process.
        """
        # if a kernel is active, stop it
        if self.kernel_app:
            self.kernel_app.kernel.do_shutdown(restart=False)
    
    def read_instructions(self, address : int, amt : int) -> list[capstone.CsInsn]:
        """
        Reads instructions from the debugger, if it exists.
        Returns None if not
        """
        if self.debugger:
            return self.debugger.read_instruction(address, instruction_cnt=amt)
        return None

    def read_memory(self, start : int, end : int):
        """
        Reads memory from the debugger if it exists.
        Returns None if not.
        """
        if self.debugger:
            return self.debugger.memory[start:end]
        return None

    def get_address_to_symbol_mapping(self):
        """
        Gets the address to symbol mapping from the debugger, used for symbol resolution in the GUI.
        Returns None if no debugger is active.
        """
        if self.debugger:
            return self.debugger.address_to_symbol
        return None

    def get_pty_fd(self):
        """
        Gets the pty file descriptor from the debugger, used for redirecting the process stdio to the terminal widget.
        Returns None if no debugger or pty is active.
        """
        if self.debugger and self.debugger.child_pty:
            return self.debugger.child_pty
        return None
    
    def single_step(self):
        """
        Steps one instruction in the debugger if it exists.
        """
        if self.debugger:
            self.debugger.single_step()
    
    def evaluate_expression(self, expression: str):
        """
        Evaluates an expression in the context of the debugged process using the interactive console shell.
        Returns the result of the evaluation, or None if no interactive shell is active.
        """
        if self.shell:
            return self.shell.ev(expression)
        return None
    
    def add_breakpoint(self, address: int):
        """
        Adds a breakpoint at the specified address.
        """
        if self.debugger:
            self.debugger.breakpoints.add_breakpoint(address)

    def remove_breakpoint(self, address: int):
        """
        Removes a breakpoint at the specified address.
        """
        if self.debugger:
            self.debugger.breakpoints.remove_breakpoint(address)
    
    def continue_execution(self):
        """
        Continues the execution of the debugged process.
        """
        if self.debugger:
            self.debugger.continue_execution()
    
    def set_register(self, register: str, value: int):
        """
        Sets the value of a register in the debugged process.
        """
        if self.debugger:
            self.debugger.registers[register] = value

    def call_from_another_thread(self, func, *args, **kwargs):
        """
        Utility function to call a method in the debugger thread from another thread (e.g. the GUI thread).
        Doesn't wait for the result.
        """
        call_func = lambda: func(*args, **kwargs)
        # use qtimer single shot to safely call the function without blocking
        QTimer.singleShot(0, self, call_func)
    
    def call_async(self, method : callable, *args):
        """
        Executes a method in the debugger thread asynchronously.
        Returns an asyncio.Future that can be awaited in the GUI thread.
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        # use execute_and_resolve to call the 
        call_func = lambda: self._execute_method(future, loop, method, *args)
        # use qtimer single shot to safely call the function without blocking
        QTimer.singleShot(0, self, call_func)
        # return the created future
        return future

    def _execute_method(self, future: asyncio.Future, loop: asyncio.AbstractEventLoop, func: callable, *args):
        """
        Internal helper that runs in the worker thread. 
        Executes the target method and pushes the result back to the GUI loop.
        """
        try:
            result = func(*args)
            loop.call_soon_threadsafe(future.set_result, result)
        except Exception as e:
            loop.call_soon_threadsafe(future.set_exception, e)
