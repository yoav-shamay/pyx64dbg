from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QWidget

from pyx64dbg.GUI.async_slot import async_slot
from pyx64dbg.GUI.debugger_worker import DebuggerWorker

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow


class DebugControlsView(QWidget):
    """
    This class defines the debug controls view widget in the GUI.
    Has buttons to manage the debugged process execution - Run, Stop, Step Into, Step Over, Step Out and Continue.
    """
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._register_callbacks()
        self._init_ui()
    
    def _register_callbacks(self) -> None:
        """
        Registers the debugger worker callbacks to update the view on various events.
        Enables/Disables buttons based on the process being available, busy, or exited.
        """
        self._debugger_worker.process_started.connect(self._on_debugger_ready)
        self._debugger_worker.debugger_ready.connect(self._on_debugger_ready)
        self._debugger_worker.process_exited.connect(self._on_process_exited)
        self._debugger_worker.file_selected.connect(self._on_process_exited)
        self._debugger_worker.debugger_busy.connect(self._on_debugger_busy)

    def _init_ui(self) -> None:
        """
        Initializes the UI of the view, creating the buttons and arranging them in a horizontal layout.
        Connects the buttons to their respective callbacks.
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0) # no need for top margins
        layout.setSpacing(8)

        # define every button and connect it to its callback
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
        # configure the buttons to have a fixed size policy, and add them to the layout with some spacing
        for button in buttons:
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setEnabled(False) # buttons are disabled until a file is selected
            layout.addWidget(button)

        # set the layout to have a stretch at the end to push the buttons to the left
        layout.addStretch(1)
        
    @async_slot
    async def _on_run(self) -> None:
        """
        Callback for when the "Run" button is clicked.
        Starts the debugged process.
        """
        await self._debugger_worker.call_async(self._debugger_worker.start_debugging)

    @async_slot
    async def _on_stop(self) -> None:
        """
        Callback for when the "Stop" button is clicked.
        Kills the debugged process.
        Doesn't use the method of the worker as it might be unavailable, so kills it directly in this thread.        
        """
        await self._main_window.force_kill_debugged_process()

    @async_slot
    async def _on_step_into(self) -> None:
        """
        Callback for when the "Step Into" button is clicked.
        Performs a single step into the debugged process.
        """
        await self._debugger_worker.call_async(self._debugger_worker.single_step)

    @async_slot
    async def _on_step_over(self) -> None:
        """
        Callback for when the "Step Over" button is clicked.
        Performs a single step over the debugged process.
        """
        await self._debugger_worker.call_async(self._debugger_worker.next_instruction)

    @async_slot
    async def _on_continue(self) -> None:
        """
        Callback for when the "Continue" button is clicked.
        Continues the debugged process.
        """
        await self._debugger_worker.call_async(self._debugger_worker.continue_execution)

    @async_slot
    async def _on_step_out(self) -> None:
        """
        Callback for when the "Step Out" button is clicked.
        Steps out of the current function in the debugged process.
        """
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
