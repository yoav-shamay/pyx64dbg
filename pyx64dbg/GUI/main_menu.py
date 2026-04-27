from __future__ import annotations

import os
from typing import Callable

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFileDialog, QMainWindow, QMenu, QMessageBox


class MainMenu:
    def __init__(
        self,
        main_window: QMainWindow,
        save_layout_callback: Callable[[], None],
        reset_layout_callback: Callable[[], None],
    ) -> None:
        self._main_window = main_window
        self._save_layout_callback = save_layout_callback
        self._reset_layout_callback = reset_layout_callback

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
        self._open_action.triggered.connect(self.open_executable)
        self._file_menu.addAction(self._open_action)

        self._save_layout_action = QAction("Save Layout", self._main_window)
        self._save_layout_action.triggered.connect(self._save_layout_callback)
        self._window_menu.addAction(self._save_layout_action)

        self._reset_layout_action = QAction("Reset Layout", self._main_window)
        self._reset_layout_action.triggered.connect(self._reset_layout_callback)
        self._window_menu.addAction(self._reset_layout_action)

    def open_executable(self) -> None:
        """Placeholder File -> Open flow that currently only selects and validates an executable path."""
        selected_path, _ = QFileDialog.getOpenFileName(
            self._main_window,
            "Open Executable",
            "",
            "All Files (*)",
        )

        if not selected_path:
            return

        if not os.path.isfile(selected_path):
            QMessageBox.warning(self._main_window, "Invalid File", "The selected path is not a file.")
            return

        if not os.access(selected_path, os.X_OK):
            QMessageBox.warning(self._main_window, "Invalid Executable", "The selected file is not executable.")
            return

        QMessageBox.information(
            self._main_window,
            "Open Executable",
            f"Selected executable:\n{selected_path}\n\nPlaceholder: launching/debug attach is not implemented yet.",
        )