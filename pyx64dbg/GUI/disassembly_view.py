from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from pyx64dbg.GUI.placeholders import PlaceholderTextEdit


class DisassemblyView(PlaceholderTextEdit):
    text = "Disassembly view placeholder\n\nThe real instruction listing will appear here."