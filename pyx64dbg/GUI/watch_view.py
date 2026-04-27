from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from pyx64dbg.GUI.placeholders import PlaceholderTable


class WatchView(PlaceholderTable):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(["Expression", "Value"], parent)