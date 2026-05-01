from __future__ import annotations

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QAbstractItemView, QTableWidget, QTextEdit, QWidget


class PlaceholderTextEdit(QTextEdit):
    text = None # placeholder for the text to show in the text edit, to be set by the inheriting class
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlainText(self.text)
        self.setMinimumHeight(160)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

class PlaceholderInteractiveConsole(PlaceholderTextEdit):
    text = "Select a file to access the console."

class PlaceholderBreakpointsView(PlaceholderTextEdit):
    text = "Run a process to view breakpoints."

class PlaceholderRegistersView(PlaceholderTextEdit):
    text = "Run a process to view registers."

class PlaceholderSymbolsView(PlaceholderTextEdit):
    text = "Run a process to view symbols."

class PlaceholderExtendedRegistersView(PlaceholderTextEdit):
    text = "Run a process to view extended registers."

class PlaceholderDisassemblyView(PlaceholderTextEdit):
    text = "Run a process to view disassembly."

class PlaceholderPtyStdioView(PlaceholderTextEdit):
    text = "Run a process to access stdio."

class PlaceholderWatchView(PlaceholderTextEdit):
    text = "Run a process to access watch."

# temporary placeholder table class until we implement the real views, to avoid having to duplicate the same code in each view.
class PlaceholderTable(QTableWidget):
    def __init__(self, headers: list[str], parent: QWidget | None = None) -> None:
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)