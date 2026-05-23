from __future__ import annotations
from typing import TYPE_CHECKING

from pyx64dbg.GUI.async_slot import async_slot
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.GUI.pty_view import PtyView

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

class StdioView(PtyView):
    """
    This class defines the PTY stdio view widget in the GUI.
    Uses PtyView as base, and syncs the pty with the debugger worker.
    """
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
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
        Receives leftover data from the PTY to show in the terminal.
        Closes the PTY (without clearing the buffer, as the user might want to see the output of the process that just exited).
        """
        # write leftover data from the PTY to the terminal, so the user can see it after the process exits
        self._write_to_terminal(self._debugger_worker.get_leftover_data())
        self._close_pty()

    def _on_file_select(self) -> None:
        """
        Callback - when a new file is selected for debugging.
        Clears the terminal buffer, as the old output is no longer relevant.
        """
        self._clear_buffer()