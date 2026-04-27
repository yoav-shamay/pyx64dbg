from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from pyx64dbg.GUI.placeholders import PlaceholderTextEdit


class DisassemblyView(PlaceholderTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Disassembly view placeholder\n\nThe real instruction listing will appear here.",
            parent,
        )