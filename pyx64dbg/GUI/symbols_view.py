from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QAbstractItemView, QLabel, QHeaderView
from pyx64dbg.GUI.async_slot import async_slot
from pyx64dbg.symbols import Symbol, SymbolType

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow
    from pyx64dbg.GUI.debugger_worker import DebuggerWorker

class SymbolsView(QWidget):
    """
    This class defines the symbols view widget in the GUI.
    It shows the symbols of the debugged process, and allows navigating to a symbol in the disassembly view.
    """
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._register_callbacks()
        self._init_ui()
        self._load_qss()

    def _register_callbacks(self) -> None:
        """
        Registers the callbacks to update the view on various events.
        Only needs to show the symbols on the process start event, as the symbols won't change during execution.
        """
        self._debugger_worker.process_started.connect(self._on_process_start)
    
    def _load_qss(self) -> None:
        """
        Loads the QSS stylesheet from the symbols_view.qss file and applies it to the widget.s
        """
        with open(str(self._main_window.base_path / "styles" / "symbols_view.qss"), "r") as f:
            self.setStyleSheet(f.read())

    def _init_ui(self) -> None:
        """
        Initializes the UI components for the symbols view.
        Creates a table widget to display the symbols and their attributes.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 4) # 0 rows, 4 columns (Name, Address, Size, Type)
        self.table.setHorizontalHeaderLabels(["Name", "Address", "Size", "Type"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows) # selecting a cell highlights the entire row
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # don't allow editing cells
        self.table.verticalHeader().setVisible(False) # don't show row numbers
        self.table.setSortingEnabled(True) # allow sorting by clicking on column headers

        # configure the header (column widths)
        header = self.table.horizontalHeader()
        # make the 3 columns resize to content, and the name take the remaining space, as the name can be long and the others are relatively constant/short
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table)

    async def _show_symbols(self, symbols: list[Symbol]) -> None:
        """
        Populates the symbols table with the given list of symbols.
        """
        
        self.table.setSortingEnabled(False) # disable sorting while populating to avoid qt sorting every time
        self.table.setRowCount(0) # clear existing rows
        for symbol in symbols:
            if symbol.type == SymbolType.OTHER:
                continue # skip symbols that aren't functions or objects, as they are usually useless
            row = self.table.rowCount() # get current row index (current table row count)
            self.table.insertRow(row)
            
            # name item - only display role is needed as we don't need to know the symbol name to jump to it
            name_item = QTableWidgetItem()
            name_item.setData(Qt.ItemDataRole.DisplayRole, symbol.name)
            name_item.setData(Qt.ItemDataRole.ToolTipRole, symbol.name) # show full name in tooltip in case it's too long to fit in the cell
            self.table.setItem(row, 0, name_item)

            # address - has a display item for display and user item for logic
            addr_item = QTableWidgetItem()
            addr_item.setData(Qt.ItemDataRole.DisplayRole, hex(symbol.address))
            addr_item.setData(Qt.ItemDataRole.UserRole, symbol.address) 
            self.table.setItem(row, 1, addr_item)

            # size - has a display item for display and user item for logic
            size_item = QTableWidgetItem()
            size_item.setData(Qt.ItemDataRole.DisplayRole, str(symbol.size))
            size_item.setData(Qt.ItemDataRole.UserRole, symbol.size)
            self.table.setItem(row, 2, size_item)

            # type - has a display item for display and user item for logic (to allow checking if it's a function when double clicking)
            type_str = "Function" if symbol.type == SymbolType.FUNCTION else "Object"
            type_item = QTableWidgetItem()
            type_item.setData(Qt.ItemDataRole.DisplayRole, type_str)
            type_item.setData(Qt.ItemDataRole.UserRole, symbol.type)
            self.table.setItem(row, 3, type_item)

        self.table.setSortingEnabled(True) # re-enable sorting after populating
    
    @async_slot
    async def _on_process_start(self) -> None:
        """
        Callback - when a process starts.
        Gets the symbols from the debugger worker and shows them in the table.
        """
        # Call the worker asynchronously to get all symbol data
        symbols = await self._debugger_worker.call_async(self._debugger_worker.get_all_symbols)
        await self._show_symbols(symbols)
    
    @async_slot
    async def _on_cell_double_clicked(self, row: int, col: int) -> None:
        """
        Handles double clicking a cell.
        If it's a function, navigates to the disassembly view at the function's address.
        Otherwise, does nothing.
        Does nothing if the debugger is busy.
        """
        if self._main_window.debugger_busy:
            return # if the debugger is busy, don't try to jump as we can't call the thread
        # fetch the symbol type from the user data
        type_item = self.table.item(row, 3)
        is_function = type_item.data(Qt.ItemDataRole.UserRole) == SymbolType.FUNCTION
        # Check if the symbol is a function before jumping
        if not is_function:
            return  # Do nothing for objects or other non-code symbols
        # fetch the address and size from the user data
        addr_item = self.table.item(row, 1)
        address = addr_item.data(Qt.ItemDataRole.UserRole)
        size_item = self.table.item(row, 2)
        size = size_item.data(Qt.ItemDataRole.UserRole)
        # change disassembly view to disassemble the function memory range
        await self._main_window.widgets["disassembly"].make_disassemble_memory_range(address, address + size)