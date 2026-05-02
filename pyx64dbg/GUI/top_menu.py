from __future__ import annotations

import os

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMenu, QMessageBox

from async_slot import async_slot


class TopMenu:
    def __init__(
        self,
        main_window: QMainWindow,
    ) -> None:
        self._main_window = main_window
        self._debugger_worker = main_window.debugger_worker
        self._file_menu = self._main_window.menuBar().addMenu("&File")
        self._view_menu = self._main_window.menuBar().addMenu("&View")
        self._window_menu = self._main_window.menuBar().addMenu("&Window")

        self._create_core_actions()

    @property
    def view_menu(self) -> QMenu:
        return self._view_menu

    def add_view_action(self, action: QAction) -> None:
        self._view_menu.addAction(action)

    def _create_core_actions(self) -> None:
        """Create and wire File and Window menu actions."""
        self._open_action = QAction("Open", self._main_window)
        self._open_action.triggered.connect(self._open_executable)
        self._file_menu.addAction(self._open_action)

        self._save_layout_action = QAction("Save Layout", self._main_window)
        self._save_layout_action.triggered.connect(self._main_window.save_layout)
        self._window_menu.addAction(self._save_layout_action)

        self._reset_layout_action = QAction("Reset Layout", self._main_window)
        self._reset_layout_action.triggered.connect(self._main_window.reset_layout)
        self._window_menu.addAction(self._reset_layout_action)

    @async_slot
    async def _open_executable(self) -> None:
        """
        Function to open a file dialog and select an executable to debug.
        Updates the state once a file is selected.
        """
        selected_path, _ = QFileDialog.getOpenFileName(
            self._main_window,
            "Open Executable",
            "",
            "All Files (*)",
        )
        
        if not selected_path:
            return

        # Check if a file is selcted (not a directory)
        if not os.path.isfile(selected_path):
            QMessageBox.warning(self._main_window, "Invalid File", "The selected path is not a file.")
            return

        # check if selected file has executable permissions. Otherwise we won't be able to run it.
        if not os.access(selected_path, os.X_OK):
            QMessageBox.warning(self._main_window, "Invalid Executable", "The selected file is not executable.")
            return
        if self._main_window.process_running:
            # if a process is already running, kill it before opening a new one.
            await self._debugger_worker.call_async(self._debugger_worker.stop_debugging)
            # update all widgets to reflect that no process is running
            self._main_window.update_gui_on_process_stop()
        # update the file path in the debugger worker
        await self._main_window.debugger_worker.call_async(self._debugger_worker.set_file_name, selected_path)
        # update file path in the main window and mark that a file has been selected and no process is currently running
        self._main_window.file_path = selected_path
        self._main_window.selected_file = True
        self._main_window.process_running = False
        self._main_window.update_gui_on_file_select()