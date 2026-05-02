from __future__ import annotations
from PyQt6.QtCore import Q_ARG, QMetaObject, QObject, Qt, pyqtSignal, pyqtSlot, QEventLoop
import capstone
from pyx64dbg.debugger import Debugger
from pyx64dbg.interactive_console.interactive_console import InteractiveConsole
from typing import Optional
from ipykernel.kernelapp import IPKernelApp
import sys
from ipykernel.eventloops import enable_gui
from pyx64dbg.GUI.debugger_state import DebuggerState
from typing import Generic, TypeVar, Optional

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


T = TypeVar('T')
class ReturnHolder(Generic[T]):
    """
    A simple class to hold a return value from a method called through the call_from_another_thread utility function.
    This is needed because when calling a method through Qt's signal-slot mechanism, we can't directly return a value from the method.
    So we use this class as an argument instead.
    """
    def __init__(self):
        self.value : Optional[T] = None

class DebuggerWorker(QObject):
    """
    A worker that manages the debugger and interactive console.
    Should run on a separate thread from the GUI to allow blocking debugger operations without freezing the GUI.
    It communicates with the GUI through signals and slots.
    The interactive_console object lives in the same thread as the debugger, so all
    interactive console operations are thread-safe with debugger operations.
    """
    
    # Signal emitted when the process starts
    process_started = pyqtSignal() 
    
    # Signal emitted when the debugger isn't busy (process is stopped)
    debugger_ready = pyqtSignal()
    
    # Signal emitted when the process exits
    process_exited = pyqtSignal()

    # Signal emitted when the debugger is busy, when waiting for the process (used to disable GUI controls)
    debugger_busy = pyqtSignal()

    # Signal emitted when the debugger state updates and the GUI should refresh views
    state_update = pyqtSignal(DebuggerState) 

    # After kernel finishes initialization
    kernel_initialized = pyqtSignal(object)
    
    def __init__(self):
        super().__init__()
        self.debugger: Optional[Debugger] = None
        self.interactive_console: Optional[InteractiveConsole] = None
        self.kernel_app = None
        self.file_name = None
    
    @pyqtSlot(object)
    def set_file_name(self, file_name: str):
        """
        Slot to set the file name to debug. Called from the GUI thread when a file is selected.
        """
        self.file_name = file_name
        # update the file in the interactive console as well if it exists
        if self.interactive_console:
            self.interactive_console.select_file(file_name)
    
    @pyqtSlot()
    def setup_kernel(self):
        """
        Function to setup the IPython kernel for the interactive console.
        Emits the kernel_initialized signal with the connection information once the kernel is ready.
        """
        self.kernel_app = IPKernelApp.instance()
        # initialize with the --quiet flag to prevent initialization messages printing to the console.
        self.kernel_app.initialize(["--quiet"])
        # save the connection dict, that will later be emitted to the GUI to connect the console widget to the kernel
        self.kernel_connection_dict = self.kernel_app.get_connection_info()
        # set the kernel's application to a custom application that has an event loop, allowing the kernel to operate on a qt event loop
        self.kernel_app.kernel.app = KernelApplication()
        # use enable_gui to make the IPython kernel event loop compatible with Qt, allowing the worker to receive signals while the kernel is running.
        enable_gui('qt6', self.kernel_app.kernel)
        self.shell = self.kernel_app.kernel.shell
        
        self.shell.autocall = 2 # autocall - call functions without parenthesis
        self.shell.show_rewritten_input = False # don't show the input twice when autocall is triggered
        self.shell.showtraceback = self._show_simple_error # override default IPython traceback to show simpler error messages in the console widget

        # initialize the interactive console object and set up callbacks for synchronization with the worker state
        self.interactive_console = InteractiveConsole(
            redirect_stdio_to_pty=True,
            update_aliases_callback=self._update_shell_aliases,
            new_debugger_object_callback=self._new_console_debugger_object
        )
        # push initial aliases
        self.shell.push(self.interactive_console.get_aliases())
        # emit signal that kernel is initialized and pass the connection information to the GUI
        self.kernel_initialized.emit(self.kernel_connection_dict)
        # start the kernel app
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
        else: # process stopped/exited
            self.process_exited.emit()
    
    def _setup_debugger_callbacks(self):
        """
        Setups all the callbacks for the various debugger states (process stop, process exit, state update, busy state).
        Uses the callbacks on this file which emits the signals for the GUI to update accordingly.
        """
        self.debugger.exit_callbacks.add(self._on_process_exit)
        self.debugger.stop_callbacks.add(self._on_process_stop)
        self.debugger.update_callbacks.add(self._on_debugger_update)
        self.debugger.busy_callbacks.add(self._on_debugger_busy)
    
    def _on_process_exit(self):
        self.process_exited.emit()
    
    def _on_process_stop(self):
        self.debugger_ready.emit()
    
    def _on_debugger_update(self):
        debugger_state = DebuggerState(self.debugger)
        self.state_update.emit(debugger_state)
    
    def _on_debugger_busy(self):
        self.debugger_busy.emit()

    @pyqtSlot()    
    def start_debugging(self):
        # start debugging the process
        self.debugger = Debugger.start_and_debug(self.file_name, redirect_stdio_to_pty=True)
        # setup callbacks for the new debugger object
        self._setup_debugger_callbacks()
        # sync the state of the interactive console with the new debugger
        self.interactive_console.update_debugger(self.debugger)
        self.process_started.emit()
        self._on_debugger_update() # trigger a state update, as a new process also means a new state
    
    @pyqtSlot()
    def stop_debugging(self):
        if self.debugger:
            # kill the process if running
            self.debugger.kill_process()
            # set that there's no active debugger
            self.debugger = None
            # update the interactive console state to reflect that there is no active debugger / process
            self.interactive_console.update_debugger(None)
            # emit the process exited signal to update the GUI
            self.process_exited.emit()
    
    @pyqtSlot()
    def handle_exit(self):
        """
        Slot to handle the exit of the debugger process.
        """
        # if a kernel is active, stop it
        if self.kernel_app:
            self.kernel_app.kernel.do_shutdown(restart=False)
    
    @pyqtSlot(object, object, object)
    def read_instructions(self, address : int, amt : int, result : ReturnHolder[list[capstone.cs_insn]]):
        """
        Reads instructions from the debugger
        """
        if self.debugger:
            result.value = self.debugger.read_instruction(address, instruction_cnt=amt)

    @pyqtSlot(object, object, object)
    def read_memory(self, start : int, end : int, result : ReturnHolder[bytes]):
        """
        Reads memory from the debugger
        """
        if self.debugger:
            result.value = self.debugger.memory[start:end]
    
    @pyqtSlot(object)
    def get_address_to_symbol_mapping(self, result : ReturnHolder[dict[int, str]]):
        """
        Gets the address to symbol mapping from the debugger, used for symbol resolution in the GUI.
        """
        if self.debugger:
            result.value = self.debugger.address_to_symbol

    def call_from_another_thread(self, method, *args, blocking=False, returning=False):
        """
        Utility function to call a method in the debugger thread from another thread (e.g. the GUI thread).
        Uses Qt's signal-slot mechanism to safely execute the method in the debugger thread.
        """
        # convert args to Q_ARG format
        qt_args = [Q_ARG(object, arg) for arg in args]
        if returning:
            ret_holder = ReturnHolder() # create a return holder to hold the return value from the method
            qt_args.append(Q_ARG(object, ret_holder)) # add it to the arguments
        # we choose the connection type based on whether we want to block until the method is executed or not (if we need to return the value, we also need to wait until the method finishes executing)
        conn_type = Qt.BlockingQueuedConnection if (blocking or returning) else Qt.QueuedConnection
        # Use invokeMethod to call the method in the debugger thread with the given arguments
        QMetaObject.invokeMethod(self, method, conn_type, *qt_args)
        if returning: # return the value from the return holder if we need to return a value
            return ret_holder.value