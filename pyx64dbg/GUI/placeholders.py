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


class PlaceholderTable(QTableWidget):
    def __init__(self, headers: list[str], parent: QWidget | None = None) -> None:
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setMinimumHeight(160)