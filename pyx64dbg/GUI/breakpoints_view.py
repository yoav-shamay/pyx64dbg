from __future__ import annotations

from PyQt6.QtWidgets import QWidget
from pyx64dbg.GUI.placeholders import PlaceholderTable


class BreakpointsView(PlaceholderTable):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(["Address", "Enabled", "Condition"], parent)
