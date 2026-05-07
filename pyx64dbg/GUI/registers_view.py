from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QWidget, QTableWidgetItem, QVBoxLayout
from PySide6.QtGui import QFont

from pyx64dbg.GUI.debugger_state import DebuggerState
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.GUI.utils import prompt_for_expression
from pyx64dbg.GUI.async_slot import async_slot

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow


class RegistersView(QWidget):
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._register_callbacks()
        self._init_ui()
        self._load_qss()
    
    def _load_qss(self):
        with open("pyx64dbg/GUI/styles/registers_view.qss", "r") as f:
            self.setStyleSheet(f.read())
    
    def _init_ui(self) -> None:
        self._table = QTableWidget(0, 3, self)
        self._table.setHorizontalHeaderLabels(["Register", "Value (hex)", "Value (dec)"])
        self._table.verticalHeader().setVisible(False) # hide row numbers
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # make table read-only
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows) # select entire rows when clicking a cell
        self._table.setSortingEnabled(False) # disable sorting
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked) # allow editing register values by double clicking a cell
        # make first col (name) fit contents as it's the shortest, and the other two take the remaining space equally
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        # add the table to the widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)

        # use Consolas monospace for font for the numbers
        # needs to be declared here as qss can't distinguish between columns
        self._values_font = QFont("Consolas", 10)
        self._values_font.setStyleHint(QFont.StyleHint.Monospace)

    def _register_callbacks(self):
        self._debugger_worker.state_update.connect(self._on_state_update)

    def _place_regs_in_table(self, regs: dict[str, bytes]) -> None:
        self._table.setRowCount(len(regs)) # clear the table
        for index, (reg_name, reg_value) in enumerate(regs.items()):
            name_col = QTableWidgetItem()
            name_col.setData(Qt.ItemDataRole.DisplayRole, reg_name)

            value_int = int.from_bytes(reg_value, byteorder="little")
            value_hex_str = f"0x{value_int:016x}"
            value_dec_str = str(value_int)

            value_hex_col = QTableWidgetItem()
            value_hex_col.setData(Qt.ItemDataRole.DisplayRole, value_hex_str)
            value_hex_col.setData(Qt.ItemDataRole.ToolTipRole, value_hex_str) # also show value in tooltip
            value_hex_col.setFont(self._values_font) # use monospace font for hex values

            value_dec_col = QTableWidgetItem()
            value_dec_col.setData(Qt.ItemDataRole.DisplayRole, value_dec_str)
            value_dec_col.setData(Qt.ItemDataRole.ToolTipRole, value_dec_str) # also show value in tooltip
            value_dec_col.setFont(self._values_font) # use monospace font for decimal values

            self._table.setItem(index, 0, name_col)
            self._table.setItem(index, 1, value_hex_col)
            self._table.setItem(index, 2, value_dec_col)
            
        
    def _on_state_update(self, state: DebuggerState) -> None:
        regs = state.standard_regs
        self._place_regs_in_table(regs)
    
    @async_slot
    async def _on_cell_double_clicked(self, row: int, col: int) -> None:
        if self._main_window.debugger_busy:
            return # if the debugger is busy, don't allow editing as we can't call the thread
        reg_name = self._table.item(row, 0).text()
        if col == 2:
            start_val = self._table.item(row, 2).text() # show decimal value if user double clicked the decimal column
        else:
            start_val = self._table.item(row, 1).text() # otherwise show hex value (default)

        # prompt the user to enter a new value for the register, showing the current value in
        new_value = await prompt_for_expression(
            self,
            "Edit Register Value",
            f"Enter new value for {reg_name}:",
            self._debugger_worker,
            start_val
        )
        if new_value is not None:
            await self._debugger_worker.call_async(self._debugger_worker.set_register, reg_name, new_value)
