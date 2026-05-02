from __future__ import annotations

from PySide6.QtCore import QThread, Qt, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QMainWindow, QStackedWidget, QTabWidget, QWidget

from pyx64dbg.GUI.breakpoints_view import BreakpointsView
from pyx64dbg.GUI.debug_controls_view import DebugControlsView
from pyx64dbg.GUI.disassembly_view import DisassemblyView
from pyx64dbg.GUI.extended_registers_view import ExtendedRegistersView
from pyx64dbg.GUI.placeholders import (
    PlaceholderInteractiveConsole,
    PlaceholderBreakpointsView,
    PlaceholderRegistersView,
    PlaceholderSymbolsView,
    PlaceholderExtendedRegistersView,
    PlaceholderDisassemblyView,
    PlaceholderPtyStdioView,
    PlaceholderWatchView,
)
from pyx64dbg.GUI.top_menu import TopMenu
from pyx64dbg.GUI.pty_stdio_view import PtyStdioView
from pyx64dbg.GUI.registers_view import RegistersView
from pyx64dbg.GUI.symbols_view import SymbolsView
from pyx64dbg.GUI.watch_view import WatchView
from pyx64dbg.GUI.interactive_console_view import InteractiveConsoleView
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.GUI.async_slot import async_slot

import os, signal

class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._done_cleanup = False
        self.setWindowTitle("PyX64Dbg")
        self.resize(1600, 1000)

        self._create_debugger_worker_thread()
        self._init_ui()

    def _init_widgets(self):
        """
        Initialize all the widgets used in the main window, including both the real views and the placeholder views.
        Doesn't place them yet.
        """
        self._widgets = {}
        self._widgets["debug_controls"] = DebugControlsView(self)
        # initialize all placeholder widgets
        self._widgets["breakpoints_placeholder"] = PlaceholderBreakpointsView(self)
        self._widgets["registers_placeholder"] = PlaceholderRegistersView(self)
        self._widgets["extended_registers_placeholder"] = (
            PlaceholderExtendedRegistersView(self)
        )
        self._widgets["symbols_placeholder"] = PlaceholderSymbolsView(self)
        self._widgets["disassembly_placeholder"] = PlaceholderDisassemblyView(self)
        self._widgets["stdio_terminal_placeholder"] = PlaceholderPtyStdioView(self)
        self._widgets["watch_placeholder"] = PlaceholderWatchView(self)
        self._widgets["interactive_console_placeholder"] = (
            PlaceholderInteractiveConsole(self)
        )
        # initialize all real widgets
        self._widgets["breakpoints"] = BreakpointsView(self)
        self._widgets["registers"] = RegistersView(self)
        self._widgets["extended_registers"] = ExtendedRegistersView(self)
        self._widgets["symbols"] = SymbolsView(self)
        self._widgets["disassembly"] = DisassemblyView(self)
        self._widgets["stdio_terminal"] = PtyStdioView(self)
        self._widgets["watch"] = WatchView(self)
        self._widgets["interactive_console"] = InteractiveConsoleView(
            self, self.debugger_worker
        )

    def _init_ui(self) -> None:
        self._init_widgets()  # init all widgets first so we can reference them when placing them in the layout
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

        # set the dock options - allow nested (allows to split a region into several docks), tabbed (allow multiple docks in the same region to be tabbed), animated (animate dock movements)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )

        self.setDocumentMode(True)
        # set the tab position to all dock areas to be on top (north)
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        )

        self.file_path = None
        self.selected_file = False
        self.process_running = False

        # Create and start the debugger thread (before registering views!)

        self._create_top_menu()
        self._create_stacked_widgets()
        self._setup_docks()
        # create the default windows state
        state_exists = self._load_layout()
        if not state_exists:
            self._create_default_layout()

    def _create_debugger_worker_thread(self):
        # initialize the thread of the debugger
        self.debugger_thread = QThread(self)
        # initialize the worker
        self.debugger_worker = DebuggerWorker()
        # connect signals from the worker to the main window
        self.debugger_worker.process_started.connect(self._on_process_started)
        self.debugger_worker.process_exited.connect(self._on_process_exit)
        # move the worker to its thread and start the thread's event loop
        self.debugger_worker.moveToThread(self.debugger_thread)
        self.debugger_thread.start()

    def _create_top_menu(self) -> None:
        self._main_menu = TopMenu(self)

    def _place_widget_in_dock(
        self, key: str, title: str, widget: QWidget, area: Qt.DockWidgetArea
    ) -> None:
        dock = QDockWidget(title, self)
        dock.setObjectName(key)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(widget)

        action = dock.toggleViewAction()
        action.setText(title)
        self._main_menu.add_view_action(action)

        self.addDockWidget(area, dock)
        self._docks[key] = dock
    
    def _create_stack_widget(self, placeholder_widget : QWidget, real_widget : QWidget) -> QStackedWidget:
        stack = QStackedWidget(self)
        stack.addWidget(placeholder_widget)
        stack.addWidget(real_widget)
        stack.setCurrentIndex(0) # show the placeholder by default
        return stack
    
    def _create_stacked_widgets(self):
        self._widgets["breakpoints_stack"] = self._create_stack_widget(self._widgets["breakpoints_placeholder"], self._widgets["breakpoints"])
        self._widgets["registers_stack"] = self._create_stack_widget(self._widgets["registers_placeholder"], self._widgets["registers"])
        self._widgets["extended_registers_stack"] = self._create_stack_widget(self._widgets["extended_registers_placeholder"], self._widgets["extended_registers"])
        self._widgets["symbols_stack"] = self._create_stack_widget(self._widgets["symbols_placeholder"], self._widgets["symbols"])
        self._widgets["disassembly_stack"] = self._create_stack_widget(self._widgets["disassembly_placeholder"], self._widgets["disassembly"])
        self._widgets["stdio_terminal_stack"] = self._create_stack_widget(self._widgets["stdio_terminal_placeholder"], self._widgets["stdio_terminal"])
        self._widgets["watch_stack"] = self._create_stack_widget(self._widgets["watch_placeholder"], self._widgets["watch"])
        self._widgets["interactive_console_stack"] = self._create_stack_widget(self._widgets["interactive_console_placeholder"], self._widgets["interactive_console"])

    def _tabify_group(self, keys: list[str]) -> None:
        if len(keys) < 2:
            return
        anchor = self._docks[keys[0]]
        for key in keys[1:]:
            self.tabifyDockWidget(anchor, self._docks[key])
        anchor.raise_()

    def _setup_docks(self) -> None:
        """
        Place all widgets (the placeholder variant) in the layout inside the appropriate docks.
        """
        self._place_widget_in_dock(
            "debug_controls",
            "Debug Controls",
            self._widgets["debug_controls"],
            Qt.DockWidgetArea.TopDockWidgetArea,
        )
        self._place_widget_in_dock(
            "symbols",
            "Symbols",
            self._widgets["symbols_stack"],
            Qt.DockWidgetArea.LeftDockWidgetArea,
        )
        self._place_widget_in_dock(
            "watch",
            "Watch",
            self._widgets["watch_stack"],
            Qt.DockWidgetArea.LeftDockWidgetArea,
        )
        self._place_widget_in_dock(
            "breakpoints",
            "Breakpoints",
            self._widgets["breakpoints_stack"],
            Qt.DockWidgetArea.LeftDockWidgetArea,
        )

        self._place_widget_in_dock(
            "disassembly",
            "Disassembly",
            self._widgets["disassembly_stack"],
            Qt.DockWidgetArea.LeftDockWidgetArea,
        )

        self._place_widget_in_dock(
            "registers",
            "Registers",
            self._widgets["registers_stack"],
            Qt.DockWidgetArea.RightDockWidgetArea,
        )
        self._place_widget_in_dock(
            "extended_registers",
            "Extended Registers",
            self._widgets["extended_registers_stack"],
            Qt.DockWidgetArea.RightDockWidgetArea,
        )

        self._place_widget_in_dock(
            "interactive_console",
            "Interactive Console",
            self._widgets["interactive_console_stack"],
            Qt.DockWidgetArea.BottomDockWidgetArea,
        )
        self._place_widget_in_dock(
            "stdio_terminal",
            "PTY Stdio",
            self._widgets["stdio_terminal_stack"],
            Qt.DockWidgetArea.BottomDockWidgetArea,
        )

    def _create_default_layout(self) -> None:
        # Create the initial layout by splitting and tabifying docks
        # first, split debug controls to be above everything else
        self.splitDockWidget(
            self._docks["debug_controls"],
            self._docks["symbols"],
            Qt.Orientation.Vertical,
        )
        # then, split symbols to have interactive console below and stdio to the right of that
        # Do it before splitting symbols so the bottom stretches across the entire width
        self.splitDockWidget(
            self._docks["symbols"],
            self._docks["interactive_console"],
            Qt.Orientation.Vertical,
        )
        self.splitDockWidget(
            self._docks["interactive_console"],
            self._docks["stdio_terminal"],
            Qt.Orientation.Horizontal,
        )
        # now split symbols to be symbols | disassembly | registers from left to right
        self.splitDockWidget(
            self._docks["symbols"],
            self._docks["disassembly"],
            Qt.Orientation.Horizontal,
        )
        self.splitDockWidget(
            self._docks["disassembly"],
            self._docks["registers"],
            Qt.Orientation.Horizontal,
        )

        # Tabify related docks together
        self._tabify_group(["symbols", "watch", "breakpoints"])
        self._tabify_group(["registers", "extended_registers"])

        # Final Sizing
        # Symbols-Disassembly-Registers horizontal sizes
        self.resizeDocks(
            [
                self._docks["symbols"],
                self._docks["disassembly"],
                self._docks["registers"],
            ],
            [300, 1000, 300],
            Qt.Orientation.Horizontal,
        )
        # Debug Controls vs Symbol-Disassembly-Registers group vs Interactive Console-PTY vertical sizes
        self.resizeDocks(
            [
                self._docks["debug_controls"],
                self._docks["disassembly"],
                self._docks["interactive_console"],
            ],
            [100, 750, 550],
            Qt.Orientation.Vertical,
        )
        # Interactive Console vs PTY horizontal sizes
        self.resizeDocks(
            [self._docks["interactive_console"], self._docks["stdio_terminal"]],
            [700, 300],
            Qt.Orientation.Horizontal,
        )

    def save_layout(self) -> None:
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

    def reset_layout(self) -> None:
        """Restore the default dock/tab arrangement created at startup."""
        self._create_default_layout()

    def update_gui_on_file_select(self) -> None:
        """
        Update the UI to reflect that a file has been selected and is ready to be debugged, but no process is currently running.
        """
        # change to the real interactive console view and stdio terminal in the stack
        self._widgets["interactive_console_stack"].setCurrentIndex(1)
        self._widgets["stdio_terminal_stack"].setCurrentIndex(1)
        # On file select the process is stopped by default, so use the logic for this case
        self._on_process_exit()

    def _on_process_exit(self) -> None:
        """
        Update the UI to reflect that the debugged process has stopped.
        """
        # replace all views that are disabled with their placeholder versions
        self._widgets["breakpoints_stack"].setCurrentIndex(0)
        self._widgets["registers_stack"].setCurrentIndex(0)
        self._widgets["extended_registers_stack"].setCurrentIndex(0)
        self._widgets["symbols_stack"].setCurrentIndex(0)
        self._widgets["disassembly_stack"].setCurrentIndex(0)
        self._widgets["watch_stack"].setCurrentIndex(0)
        self._docks["debug_controls"].widget().set_process_stopped_state()

    def _on_process_started(self) -> None:
        """
        Update the UI to reflect that a debugged process has started.
        """
        # replace placeholder views with the real ones
        self._widgets["breakpoints_stack"].setCurrentIndex(1)
        self._widgets["registers_stack"].setCurrentIndex(1)
        self._widgets["extended_registers_stack"].setCurrentIndex(1)
        self._widgets["symbols_stack"].setCurrentIndex(1)
        self._widgets["disassembly_stack"].setCurrentIndex(1)
        self._widgets["watch_stack"].setCurrentIndex(1)
        self._docks["debug_controls"].widget().set_process_running_state()
    
    def _on_process_update(self, new_debugger_state):
        """
        Update the UI to reflect an update in the debugged process state (e.g. new breakpoint, new register values, etc).
        """
        self.debugger_state = new_debugger_state
        self._widgets["disassembly"].update_view(new_debugger_state)
    
    def closeEvent(self, event):
        # if we already done the cleanup, finish the event
        if self._done_cleanup:
            return
        # otherwise prevent the event from progressing before the async cleanup
        event.ignore()
        # run the closing cleanup async function, which will close it again in the end
        self._closing_cleanup(event)

    @async_slot
    async def _closing_cleanup(self, event) -> None:
        """
        Handles the window close event.
        Ensures the debugger thread is properly shut down.
        """
        # If the debugger thread is running, we need to stop it before closing the application to ensure a clean exit.
        if self.debugger_thread.isRunning():
            # kill the traced child manually, as the thread might be blocked waiting and won't be able to process a stop signal.
            if self.debugger_worker.debugger is not None:
                child_pid = self.debugger_worker.debugger.child_pid
                os.kill(child_pid, signal.SIGKILL)
            # tell the debugger worker to finish, shutting down the kernel. As the traced process is dead, it shouldn't be blocked.
            await self.debugger_worker.call_async(self.debugger_worker.handle_exit)
            # stop the debugger thread
            self.debugger_thread.quit()

        # close again, now with cleanup marked as done
        self._done_cleanup = True
        self.close()
