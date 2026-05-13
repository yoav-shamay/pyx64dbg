from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QAbstractItemView, QHeaderView, QToolBar, QInputDialog, QMenu)
from PySide6.QtGui import QAction
from pyx64dbg.GUI.async_slot import async_slot
from pyx64dbg.GUI.debugger_state import DebuggerState
from pyx64dbg.GUI.debugger_worker import DebuggerWorker

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

class WatchView(QWidget):
    """
    This class defines the watch view widget in the GUI.
    It allows the user to add watch expressions that are evaluated with the console context.
    The watch expressions persist across debugging sessions (but not evaluated when no process is running), but are cleared when a new file is selected.
    """
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._watch_expressions: list[str] = []
        self._register_callbacks()
        self._init_ui()
        self._load_qss()

    def _register_callbacks(self) -> None:
        """
        This method registers the necessary callbacks to update the view on various events.
        Resets watches when a new file is selected (as they probably aren't relevant), and refreshes on updates.
        """
        self._debugger_worker.file_selected.connect(self._reset_watches)
        self._debugger_worker.state_update.connect(self._on_debugger_update)

    def _init_ui(self) -> None:
        """
        Initializes the UI of the view.
        Creates a toolbar with an "Add Watch" button, and a table to show the watch expressions and their current values.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # no need for margins

        # Toolbar for adding watches
        self.toolbar = QToolBar()
        add_action = QAction("+", self)
        add_action.triggered.connect(self._add_watch_prompt)
        self.toolbar.addAction(add_action)
        layout.addWidget(self.toolbar)

        # Table Setup
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Expression", "Value"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows) # select entire rows
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # make table read-only
        self.table.verticalHeader().setVisible(False) # hide row numbers
        # custom right click menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        # configure the header (column widths) - both columns take equal space
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.table.cellDoubleClicked.connect(self._on_double_click) # double clicking a watch allows editing it

        layout.addWidget(self.table)

    def _load_qss(self) -> None:
        """
        Loads the QSS stylesheet from the watch_view.qss file and applies it to the widget.
        """
        with open(str(self._main_window.base_path / "styles" / "watch_view.qss"), "r") as f:
            self.setStyleSheet(f.read())

    @async_slot
    async def _add_watch_prompt(self) -> None:
        """
        Called when clicking the "+" button in the toolbar or in the context menu.
        Prompts the user for a watch expression and adds it to the watch list.
        Refreshes the list to evaluate the new watch and show its value.
        """
        expr, ok = QInputDialog.getText(self, "Add Watch", "Enter expression:")
        if ok and expr.strip(): # if the user clicked OK and the expression is not empty
            self._watch_expressions.append(expr.strip())
            await self._refresh_watches()

    def _show_context_menu(self, position: QPoint) -> None:
        """
        Called when the user right clicks.
        Shows a context menu with options to add, remove and edit watches.
        The remove and edit options are disabled if no watch is selected.
        """
        menu = QMenu()
        
        # Create Actions
        add_action = QAction("Add Watch", self)
        remove_action = QAction("Remove Watch", self)
        edit_action = QAction("Edit Watch", self)
        
        # setup binds
        add_action.triggered.connect(self._add_watch_prompt)
        remove_action.triggered.connect(self._remove_selected_watch)
        edit_action.triggered.connect(self._edit_selected_watch)
        
        # Disable "Remove" and "Edit" if nothing is actually selected
        selected_items = self.table.selectedItems()
        remove_action.setEnabled(len(selected_items) > 0)
        edit_action.setEnabled(len(selected_items) > 0)
        
        # Populate
        menu.addAction(add_action)
        menu.addAction(remove_action)
        menu.addAction(edit_action)

        # Execute the menu
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    @async_slot
    async def _on_debugger_update(self, debugger_state: DebuggerState) -> None:
        """
        Callback to when the debugger updates, just calls refresh watch.
        """
        await self._refresh_watches()

    async def _refresh_watches(self) -> None:
        """
        Evaluates all watch expressions and updates the table with their current values.
        """
        # set the table row count to the number of watch expressions
        self.table.setRowCount(len(self._watch_expressions))
        for row, expr in enumerate(self._watch_expressions):
            if not self._main_window.debugger_busy and self._main_window.process_running:
                # only try to evaluate if the debugger thread isn't blocked and the process is running
                try:
                    eval_value = await self._debugger_worker.call_async(self._debugger_worker.evaluate_expression, expr)
                    value = repr(eval_value) # repr for display of values instead of str as it showcases the object better
                except Exception as e:
                    value = f"{e.__class__.__name__}: {str(e)}" # show reduced exception form
            else:
                value = "" # show an empty value if we can't evaluate
            # expression item
            expr_item = QTableWidgetItem()
            expr_item.setData(Qt.ItemDataRole.DisplayRole, expr)
            expr_item.setData(Qt.ItemDataRole.ToolTipRole, expr) # show full expression in tooltip in case it's too long to fit in the cell
            self.table.setItem(row, 0, expr_item)
            # value item
            value_item = QTableWidgetItem()
            value_item.setData(Qt.ItemDataRole.DisplayRole, value)
            value_item.setData(Qt.ItemDataRole.ToolTipRole, value) # show full value in tooltip in case it's too long to fit in the cell
            self.table.setItem(row, 1, value_item)
    
    def _reset_watches(self):
        """
        Clears all watches when a new file is selected, as they won't be relevant anymore.
        """
        self._watch_expressions.clear()
        self.table.setRowCount(0) # clear the table
    
    @async_slot
    async def _remove_selected_watch(self):
        """
        Called from the right click menu.
        Remove the selected watch in the table
        """
        row = self.table.currentRow()
        self._watch_expressions.pop(row)
        await self._refresh_watches()
    
    @async_slot
    async def _edit_selected_watch(self):
        """
        Called from the right click menu or on double click.
        Edit the selected watch in the table
        """
        row = self.table.currentRow()
        current_expr = self._watch_expressions[row]
        new_expr, ok = QInputDialog.getText(self, "Edit Watch", "Edit expression:", text=current_expr)
        if ok and new_expr.strip(): # if the user clicked OK and the expression is not empty
            self._watch_expressions[row] = new_expr.strip()
            await self._refresh_watches()
    
    @async_slot
    async def _on_double_click(self, row: int, column: int) -> None:
        """
        Double clicking a watch allows editing it, just calls the edit function for the selected watch
        """
        await self._edit_selected_watch()