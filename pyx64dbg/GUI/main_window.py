from __future__ import annotations

from PySide6.QtCore import QThread, Qt, QSettings
from PySide6.QtGui import QIcon, QCloseEvent
from PySide6.QtWidgets import QDockWidget, QMainWindow, QStackedWidget, QTabWidget, QWidget

from pyx64dbg.GUI.breakpoints_view import BreakpointsView
from pyx64dbg.GUI.debug_controls_view import DebugControlsView
from pyx64dbg.GUI.disassembly_view import DisassemblyView
from pyx64dbg.GUI.extended_registers_view import ExtendedRegistersView
from pyx64dbg.GUI.placeholders import (
    PlaceholderBreakpointsView,
    PlaceholderRegistersView,
    PlaceholderSymbolsView,
    PlaceholderExtendedRegistersView,
    PlaceholderDisassemblyView,
    PlaceholderPtyStdioView,
    PlaceholderWatchView,
)
from pyx64dbg.GUI.top_menu import TopMenu
from pyx64dbg.GUI.stdio_view import StdioView
from pyx64dbg.GUI.registers_view import RegistersView
from pyx64dbg.GUI.symbols_view import SymbolsView
from pyx64dbg.GUI.watch_view import WatchView
from pyx64dbg.GUI.interactive_console_view import InteractiveConsoleView
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.GUI.async_slot import async_slot

import os, signal
from pathlib import Path

class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.debugger_busy = False # whether the debugger worker is currently busy in a blocking wait call
        self.process_running: bool = False # whether a process is running or not
        self.base_path: Path = Path(__file__).parent # base path of the GUI directory, used for assets reference
        self._done_cleanup: bool = False # whether we already done the cleanup in the clos  event
        self.setWindowIcon(QIcon(str(self.base_path / "assets" / "icon.svg")))
        self.setWindowTitle("PyX64Dbg")
        self.resize(1280, 720) # a reasonable default size for non-maximized start (for example if the user unmaximizes the window)
        self._create_debugger_worker_thread_and_connect_init_ui()

    def _init_widgets(self) -> None:
        """
        Initialize all the widgets used in the main window, including both the real views and the placeholder views.
        Doesn't place them yet.
        """
        self.widgets: dict[str, QWidget] = {}
        self.widgets["debug_controls"] = DebugControlsView(self)
        # initialize all placeholder widgets
        self.widgets["breakpoints_placeholder"] = PlaceholderBreakpointsView(self)
        self.widgets["registers_placeholder"] = PlaceholderRegistersView(self)
        self.widgets["extended_registers_placeholder"] = (
            PlaceholderExtendedRegistersView(self)
        )
        self.widgets["symbols_placeholder"] = PlaceholderSymbolsView(self)
        self.widgets["disassembly_placeholder"] = PlaceholderDisassemblyView(self)
        self.widgets["stdio_terminal_placeholder"] = PlaceholderPtyStdioView(self)
        self.widgets["watch_placeholder"] = PlaceholderWatchView(self)
        # initialize all real widgets
        self.widgets["breakpoints"] = BreakpointsView(self)
        self.widgets["registers"] = RegistersView(self)
        self.widgets["extended_registers"] = ExtendedRegistersView(self)
        self.widgets["symbols"] = SymbolsView(self)
        self.widgets["disassembly"] = DisassemblyView(self)
        self.widgets["stdio_terminal"] = StdioView(self)
        self.widgets["watch"] = WatchView(self)
        self.widgets["interactive_console"] = InteractiveConsoleView(self)
    
    def _load_qss(self):
        """
        Loads the style sheet for the main window from the main_window.qss file.
        """
        with open(str(self.base_path / "styles" / "main_window.qss"), "r") as f:
            self.setStyleSheet(f.read())

    def _init_ui(self) -> None:
        """
        Initialize the user interface for the main window.
        Sets up widgets and docks.
        Called after the debugger worker thread finishes initialization.
        """
        self._init_widgets()  # init all widgets first so we can reference them when placing them in the layout
        self._docks: dict[str, QDockWidget] = {}
        # load main_window.qss
        self._load_qss()
        # set the dock options
        # allow nested (allows to split a region into several docks)
        # tabbed (allow multiple docks in the same region to be tabbed)
        # animated (animate dock movements)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
        )

        # set the tab position to all dock areas to be on top (north)
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        )
        self._top_menu = TopMenu(self)
        self._create_stacked_widgets()
        self._setup_docks()
        # load a saved state, or create the default layout if no saved state exists
        state_exists = self._load_layout()
        if not state_exists:
            self._create_default_layout()
        self.showMaximized() # show the window maximized after we finished initalization

    def _create_debugger_worker_thread_and_connect_init_ui(self) -> None:
        """
        Initializes the debugger worker thread.
        Connects the _init_ui method to start after the thread is running, so we can safely call methods of the worker during the UI initialization.
        """
        # initialize the thread of the debugger
        self.debugger_thread = QThread(self)
        # initialize the worker
        self.debugger_worker = DebuggerWorker()
        # connect signals from the worker to the main window
        self.debugger_worker.process_started.connect(self._on_process_started)
        self.debugger_worker.process_exited.connect(self._on_process_exit)
        self.debugger_worker.file_selected.connect(self._on_file_select)
        self.debugger_worker.debugger_busy.connect(self._on_debugger_busy)
        self.debugger_worker.debugger_ready.connect(self._on_debugger_ready)
        # move the worker to its thread and start the thread's event loop
        self.debugger_worker.moveToThread(self.debugger_thread)
        self.debugger_thread.started.connect(self._init_ui) # init the UI only after the debugger thread is running so we can call it safely
        self.debugger_thread.started.connect(self.debugger_worker.start_asyncio_loop) # start the asyncio loop in the debugger thread when it starts
        self.debugger_thread.start()

    def _place_widget_in_dock(
        self, key: str, title: str, widget: QWidget, area: Qt.DockWidgetArea
    ) -> None:
        """
        Helper method to place a widget inside a dock with the given title and area.
        Creates the dock, adds the widget, saves it in the dictionary, and adds the toggle view action to the top menu.
        """
        dock = QDockWidget(title, self)
        dock.setObjectName(key)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(widget)
        self._top_menu.add_view_action(dock, title)

        self.addDockWidget(area, dock)
        self._docks[key] = dock
    
    def _create_stack_widget(self, placeholder_widget : QWidget, real_widget : QWidget) -> QStackedWidget:
        """
        Creates a stack widget with the given placeholder widget and real widget.
        The placeholder widget is shown by default.
        """
        stack = QStackedWidget(self)
        stack.addWidget(placeholder_widget)
        stack.addWidget(real_widget)
        stack.setCurrentIndex(0) # show the placeholder by default
        return stack
    
    def _create_stacked_widgets(self) -> None:
        """
        Initializes all the stacked widgets used in the window.
        """
        self.widgets["breakpoints_stack"] = self._create_stack_widget(self.widgets["breakpoints_placeholder"], self.widgets["breakpoints"])
        self.widgets["registers_stack"] = self._create_stack_widget(self.widgets["registers_placeholder"], self.widgets["registers"])
        self.widgets["extended_registers_stack"] = self._create_stack_widget(self.widgets["extended_registers_placeholder"], self.widgets["extended_registers"])
        self.widgets["symbols_stack"] = self._create_stack_widget(self.widgets["symbols_placeholder"], self.widgets["symbols"])
        self.widgets["disassembly_stack"] = self._create_stack_widget(self.widgets["disassembly_placeholder"], self.widgets["disassembly"])
        self.widgets["stdio_terminal_stack"] = self._create_stack_widget(self.widgets["stdio_terminal_placeholder"], self.widgets["stdio_terminal"])
        self.widgets["watch_stack"] = self._create_stack_widget(self.widgets["watch_placeholder"], self.widgets["watch"])

    def _tabify_group(self, keys: list[str]) -> None:
        """
        Takes a group of docks identified by their keys, and tabifies them together in the order of the keys.
        """
        if len(keys) < 2:
            return
        anchor = self._docks[keys[0]]
        for key in keys[1:]:
            self.tabifyDockWidget(anchor, self._docks[key])
        anchor.raise_() # make sure the first one is the active tab

    def _setup_docks(self) -> None:
        """
        Place all widgets (the placeholder variant) in the layout inside docks.
        """
        self._place_widget_in_dock(
            "debug_controls",
            "Debug Controls",
            self.widgets["debug_controls"],
            Qt.DockWidgetArea.TopDockWidgetArea,
        )
        self._place_widget_in_dock(
            "symbols",
            "Symbols",
            self.widgets["symbols_stack"],
            Qt.DockWidgetArea.LeftDockWidgetArea,
        )
        self._place_widget_in_dock(
            "watch",
            "Watch",
            self.widgets["watch_stack"],
            Qt.DockWidgetArea.LeftDockWidgetArea,
        )
        self._place_widget_in_dock(
            "breakpoints",
            "Breakpoints",
            self.widgets["breakpoints_stack"],
            Qt.DockWidgetArea.LeftDockWidgetArea,
        )

        self._place_widget_in_dock(
            "disassembly",
            "Disassembly",
            self.widgets["disassembly_stack"],
            Qt.DockWidgetArea.LeftDockWidgetArea,
        )

        self._place_widget_in_dock(
            "registers",
            "Registers",
            self.widgets["registers_stack"],
            Qt.DockWidgetArea.RightDockWidgetArea,
        )
        self._place_widget_in_dock(
            "extended_registers",
            "Extended Registers",
            self.widgets["extended_registers_stack"],
            Qt.DockWidgetArea.RightDockWidgetArea,
        )

        self._place_widget_in_dock(
            "interactive_console",
            "Interactive Console",
            self.widgets["interactive_console"],
            Qt.DockWidgetArea.BottomDockWidgetArea,
        )
        self._place_widget_in_dock(
            "stdio_terminal",
            "Stdio",
            self.widgets["stdio_terminal_stack"],
            Qt.DockWidgetArea.BottomDockWidgetArea,
        )

    def _create_default_layout(self) -> None:
        """
        Creates the default window layout.
        Uses splitting and tabification of docks to create the default arrangement of the views.
        Sets the sizes to the default ratios.
        """
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
            [23, 54, 23],
            Qt.Orientation.Horizontal,
        )
        # Debug Controls vs Symbol-Disassembly-Registers group vs Interactive Console-PTY vertical sizes
        self.resizeDocks(
            [
                self._docks["debug_controls"],
                self._docks["disassembly"],
                self._docks["interactive_console"],
            ],
            [7, 53, 40],
            Qt.Orientation.Vertical,
        )
        # Interactive Console vs PTY horizontal sizes
        self.resizeDocks(
            [self._docks["interactive_console"], self._docks["stdio_terminal"]],
            [70, 30],
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
        """
        Change the layout to the default layout.
        """
        self._create_default_layout()

    def _on_file_select(self) -> None:
        """
        Callback - update the UI to reflect that a file has been selected and is ready to be debugged, but no process is currently running.
        """
        # change to the real stdio terminal and watch in the stack
        self.widgets["stdio_terminal_stack"].setCurrentIndex(1)
        self.widgets["watch_stack"].setCurrentIndex(1)


    def _on_process_exit(self) -> None:
        """
        Callback - update the UI to reflect that the debugged process has stopped.
        """
        # replace all views that are disabled with their placeholder versions
        self.widgets["breakpoints_stack"].setCurrentIndex(0)
        self.widgets["registers_stack"].setCurrentIndex(0)
        self.widgets["extended_registers_stack"].setCurrentIndex(0)
        self.widgets["symbols_stack"].setCurrentIndex(0)
        self.widgets["disassembly_stack"].setCurrentIndex(0)
        self.process_running = False

    def _on_process_started(self) -> None:
        """
        Callback - update the UI to reflect that a debugged process has started.
        """
        # replace placeholder views with the real ones
        self.widgets["breakpoints_stack"].setCurrentIndex(1)
        self.widgets["registers_stack"].setCurrentIndex(1)
        self.widgets["extended_registers_stack"].setCurrentIndex(1)
        self.widgets["symbols_stack"].setCurrentIndex(1)
        self.widgets["disassembly_stack"].setCurrentIndex(1)
        self.debugger_busy = False
        self.process_running = True
    
    def _on_process_update(self, new_debugger_state: DebuggerState) -> None:
        """
        Callback - update the UI to reflect an update in the debugged process state (e.g. new breakpoint, new register values, etc).
        """
        self.debugger_state = new_debugger_state
        self.widgets["disassembly"].update_view(new_debugger_state)
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Event handler when the window is closed
        Starts the async cleanup process to ensure the debugger thread is properly shut down before closing the application.
        This cleanup will trigger this event again after finishing, with _done_cleanup=True.
        In this case we accept the event and the window finishes closing.
        """
        # if we already done the cleanup, finish the event
        if self._done_cleanup:
            return
        # otherwise prevent the event from progressing before the async cleanup
        event.ignore()
        # run the closing cleanup async function, which will close it again in the end
        self._closing_cleanup()
    
    async def force_kill_debugged_process(self):
        """
        Force kill the debugged process, for when the debugger thread is blocked and can't process the stop signal.
        """
        if self.debugger_worker.debugger is not None:
            child_pid = self.debugger_worker.debugger.child_pid
            os.kill(child_pid, signal.SIGKILL)
        # tell the debugger worker (which shouldn't be blocked now) to process the kill, which will also emit the process exit signal
        await self.debugger_worker.call_async(self.debugger_worker.on_process_kill)

    @async_slot
    async def _closing_cleanup(self) -> None:
        """
        Handles the window close event.
        Ensures the debugger thread is properly shut down.
        """
        # If the debugger thread is running, we need to stop it before closing the application to ensure a clean exit.
        if self.debugger_thread.isRunning():
            # kill the traced child manually, as the thread might be blocked waiting and won't be able to process a stop signal.
            await self.force_kill_debugged_process()
            # tell the debugger worker to finish, shutting down the kernel. As the traced process is dead, it shouldn't be blocked.
            await self.debugger_worker.call_async(self.debugger_worker.handle_exit)
            # stop the debugger thread
            self.debugger_thread.quit()
            # wait for the thread to exit before finishing to close
            self.debugger_thread.wait()

        # close again, now with cleanup marked as done
        self._done_cleanup = True
        self.close()
    
    def _on_debugger_busy(self) -> None:
        """
        Callback - when the debugger becomes busy.
        Updates the internal state.
        """
        self.debugger_busy = True
    
    def _on_debugger_ready(self) -> None:
        """
        Callback - when the debugger is ready.
        Updates the internal state.
        """
        self.debugger_busy = False
