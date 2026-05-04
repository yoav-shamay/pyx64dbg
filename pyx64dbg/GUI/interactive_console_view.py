from __future__ import annotations

from typing import TYPE_CHECKING
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.manager import QtKernelManager
from traitlets.config import Config

from pyx64dbg.GUI.debugger_worker import DebuggerWorker
from pyx64dbg.interactive_console.interactive_console import banner

if TYPE_CHECKING:
    from pyx64dbg.GUI.main_window import MainWindow


class InteractiveConsoleView(QWidget):
    def __init__(
        self, main_window: MainWindow, debugger_worker: DebuggerWorker
    ) -> None:
        super().__init__(main_window)
        self.debugger = None
        self._main_window = main_window
        self._debugger_worker = debugger_worker
        self._init_ui()

    def _init_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        # setup the kernel for the interactive console in the debugger worker thread
        self._debugger_worker.kernel_initialized.connect(self._post_kernel_init)
        self._debugger_worker.call_from_another_thread(self._debugger_worker.setup_kernel)
        # initialize the console widget with the appropriate configuration for our use case
        # attach the kernel later, after it's initialized, in the _post_kernel_init function
        c = Config()
        c.ConsoleWidget.gui_completion = (
            "droplist"  # show completions in a dropdown list
        )

        self.console_widget = RichJupyterWidget(config=c)

        # add the newly added console widget to the layout immediately, so it shows up while the kernel is still initializing
        # instead of being a white empty space
        self.layout.addWidget(self.console_widget)
        # Safely Suppress the IPython Default Banner
        # Intercept the kernel info packet before the widget processes it.
        # This dynamically clears the default Python/IPython text payload
        # so that only our custom 'banner' property is rendered.
        original_handler = self.console_widget._handle_kernel_info_reply

        def patched_info_reply(rep):
            if "content" in rep:
                rep["content"]["banner"] = ""
            original_handler(rep)

        self.console_widget._handle_kernel_info_reply = patched_info_reply

        # linux colors - similar to a real terminal
        self.console_widget.set_default_style("linux")

        # setup banner and prompt
        self.console_widget.in_prompt = "PyX64Dbg> "
        self.console_widget.banner = banner

    def _post_kernel_init(self, connection_dict):
        self.kernel_manager = QtKernelManager()
        # load the connection info
        self.kernel_manager.load_connection_info(
            connection_dict
        )
        self.console_widget.kernel_manager = self.kernel_manager
        # initialize the kernel client
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        self.console_widget.kernel_client = self.kernel_client

        # disconnect the signal after the kernel is initialized to avoid unnecessary calls in the future
        self._debugger_worker.kernel_initialized.disconnect(self._post_kernel_init)
