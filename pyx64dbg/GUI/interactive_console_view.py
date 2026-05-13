from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.manager import QtKernelManager
from traitlets.config import Config
from jupyter_client import KernelClient, KernelConnectionInfo
from pyx64dbg.debugger import Debugger
from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.interactive_console.interactive_console import banner

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow

class InteractiveConsoleView(QWidget):
    """
    This class defines the interactive console view widget in the GUI.
    It uses a Jupyter console widget to provide an interactive Python console.
    This widget only contains the console itself.
    It connects to a kernel that is set up in the DebuggerWorker thread, and some of the console configuration is done there.
    """
    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)
        self.debugger: Debugger | None = None
        self._main_window: MainWindow = main_window
        self._debugger_worker: DebuggerWorker = main_window.debugger_worker
        self._kernel_client : KernelClient | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # setup the kernel for the interactive console in the debugger worker thread
        # this method emits a signal when the kernel is initialized, we connect a post-initialization function to that signal.
        self._debugger_worker.kernel_initialized.connect(self._post_kernel_init)
        self._debugger_worker.call_from_another_thread(self._debugger_worker.setup_kernel)
        # initialize the console widget with the appropriate configuration for our use case (that doesn't require the kernel)
        # attach the kernel later, after it's initialized, in the _post_kernel_init function
        c = Config()
        # show completions in a dropdown list
        c.ConsoleWidget.gui_completion = "droplist"

        self._console_widget: RichJupyterWidget = RichJupyterWidget(config=c)

        # add the newly added console widget to the layout immediately, so it shows up while the kernel is still initializing
        # instead of being a white empty space
        layout.addWidget(self._console_widget)
        # linux colors - similar to a real terminal
        self._console_widget.set_default_style("linux")

        # setup banner and prompt
        self._console_widget.in_prompt = "PyX64Dbg> "
        self._console_widget.banner = banner

    def _post_kernel_init(self, connection_dict: KernelConnectionInfo) -> None:
        """
        Method that finishes the console initialization after the kernel is initialized in the debugger worker thread.
        Gets the connection dict from the debugger worker thread.
        """
        self.kernel_manager = QtKernelManager()
        # load the connection info
        self.kernel_manager.load_connection_info(connection_dict)
        self._console_widget.kernel_manager = self.kernel_manager
        # initialize the kernel client
        self._kernel_client = self.kernel_manager.client()
        self._kernel_client.start_channels() # init the communication channels with the kernel
        self._console_widget.kernel_client = self._kernel_client

        # disconnect the signal after the kernel is initialized to avoid unnecessary calls in the future
        self._debugger_worker.kernel_initialized.disconnect(self._post_kernel_init)