"""
This module defines placeholder widgets for the different views.
Those placeholders are shown when the process isn't running / file isn't selected, as the normal views are irrelevant.
"""
from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QTextEdit, QWidget


class PlaceholderTextEdit(QTextEdit):
    """
    General placeholder text edit widget, used as a base for all the specific placeholders.
    It is read-only,  and has a fixed text set by subclasses
    """
    text = None # text shown in the widgets, should be set by subclasses
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlainText(self.text)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.setFont(font) # set the font to a fixed-width font for better readability of the placeholder text

class PlaceholderBreakpointsView(PlaceholderTextEdit):
    """
    Placeholder for the breakpoints view, shown when no process is running.
    """
    text = "Run a process to view breakpoints."

class PlaceholderRegistersView(PlaceholderTextEdit):
    """
    Placeholder for the registers view, shown when no process is running.
    """
    text = "Run a process to view registers."

class PlaceholderSymbolsView(PlaceholderTextEdit):
    """
    Placeholder for the symbols view, shown when no process is running.
    """
    text = "Run a process to view symbols."

class PlaceholderExtendedRegistersView(PlaceholderTextEdit):
    """
    Placeholder for the extended registers view, shown when no process is running.
    """
    text = "Run a process to view extended registers."

class PlaceholderDisassemblyView(PlaceholderTextEdit):
    """
    Placeholder for the disassembly view, shown when no process is running.
    """
    text = "Run a process to view disassembly."

class PlaceholderPtyStdioView(PlaceholderTextEdit):
    """
    Placeholder for the stdio view, shown when no file is selected.
    """
    text = "Select a file to access stdio."

class PlaceholderWatchView(PlaceholderTextEdit):
    """
    Placeholder for the watch view, shown when no file is selected.
    """
    text = "Select a file to access watch."