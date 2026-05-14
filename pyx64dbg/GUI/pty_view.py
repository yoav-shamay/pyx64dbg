from __future__ import annotations
import os
import fcntl
import struct
import termios
from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import QObject, Slot, QSocketNotifier, QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

class TerminalBridge(QObject):
    """
    Acts as the interface between Javascript and Python.
    Writes data from JS to the PTY and resizes it on demand.
    """
    def __init__(self, parent_view: PtyView):
        super().__init__(parent_view)
        self._pty_view = parent_view

    @Slot(str)
    def on_js_input(self, data: str) -> None:
        """
        Called by JS when the user types in the terminal. Writes the input data to the PTY.
        """
        if self._pty_view.read_only: # if the PTY is read-only, ignore the input
            return
        if self._pty_view.fd is not None: # if we have a valid PTY file descriptor
            os.write(self._pty_view.fd, data.encode())

    @Slot(int, int)
    def on_js_resize(self, rows: int, cols: int) -> None:
        """
        Called when the terminal is resized in JS (which should be called when the user resizes the window, with the JS calculating the terminal size).
        Resizes the PTY accordingly.
        """
        # update the saved terminal size
        self._pty_view.term_rows = rows
        self._pty_view.term_cols = cols
        self._pty_view.refresh_pty_size() # synchronize the PTY size with the new terminal size

class PtyView(QWidget):
    """
    This class defines a PTY view widget in the GUI.
    Used for both the interactive console and the stdio view (which inherit from this class and add the necessary handling).
    Uses xterm.js with a QWebEngineView to render the terminal.
    """
    def __init__(self, main_window: MainWindow, post_load: Optional[Callable[[], None]] = None) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self.fd: int | None = None
        self._notifier: QSocketNotifier | None = None

        # Setup WebEngineView and communication bridge
        self._view: QWebEngineView = QWebEngineView(self)
        self._channel: QWebChannel = QWebChannel(self)
        self._bridge: TerminalBridge = TerminalBridge(self)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)
        
        # connect an optional post load callback that can be used by subclasses to perform actions after the HTML is loaded
        if post_load:
            self._view.loadFinished.connect(post_load)
        
        # Load the HTML
        file_path = main_window.base_path / "pty_view" / "index.html"
        self._view.load(QUrl.fromLocalFile(str(file_path)))

        # add the view to the widget layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._notifier: QSocketNotifier | None = None

        # term size, with default values 24x80
        self.term_rows: int = 24
        self.term_cols: int = 80

        self.read_only: bool = False # whether the PTY is read-only (used for the interactive console, which should be read-only while the debugger is busy)

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

        self.refresh_pty_size() # set the initial size of the PTY to match the terminal size we have saved

        # Setup Read Notifier
        self._notifier = QSocketNotifier(self.fd, QSocketNotifier.Read, self)
        self._notifier.activated.connect(self._handle_read)

    def _handle_read(self) -> None:
        """
        Callback - when there's data to read from the PTY.
        Reads the data, and sends it to JS to be written to the terminal.
        """
        if self.fd is None:
            # if it was mistakenly called when we don't have a valid file descriptor, do nothing
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
    
    def refresh_pty_size(self) -> None:
        """
        Synchronizes the pty size with the current terminal size we save.
        Uses fnctl to set the window size of the PTY.
        """
        if self.fd is not None:
            s = struct.pack("HHHH", self.term_rows, self.term_cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, s)