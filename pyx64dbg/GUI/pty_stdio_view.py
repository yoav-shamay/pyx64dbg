from __future__ import annotations
import os
import fcntl
import struct
import termios
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, Slot, QSocketNotifier, QUrl, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

from pyx64dbg.GUI.async_slot import async_slot
from pyx64dbg.GUI.debugger_worker import DebuggerWorker

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

class TerminalBridge(QObject):
    """
    Acts as the interface between Javascript and Python.
    Writes data from JS to the PTY and resizes it on demand.
    """
    def __init__(self, parent_view: PtyStdioView):
        super().__init__(parent_view)
        self._pty_view = parent_view

    @Slot(str)
    def on_js_input(self, data: str) -> None:
        """
        Called by JS when the user types in the terminal. Writes the input data to the PTY.
        """
        if self._pty_view.fd is not None: # if we have a valid PTY file descriptor
            os.write(self._pty_view.fd, data.encode())

    @Slot(int, int)
    def on_js_resize(self, rows: int, cols: int) -> None:
        """
        Called when the terminal is resized in JS (which should be called when the user resizes the window, with the JS calculating the terminal size).
        Resizes the PTY accordingly.
        """
        if self._pty_view.fd is not None:
            # use fnctl to resize the PTY
            s = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self._pty_view.fd, termios.TIOCSWINSZ, s)

class PtyStdioView(QWidget):
    """
    This class defines the PTY stdio view widget in the GUI, which shows the standard input/output of the debugged process.
    Uses xterm.js with a QWebEngineView to render the terminal.
    """
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self.fd: int | None = None
        self._notifier: QSocketNotifier | None = None

        # Setup WebEngineView and communication bridge
        self._view: QWebEngineView = QWebEngineView(self)
        self._channel: QWebChannel = QWebChannel(self)
        self._bridge: TerminalBridge = TerminalBridge(self)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)
        
        # Load the HTML
        file_path = main_window.base_path / "pty_view" / "index.html"
        self._view.load(QUrl.fromLocalFile(str(file_path)))

        # add the view to the widget layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._notifier: QSocketNotifier | None = None

        self._register_callbacks()

    def _register_callbacks(self) -> None:
        self._debugger_worker.process_started.connect(self._on_process_start)
        self._debugger_worker.process_exited.connect(self._on_process_exit)
        self._debugger_worker.file_selected.connect(self._on_file_select)

    @async_slot
    async def _on_process_start(self) -> None:
        """
        Callback - when a process starts.
        Gets the PTY from the debugger worker, opens it, and clears the terminal buffer.
        """
        pty_fd = await self._debugger_worker.call_async(self._debugger_worker.get_pty_fd)
        self._open_pty(pty_fd)
        self._clear_buffer()

    @async_slot
    async def _on_process_exit(self) -> None:
        """
        Callback - when a process exits.
        Closes the PTY (without clearing the buffer, as the user might want to see the output of the process that just exited).
        """
        self._close_pty()

    def _open_pty(self, fd: int) -> None:
        """
        Opens the PTY with the given file descriptor.
        Sets it to non-blocking mode, and sets up a QSocketNotifier to read from it when there's data available.
        """
        self._close_pty()
        self.fd = fd
        
        # Non-blocking mode
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        # Setup Read Notifier
        self._notifier = QSocketNotifier(self.fd, QSocketNotifier.Read, self)
        self._notifier.activated.connect(self._handle_read)

    def _handle_read(self) -> None:
        """
        Callback - when there's data to read from the PTY.
        Reads the data, and sends it to JS to be written to the terminal.
        """
        if self.fd is None:
            # if it was mistakenly called when we don't have a valid file descriptor (can happen if the process exits right after this is called), do nothing
            return
        try:
            buf = os.read(self.fd, 1024)
            if buf:
                # Send data to JS
                js_code = f"writeToTerminal({repr(buf.decode(errors='ignore'))})"
                self._view.page().runJavaScript(js_code)
            else:
                # empty read means EOF
                self._close_pty()
        except (OSError, BlockingIOError):
            # if there's an error reading, we assume the PTY is closed and clean up
            self._close_pty()

    def _close_pty(self) -> None:
        """
        Cleans up after we finish with the PTY.
        Disables the notifier and marks that we no longer have a file descriptor.
        """
        if self._notifier:
            # if we have a notifier, disable it and delete it
            self._notifier.setEnabled(False)
            self._notifier.deleteLater()
            self._notifier = None
        self.fd = None

    def _clear_buffer(self) -> None:
        """
        Clears the terminal buffer, by calling a JS function to clear the terminal.
        """
        self._view.page().runJavaScript("clearTerminal();")

    def _on_file_select(self) -> None:
        """
        Callback - when a new file is selected for debugging.
        Clears the terminal buffer, as the old output is no longer relevant.
        """
        self._clear_buffer()