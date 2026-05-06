from __future__ import annotations
import os
from typing import TYPE_CHECKING
from pyx64dbg.GUI.async_slot import async_slot
from qtpy.QtCore import QSocketNotifier
from qtpy.QtWidgets import QWidget, QVBoxLayout
from termqt import Terminal, TerminalPOSIXIO
from termqt.terminal_widget import CursorState

import fcntl
import struct
import termios

from pyx64dbg.GUI.debugger_worker import DebuggerWorker

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

class PtyTerminalIO(TerminalPOSIXIO):
    """
    An implementation of TerminalPOSIXIO that is designed to work with a PTY file descriptor instead of creating a process.
    It uses a QSocketNotifier to listen for data on the PTY and reads it asynchronously
    """
    def __init__(self, cols: int, rows: int, parent : QWidget, logger=None):
        super().__init__(cols, rows, logger)
        self._notifier = None
        self._parent = parent

    def spawn(self, fd: int):
        """
        An override of the spawn method. As we don't really spawn a process, just initiates fd.
        Also sets up a QSocketNotifier instead of the original thread solution, as the original solution might spawn multiple threads in case of quick multiple spawn/terminate calls.
        Takes the relevant logic from the original method
        """
        self.fd = fd
        self.running = True

        # Set the file descriptor to non-blocking
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        # Set the window size of the PTY to match our terminal widget
        s = struct.pack("HHHH", self.rows, self.cols, 0, 0)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, s)

        # set pty configuration using termios to make backspace work correctly
        attrs = termios.tcgetattr(fd)
        iflag, oflag, cflag, lflag, ispeed, ospeed, cc = attrs
        # Tell the PTY to treat \x08 (backspace) as the "Erase" command.
        cc[termios.VERASE] = b'\x08' 
        # Apply settings
        new_attrs = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
        termios.tcsetattr(fd, termios.TCSANOW, new_attrs)

        # Setup QSocketNotifier for Read events. connect it to our parent widget
        self._notifier = QSocketNotifier(self.fd, QSocketNotifier.Read, self._parent)
        self._notifier.activated.connect(self._handle_read)

    def _handle_read(self):
        """
        Slot triggered by Qt whenever there is data available on the PTY.
        """
        try:
            # Read up to 1032 bytes (as per original logic)
            buf = os.read(self.fd, 1032)
            if buf:
                self.stdout_callback(buf)
            else:
                # Empty buf on read indicates EOF reached
                self.terminate()
        except (OSError, BlockingIOError):
            self.terminate() # if there is an error reading, we assume the PTY is closed and terminate the notifier

    def terminate(self):
        """
        Handles closing the PTY.
        Sets the running flag to False, disables and deletes the notifier, and sets fd to -1.
        """
        self.running = False
        if self._notifier:
            self._notifier.setEnabled(False)
            self._notifier.deleteLater() # Schedule the notifier for deletion
            self._notifier = None
        self.fd = -1
    
    def resize(self, rows : int, cols : int):
        """
        Override of the original resize method.
        Doesn't send a signal (as we don't want to cause confusion with random signals when debugging)
        Also only attempts to do it if there's an fd.
        """
        if self.fd != -1:
            s = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, s) # resize this pty using ioctl

    def run_slave(self):
        """
        We need to implement it as it's an abstract method in the parent class.
        Unused, so does nothing.
        """
        pass # Not used in this implementation

class PtyStdioView(QWidget):
    def __init__(self, main_window : MainWindow) -> None:
        super().__init__()
        self._main_window: MainWindow= main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._connect_signals()
        
        # Initialize the Terminal widget as a child member
        # Initial size is 100x100 as it will crash with too small size
        # it needs to be small enough so it won't try to expand the dock to its size
        # It will automatically resize it to fit the dock.
        self._terminal: Terminal = Terminal(100, 100)

        # define terminal io and connect it to the widget, as shown in the example of termqt
        self._terminal_io: PtyTerminalIO = PtyTerminalIO(self._terminal.row_len, self._terminal.col_len, self)
        self._terminal_io.stdout_callback = self._terminal.stdout
        self._terminal.stdin_callback = self._terminal_io.write
        self._terminal.resize_callback = self._terminal_io.resize
        
        # Setup a layout to hold the terminal widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._terminal)

        # apply the cursor fix to the terminal
        self._fix_terminal_cursor()
    
    def _patched_paint_cursor(self):
        # If the widget doesn't have focus, we force the state to OFF
        # before the original drawing logic runs.
        if not self._terminal.hasFocus():
            self._terminal._cursor_blinking_state = CursorState.OFF
        
        # Call the original drawing logic
        self._original_paint_cursor()


    def _fix_terminal_cursor(self):
        """
        Patch the terminal so the cursor only blinks when the terminal widget has focus, otherwise it stays invisible.
        This is because we want to have some indicator when the terminal is focused, and the library shows the cursor even when the terminal is not focused, which can be misleading.
        """
        # Store the original paint method
        self._original_paint_cursor = self._terminal._paint_cursor
        self._terminal._paint_cursor = self._patched_paint_cursor

    def _connect_signals(self):
        self._debugger_worker.process_started.connect(self._on_process_start)
        self._debugger_worker.process_exited.connect(self._on_process_exit)
        self._debugger_worker.file_selected.connect(self._on_file_select)

    @async_slot
    async def _on_process_start(self):
        pty_fd = await self._debugger_worker.call_async(self._debugger_worker.get_pty_fd)
        self._terminal_io.spawn(pty_fd)
        # Call clear on the internal terminal object
        self.clear_buffer()
    
    @async_slot
    async def _on_process_exit(self):
        self.close_pty()

    def open_pty(self, fd: int) -> None:
        self.close_pty() # close any existing pty before opening a new one
        self._terminal_io.spawn(fd)

    def close_pty(self) -> None:
        self._terminal_io.terminate()

    def clear_buffer(self) -> None:
        """
        Manually handles the clearing logic since Terminal doesn't have it.
        We access the terminal's internal state directly.
        """
        self._terminal._buffer_lock.lock()
        try:
            self._terminal._buffer = []
            # Assuming Position is available in the terminal_buffer module
            from termqt.terminal_buffer import Position
            self._terminal._cursor_position = Position(0, 0)
            self._terminal._buffer_display_offset = 0
            # Trigger the terminal's internal resize logic to refresh empty state
            self._terminal.resize(self._terminal.width(), self._terminal.height())
        finally:
            self._terminal._buffer_lock.unlock()
            
        # Trigger the terminal's internal repaint signal
        self._terminal.total_repaint_sig.emit()

    def _on_file_select(self) -> None:
        self.clear_buffer()