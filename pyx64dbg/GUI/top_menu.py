from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QFileDialog, QMessageBox

from pyx64dbg.GUI.async_slot import async_slot
from pyx64dbg.GUI.debugger_worker import DebuggerWorker

# we need it as main window imports top menu
if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow 


class TopMenu:
    """
    This class defines the top menu of the main window.
    Has File menu with an option to open a file,
    a Window menu with options to save and reset the layout.
    And a View menu, which is populated with actions to show/hide the different views
    """
    def __init__(
        self,
        main_window: MainWindow,
    ) -> None:
        self._main_window = main_window
        self._debugger_worker : DebuggerWorker = main_window.debugger_worker
        self._init_ui()
        self._create_actions()

    def _init_ui(self) -> None:
        """
        Initializes the UI of the top menu, creating the File, View and Window menus.
        """
        self._file_menu = self._main_window.menuBar().addMenu("&File")
        self._view_menu = self._main_window.menuBar().addMenu("&View")
        self._window_menu = self._main_window.menuBar().addMenu("&Window")

    def add_view_action(self, dock: QDockWidget, title: str) -> None:
        """
        A method to add an action tp show/hide a dock widget to the view menu.
        Should get the dock widget and its title.
        Called by the main window when creating the views.
        """

        action = dock.toggleViewAction()
        action.setText(title)
        self._view_menu.addAction(action)

    def _create_actions(self) -> None:
        """
        Create and wire File and Window menu actions.
        """
        self._open_action = QAction("Open", self._main_window)
        self._open_action.triggered.connect(self._open_executable)
        self._file_menu.addAction(self._open_action)

        self._save_layout_action = QAction("Save Layout", self._main_window)
        self._save_layout_action.triggered.connect(self._main_window.save_layout)
        self._window_menu.addAction(self._save_layout_action)

        self._reset_layout_action = QAction("Reset Layout", self._main_window)
        self._reset_layout_action.triggered.connect(self._main_window.create_default_layout)
        self._window_menu.addAction(self._reset_layout_action)

    @async_slot
    async def _open_executable(self) -> None:
        """
        Function to open a file dialog and select an executable to debug.
        Updates the state once a file is selected.
        """
        selected_path, _ = QFileDialog.getOpenFileName(
            self._main_window,
            "Open Executable", # window title
            "", # start in current directory
            "All Files (*)", # executables has no extension filter, so show all files
        )
        
        if not selected_path: # if we didn't select a file, do nothing
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
            # if there's a process running, force kill the current process, as the debugger might be blocked and the call won't register
            await self._main_window.force_kill_debugged_process()
        # update the file path in the debugger worker, which will emit a signal to inform the main window anyway
        await self._main_window.debugger_worker.call_async(self._debugger_worker.set_file_name, selected_path)