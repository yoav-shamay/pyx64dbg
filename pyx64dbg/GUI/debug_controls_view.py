from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QWidget

from pyx64dbg.debugger import Debugger

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow


class DebugControlsView(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window = main_window
        self._debugger_worker = main_window.debugger_worker
        self._init_ui()

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
        self.continue_button = QPushButton("Continue", self)
        self.continue_button.clicked.connect(self._on_continue)
        self.step_out_button = QPushButton("Step Out", self)
        self.step_out_button.clicked.connect(self._on_step_out)

        buttons = (
            self.run_button,
            self.stop_button,
            self.step_into_button,
            self.step_over_button,
            self.continue_button,
            self.step_out_button,
        )
        for button in buttons:
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setEnabled(False) # buttons are disabled until a file is selected
            layout.addWidget(button)

        layout.addStretch(1)
        

    def _on_run(self) -> None:
        self._debugger_worker.call_from_another_thread(self._debugger_worker.start_debugging)

    def _on_stop(self) -> None:
        self._debugger_worker.call_from_another_thread(self._debugger_worker.stop_debugging)

    def _on_step_into(self) -> None:
        self._debugger_worker.call_from_another_thread(self._debugger_worker.single_step)

    def _on_step_over(self) -> None:
        self._debugger_worker.call_from_another_thread(self._debugger_worker.next_instruction)

    def _on_continue(self) -> None:
        self._debugger_worker.call_from_another_thread(self._debugger_worker.continue_execution)

    def _on_step_out(self) -> None:
        self._debugger_worker.call_from_another_thread(self._debugger_worker.finish)

    def set_process_stopped_state(self):
        """
        Enable/Disable buttons based on the process being stopped.
        When the process is stopped, only the "Run" button should be enabled.
        """
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.step_into_button.setEnabled(False)
        self.step_over_button.setEnabled(False)
        self.continue_button.setEnabled(False)
        self.step_out_button.setEnabled(False)

    def set_process_running_state(self):
        """
        Enable/Disable buttons based on the process being running.
        When the process is running, only the "Run" button should be disabled.
        """
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.step_into_button.setEnabled(True)
        self.step_over_button.setEnabled(True)
        self.continue_button.setEnabled(True)
        self.step_out_button.setEnabled(True)
