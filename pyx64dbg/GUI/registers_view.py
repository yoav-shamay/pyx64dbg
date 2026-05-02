from __future__ import annotations

from PySide6.QtWidgets import QWidget

from pyx64dbg.GUI.placeholders import PlaceholderTable


class RegistersView(PlaceholderTable):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(["Register", "Value"], parent)