from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QWidget

from pyx64dbg.GUI.async_slot import async_slot
from pyx64dbg.GUI.debugger_worker import DebuggerWorker

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow


class DebugControlsView(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._register_callbacks()
        self._init_ui()
    
    def _register_callbacks(self) -> None:
        self._debugger_worker.process_started.connect(self._on_debugger_ready)
        self._debugger_worker.debugger_ready.connect(self._on_debugger_ready)
        self._debugger_worker.process_exited.connect(self._on_process_exited)
        self._debugger_worker.file_selected.connect(self._on_process_exited)
        self._debugger_worker.debugger_busy.connect(self._on_debugger_busy)

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.run_button = QPushButton("Run", self)
        self.run_button.clicked.connect(self._on_run)
        self.stop_button = QPushButton("Stop", self)
        self.stop_button.clicked.connect(self._on_stop)
        self.step_into_button = QPushButton("Step Into", self)
        self.step_into_button.clicked.connect(self._on_step_into)
        self.step_over_button = QPushButton("Step Over", self)
        self.step_over_button.clicked.connect(self._on_step_over)
        self.step_out_button = QPushButton("Step Out", self)
        self.step_out_button.clicked.connect(self._on_step_out)
        self.continue_button = QPushButton("Continue", self)
        self.continue_button.clicked.connect(self._on_continue)

        buttons = (
            self.run_button,
            self.stop_button,
            self.step_into_button,
            self.step_over_button,
            self.step_out_button,
            self.continue_button,
        )
        for button in buttons:
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setEnabled(False) # buttons are disabled until a file is selected
            layout.addWidget(button)

        layout.addStretch(1)
        
    @async_slot
    async def _on_run(self) -> None:
        await self._debugger_worker.call_async(self._debugger_worker.start_debugging)

    @async_slot
    async def _on_stop(self) -> None:
        # force kill the debugged process directly, as the thread might be blocked in os.wait
        await self._main_window.force_kill_debugged_process()

    @async_slot
    async def _on_step_into(self) -> None:
        await self._debugger_worker.call_async(self._debugger_worker.single_step)

    @async_slot
    async def _on_step_over(self) -> None:
        await self._debugger_worker.call_async(self._debugger_worker.next_instruction)

    @async_slot
    async def _on_continue(self) -> None:
        await self._debugger_worker.call_async(self._debugger_worker.continue_execution)

    @async_slot
    async def _on_step_out(self) -> None:
        await self._debugger_worker.call_async(self._debugger_worker.finish)

    def _on_process_exited(self) -> None:
        """
        Enable/Disable buttons based on the process isn't running (on exit / file selection)
        When the process is stopped, only the "Run" button should be enabled.
        """
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.step_into_button.setEnabled(False)
        self.step_over_button.setEnabled(False)
        self.continue_button.setEnabled(False)
        self.step_out_button.setEnabled(False)

    def _on_debugger_ready(self) -> None:
        """
        Enable/Disable buttons based on the process being running and available.
        Only the "Run" button should be disabled.
        """
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.step_into_button.setEnabled(True)
        self.step_over_button.setEnabled(True)
        self.continue_button.setEnabled(True)
        self.step_out_button.setEnabled(True)
    
    def _on_debugger_busy(self) -> None:
        """
        Enable/Disable buttons based on the debugger being busy.
        Only the "Stop" button should be enabled (as it's the only one that doesn't require the thread to be available)
        """
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.step_into_button.setEnabled(False)
        self.step_over_button.setEnabled(False)
        self.continue_button.setEnabled(False)
        self.step_out_button.setEnabled(False)
