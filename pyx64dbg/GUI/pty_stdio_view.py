from __future__ import annotations
import os
import fcntl
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import QSocketNotifier, Qt
from pyx64dbg.GUI.async_slot import async_slot

BATCH_READ_SIZE = 4096 # amount of characters to read at once to prevent syscall for every character

class PtyStdioView(QPlainTextEdit):
    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self._pty_fd = None
        self._notifier = None
        self._main_window = main_window
        self._debugger_worker = main_window.debugger_worker
        # connect process start and exit signals to open and close the pty
        self._debugger_worker.process_started.connect(self._on_process_start)
        self._debugger_worker.process_exited.connect(self._on_process_exit)
        
        # Load the stylesheet from the specified relative path
        style_path = os.path.join(os.path.dirname(__file__), "styles", "pty_stdio.qss")
        if os.path.exists(style_path):
            with open(style_path, "r") as f:
                self.setStyleSheet(f.read())

        # Logic settings that QSS cannot handle
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setReadOnly(False) 
        self.setPlaceholderText("Process output will appear here...")
    
    @async_slot
    async def _on_process_start(self):
        pty_fd = await self._debugger_worker.call_async(self._debugger_worker.get_pty_fd)
        if pty_fd is not None:
            self.open_pty(pty_fd)
    
    @async_slot
    async def _on_process_exit(self):
        self.close_pty()

    def open_pty(self, fd: int) -> None:
        self.close_pty()
        self._pty_fd = fd
        
        # Non-blocking for GUI safety
        flags = fcntl.fcntl(self._pty_fd, fcntl.F_GETFL) # get the current flags for the pty fd
        fcntl.fcntl(self._pty_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK) # set the pty fd to non-blocking mode
        
        # create qsocketnotifier to watch for the pty reads
        self._notifier = QSocketNotifier(self._pty_fd, QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._on_pty_read)

    def close_pty(self) -> None:
        # Before detaching, check if there's any residual data in the buffer
        if self._pty_fd is not None:
            self._on_pty_read()

        if self._notifier:
            self._notifier.setEnabled(False)
            self._notifier = None
        self._pty_fd = None

    def _on_pty_read(self) -> None:
        if self._pty_fd is None: return
        try:
            # Read until the buffer is empty (Non-blocking)
            while True:
                data = os.read(self._pty_fd, BATCH_READ_SIZE)
                if not data:
                    break
                    
                cursor = self.textCursor()
                for char_code in data:
                    if char_code == 0x08 or char_code == 0x7f:  # Backspace/Delete
                        cursor.movePosition(QTextCursor.MoveOperation.End)
                        cursor.deletePreviousChar()
                    elif char_code == 0x0D: # Ignore \r
                        pass 
                    else:
                        self.moveCursor(QTextCursor.MoveOperation.End)
                        self.insertPlainText(chr(char_code))
                self.ensureCursorVisible()
        except (OSError, EOFError):
            pass # in case there was some reading error, like when the pty was closed, just ignore it 

    def keyPressEvent(self, event) -> None:
        if self._pty_fd is None:
            super().keyPressEvent(event)
            return

        key = event.key()
        text = event.text()

        if key == Qt.Key_Return or key == Qt.Key_Enter:
            os.write(self._pty_fd, b"\n")
        elif key == Qt.Key_Backspace:
            os.write(self._pty_fd, b"\x7f")
        elif text:
            try:
                os.write(self._pty_fd, text.encode('utf-8'))
            except OSError:
                pass
        # Kernel Echo handles the visual update