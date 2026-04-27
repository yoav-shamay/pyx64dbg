from __future__ import annotations

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QDockWidget, QMainWindow, QTabWidget, QWidget

from pyx64dbg.GUI.breakpoints_view import BreakpointsView
from pyx64dbg.GUI.disassembly_view import DisassemblyView
from pyx64dbg.GUI.extended_registers_view import ExtendedRegistersView
from pyx64dbg.GUI.interactive_console_view import InteractiveConsoleView
from pyx64dbg.GUI.main_menu import MainMenu
from pyx64dbg.GUI.pty_stdio_view import PtyStdioView
from pyx64dbg.GUI.registers_view import RegistersView
from pyx64dbg.GUI.symbols_view import SymbolsView
from pyx64dbg.GUI.watch_view import WatchView


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PyX64Dbg")
        self.resize(1600, 1000)

        self._dock_actions: dict[str, QAction] = {}
        self._docks: dict[str, QDockWidget] = {}

        # Make the dock separators (margins) visible
        # TODO this is a temporary solution. We will have proper style sheet files but the widgets won't look like that in the end anyway.
        self.setStyleSheet("""
            QMainWindow::separator {
                background: #c0c0c0; 
                width: 2px; 
                height: 2px;
            }
            QMainWindow::separator:hover {
                background: #308cc6; /* Highlights blue when hovering to resize */
            }
        """)

        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )
        
        self.setDockNestingEnabled(True)
        self.setDocumentMode(True)
        self.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)

        # Ensure sidebars stay on the sides and bottom stretches across
        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.BottomDockWidgetArea)

        self._create_menus()
        self._register_all_views()
        # create the default windows state
        state_exists = self._load_layout()
        if not state_exists:
            self._create_default_layout()

    def _create_menus(self) -> None:
        self._main_menu = MainMenu(
            self,
            save_layout_callback=self._save_layout,
            reset_layout_callback=self._reset_layout,
        )

    def _register_view(self, key: str, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> None:
        dock = QDockWidget(title, self)
        dock.setObjectName(key)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(widget)

        action = dock.toggleViewAction()
        action.setText(title)
        self._main_menu.add_view_action(action)
        
        self.addDockWidget(area, dock)

        self._dock_actions[key] = action
        self._docks[key] = dock

    def _tabify_group(self, keys: list[str]) -> None:
        if len(keys) < 2: return
        anchor = self._docks[keys[0]]
        for key in keys[1:]:
            self.tabifyDockWidget(anchor, self._docks[key])
        anchor.raise_()
    
    def _register_all_views(self) -> None:
        self._register_view("symbols", "Symbols", SymbolsView(self), Qt.DockWidgetArea.LeftDockWidgetArea)
        self._register_view("watch", "Watch", WatchView(self), Qt.DockWidgetArea.LeftDockWidgetArea)
        self._register_view("breakpoints", "Breakpoints", BreakpointsView(self), Qt.DockWidgetArea.LeftDockWidgetArea)
        
        self._register_view("disassembly", "Disassembly", DisassemblyView(self), Qt.DockWidgetArea.LeftDockWidgetArea)
        
        self._register_view("registers", "Registers", RegistersView(self), Qt.DockWidgetArea.RightDockWidgetArea)
        self._register_view("extended_registers", "Extended Registers", ExtendedRegistersView(self), Qt.DockWidgetArea.RightDockWidgetArea)
        
        self._register_view("interactive_console", "Interactive Console", InteractiveConsoleView(self), Qt.DockWidgetArea.BottomDockWidgetArea)
        self._register_view("stdio_terminal", "PTY Stdio", PtyStdioView(self), Qt.DockWidgetArea.BottomDockWidgetArea)

    def _create_default_layout(self) -> None:
        # Create the initial layout by splitting and tabifying docks
        # first, split symbols to have interactive console below and stdio to the right of that
        # Do it before splitting symbols so the bottom stretches across the entire width
        self.splitDockWidget(self._docks["symbols"], self._docks["interactive_console"], Qt.Orientation.Vertical)
        self.splitDockWidget(self._docks["interactive_console"], self._docks["stdio_terminal"], Qt.Orientation.Horizontal)
        # now split symbols to be symbols | disassembly | registers from left to right
        self.splitDockWidget(self._docks["symbols"], self._docks["disassembly"], Qt.Orientation.Horizontal)
        self.splitDockWidget(self._docks["disassembly"], self._docks["registers"], Qt.Orientation.Horizontal)
        
        # Tabify related docks together
        self._tabify_group(["symbols", "watch", "breakpoints"])
        self._tabify_group(["registers", "extended_registers"])

        # Final Sizing
        self.resizeDocks(
            [self._docks["symbols"], self._docks["disassembly"], self._docks["registers"]],
            [300, 1000, 300],
            Qt.Orientation.Horizontal,
        )
        self.resizeDocks(
            [self._docks["disassembly"], self._docks["interactive_console"]],
            [750, 250],
            Qt.Orientation.Vertical,
        )
    
    def _save_layout(self) -> None:
        """
        Save the current dock layout to QSettings.
        This can be loaded later with load_settings() or reset to default with reset_layout().
        """
        settings = QSettings()
        settings.setValue("windowState", self.saveState())

    def _load_layout(self) -> None:
        """
        Load a previously saved dock layout from QSettings, if present.
        Returns True if a layout was successfully loaded, False otherwise (e.g. no saved layout or failed to restore).
        """
        settings = QSettings()

        state = settings.value("windowState")
        if state:
            self.restoreState(state)
            return True
        return False

    def _reset_layout(self) -> None:
        """Restore the default dock/tab arrangement created at startup."""
        self._create_default_layout()