from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QVBoxLayout, QWidget, QListWidget, QMenu
from PySide6.QtGui import QAction
from pyx64dbg.GUI.async_slot import async_slot
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.GUI.utils import prompt_for_expression

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

BP_SYMBOL = "🔴" # symbol that will appear before the breakpoint address in the list

class BreakpointsView(QWidget):
    def __init__(self, main_window : MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = self._main_window.debugger_worker
        self._register_callbacks()
        self._init_ui()
        self._load_qss()

    def _register_callbacks(self):
        self._debugger_worker.state_update.connect(self._on_state_update)
    
    def _load_qss(self):
        with open("pyx64dbg/GUI/styles/breakpoints_view.qss", "r") as f:
            self.setStyleSheet(f.read())
    
    def _init_ui(self):
        self._list_widget = QListWidget(self)
        self._list_widget.setAlternatingRowColors(True) # make it easier to read
        # register right click menu
        self._list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_widget.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list_widget)
    
    def _show_context_menu(self, pos):
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
        
        # Populate and Execute
        menu.addAction(add_action)
        menu.addAction(remove_action)

        menu.exec(self._list_widget.viewport().mapToGlobal(pos))
    
    @async_slot
    async def _add_breakpoint(self):
        # prompt the user to enter an address, as an expression
        address = await prompt_for_expression(self, "Add Breakpoint", "Address:", self._debugger_worker)
        if address is not None:
            await self._debugger_worker.call_async(self._debugger_worker.add_breakpoint, address)

    @async_slot
    async def _remove_selected_breakpoint(self):
        selected_breakpoint = self._list_widget.currentItem()
        if selected_breakpoint:
            bp_address = selected_breakpoint.data(Qt.ItemDataRole.UserRole)
            await self._debugger_worker.call_async(self._debugger_worker.remove_breakpoint, bp_address)
    
    def _set_table(self, breakpoints : list[int]):
        self._list_widget.clear()
        for bp in breakpoints:
            bp_text = f"{BP_SYMBOL} 0x{bp:016x}"  # show breakpoint symbol and address as 64-bit hex
            address_hex = f"0x{bp:016x}"
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.DisplayRole, bp_text)
            item.setData(Qt.ItemDataRole.ToolTipRole, address_hex) # show only address in tooltip
            item.setData(Qt.ItemDataRole.UserRole, bp) # store the breakpoint address in the user data to access later
            self._list_widget.addItem(item)


    def _on_state_update(self, debugger_state):
        breakpoints = debugger_state.breakpoints
        self._set_table(breakpoints)
        