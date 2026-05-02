from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget


class PtyStdioView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_layout()
    
    def _init_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        placeholder = QWidget(self)
        placeholder.setStyleSheet("background-color: #1e1e1e;")
        layout.addWidget(placeholder)