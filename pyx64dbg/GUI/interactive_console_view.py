from __future__ import annotations

from typing import TYPE_CHECKING
import pty
from pyx64dbg.GUI.pty_view import PtyView
from pyx64dbg.GUI.debugger_worker import DebuggerWorker

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

class InteractiveConsoleView(PtyView):
    """
    This class defines the interactive console view widget in the GUI.
    Is a pty web view that shows the interactive console IPython shell
    """
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window, self._init_shell) # setup _init_shell after the web view is loaded
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._register_callbacks()
    
    def _register_callbacks(self) -> None:
        """
        Registers the necessary callbacks to update the console state based on various debugger events.
        Makes the console read-only when the debugger is busy, and editable when it's ready for input.
        """
        self._debugger_worker.debugger_busy.connect(self._on_debugger_busy)
        self._debugger_worker.debugger_ready.connect(self._on_debugger_ready)
        self._debugger_worker.process_exited.connect(self._on_debugger_ready) # when the process exits, the thread is non-blocked too so it's same as ready

    def _init_shell(self) -> None:
        master_fd, slave_fd = pty.openpty()
        self._debugger_worker.call_from_another_thread(self._debugger_worker.setup_shell, slave_fd)
        self._open_pty(master_fd)
    
    def _on_debugger_busy(self) -> None:
        """
        Callback - when the debugger becomes busy
        Makes the console read-only to prevent user input while the debugger is busy.
        """
        self.read_only = True
    
    def _on_debugger_ready(self) -> None:
        """
        Callback - when the debugger becomes non-blocked (ready)
        Makes the console editable again to allow user input.
        """
        self.read_only = False