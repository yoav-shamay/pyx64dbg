from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QListWidgetItem, QToolBar, QVBoxLayout, QWidget, QListWidget, QMenu
from PySide6.QtGui import QAction
from pyx64dbg.GUI.async_slot import async_slot
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.GUI.utils import prompt_for_expression
from pyx64dbg.GUI.debugger_state import DebuggerState

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

BP_SYMBOL = "🔴" # symbol that will appear before the breakpoint address in the list

class BreakpointsView(QWidget):
    """
    This class defines the breakpoints view widget in the GUI.
    Shows a list of the current breakpoints, and allows to add/remove breakpoints.
    Consists of a "+" button and a list of the breakpoints.
    """
    def __init__(self, main_window : MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = self._main_window.debugger_worker
        self._register_callbacks()
        self._init_ui()
        self._load_qss()

    def _register_callbacks(self) -> None:
        """
        Registers the debugger worker callbacks to update the view on various events.
        """
        self._debugger_worker.state_update.connect(self._on_state_update)
        self._debugger_worker.debugger_busy.connect(self._on_debugger_busy)
        self._debugger_worker.debugger_ready.connect(self._on_debugger_ready)
    
    def _load_qss(self) -> None:
        """
        Loads the style sheet for the view from the breakpoints_view.qss file.
        """
        with open(str(self._main_window.base_path / "styles" / "breakpoints_view.qss"), "r") as f:
            self.setStyleSheet(f.read())
    
    def _init_ui(self) -> None:
        """
        Initializes the UI of the view, creating the toolbar and the list widget.
        """
        # toolbar with a + button
        self._toolbar = QToolBar()
        self._add_action = QAction("+", self)
        self._add_action.triggered.connect(self._add_breakpoint)
        self._toolbar.addAction(self._add_action)
        # list widget with breakpoints
        self._list_widget = QListWidget(self)
        self._list_widget.setAlternatingRowColors(True) # make it easier to read
        # register right click menu
        self._list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_widget.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._list_widget)
    
    def _show_context_menu(self, pos: QPoint) -> None:
        """
        Shows the context menu when right clicking on a breakpoint in the list.
        Allows to remove the selected breakpoint, or add a new one.
        """
        menu = QMenu()
        
        # Create Actions
        add_action = QAction("Add Breakpoint", self)
        remove_action = QAction("Remove Breakpoint", self)
        
        # setup binds
        add_action.triggered.connect(self._add_breakpoint)
        remove_action.triggered.connect(self._remove_selected_breakpoint)
        
        # Disable "Remove" if nothing is actually selected
        selected_items = self._list_widget.selectedItems()
        remove_action.setEnabled(len(selected_items) > 0)

        # Disable both if the debugger is busy, as we won't be able to call the thread to add/remove breakpoints
        if self._main_window.debugger_busy:
            add_action.setEnabled(False)
            remove_action.setEnabled(False)
        
        # add the actions to the menu
        menu.addAction(add_action)
        menu.addAction(remove_action)

        # show the menu
        menu.exec(self._list_widget.viewport().mapToGlobal(pos))
    
    @async_slot
    async def _add_breakpoint(self) -> None:
        """
        Called when the user clicks the "Add Breakpoint" button or the corresponding context menu action.
        Prompts the user to enter an address as an expression, and adds a breakpoint at the given address.
        """
        # prompt the user to enter an address, as an expression
        address = await prompt_for_expression(self, "Add Breakpoint", "Address:", self._debugger_worker)
        if address is not None:
            await self._debugger_worker.call_async(self._debugger_worker.add_breakpoint, address)

    @async_slot
    async def _remove_selected_breakpoint(self) -> None:
        """
        Called when the user selects a breakpoint and chooses to remove it.
        Removes the selected breakpoint.
        """
        selected_breakpoint = self._list_widget.currentItem()
        if selected_breakpoint:
            bp_address = selected_breakpoint.data(Qt.ItemDataRole.UserRole)
            await self._debugger_worker.call_async(self._debugger_worker.remove_breakpoint, bp_address)
    
    def _fill_list(self, breakpoints : list[int]) -> None:
        """
        Fills the breakpoints list widget with the given breakpoints.
        """
        self._list_widget.clear() # clear the existing breakpoints
        for bp in breakpoints:
            bp_text = f"{BP_SYMBOL} 0x{bp:016x}"  # show breakpoint symbol and address as 64-bit hex
            address_hex = f"0x{bp:016x}"
            # create the list item, set its data and add it to the list
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, bp_text)
            item.setData(Qt.ItemDataRole.ToolTipRole, address_hex) # show only address in tooltip
            item.setData(Qt.ItemDataRole.UserRole, bp) # store the breakpoint address in the user data to access later
            self._list_widget.addItem(item)


    def _on_state_update(self, debugger_state: DebuggerState) -> None:
        """
        Callback when the debugger state updates.
        Updates the breakpoints list with the new breakpoints from the state.
        """
        breakpoints = debugger_state.breakpoints
        self._fill_list(breakpoints)
        
    def _on_debugger_busy(self):
        """
        Callback when the debugger is busy (when waiting for a movement to finish).
        Disables the add breakpoint button.
        """
        self._add_action.setEnabled(False)
    
    def _on_debugger_ready(self):
        """
        Callback when the debugger is ready (when it's not busy and can accept operations).
        Enables the add breakpoint button.
        """
        self._add_action.setEnabled(True)
