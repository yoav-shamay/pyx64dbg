from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTextEdit, QWidget


class PlaceholderTextEdit(QTextEdit):
    text = None # placeholder for the text to show in the text edit, to be set by the inheriting class
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlainText(self.text)
        self.setMinimumHeight(160)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

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
    text = "Select a file to access stdio."

class PlaceholderWatchView(PlaceholderTextEdit):
    text = "Run a process to access watch."