from __future__ import annotations

import sys
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from traitlets.config import Config

from pyx64dbg.interactive_console.interactive_console import InteractiveConsole, banner

class InteractiveConsoleView(QWidget):
    def __init__(self, file_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.file_name = file_name
        self.debugger = None

        self._main_window = parent

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Initialzie in-process kernel manager
        # This means that the IPython kernel will run in the same process as the GUI, allowing for direct access to the debugger object and shared state.
        # It also means all prints will directly go to the console widget, like we want
        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = 'qt'

        self.shell = self.kernel_manager.kernel.shell
        
        self.shell.autocall = 2 # autocall - call functions without parenthesis
        self.shell.show_rewritten_input = False # don't show the input twice when autocall is triggered
        self.shell.showtraceback = self._show_simple_error # override default IPython traceback to show simpler error messages in the console widget

        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()

        # Configure Traitlets before initializing the widget
        c = Config()
        c.ConsoleWidget.gui_completion = 'droplist' # show completions in a dropdown list
        
        self.console_widget = RichJupyterWidget(config=c)
        self.console_widget.kernel_manager = self.kernel_manager
        self.console_widget.kernel_client = self.kernel_client

        # Safely Suppress the IPython Default Banner
        # Intercept the kernel info packet before the widget processes it.
        # This dynamically clears the default Python/IPython text payload
        # so that only our custom 'banner' property is rendered.
        original_handler = self.console_widget._handle_kernel_info_reply
        def patched_info_reply(rep):
            if 'content' in rep:
                rep['content']['banner'] = ''
            original_handler(rep)
        self.console_widget._handle_kernel_info_reply = patched_info_reply
        
        # linux colors - similar to a real terminal
        self.console_widget.set_default_style('linux')

        # setup banner and prompt 
        self.console_widget.in_prompt = "PyX64Dbg> "
        self.console_widget.banner = banner

        layout.addWidget(self.console_widget)
        # init the interactive console. This is afterwards so the new stdout stream can be passed
        self.interactive_console = InteractiveConsole(
            file_name=self.file_name,
            update_aliases_callback=self._update_shell_aliases,
            new_debugger_object_callback=self._set_debugger_internal,
            stdout_stream=self.kernel_manager.kernel.stdout
        )
        # push the initial alises to the shell
        self.shell.push(self.interactive_console.get_aliases())


    def _update_shell_aliases(self, aliases: dict):
        """
        Callback - called when the aliases in the interactive console need to be updated (process start / stop)
        """
        self.shell.push(aliases)

    def _set_debugger_internal(self, debugger):
        """
        Callback - called when the debugger object is created in the interactive console, allowing us to set it in the main window and have it accessible to all other views.
        """
        self._main_window.debugger = debugger

    def _show_simple_error(self, *args, **kwargs):
        """
        Override for IPython's default traceback to show simpler error messages in the console widget, showing only the exception type and message without the full stack trace.
        """
        exc_type, exc_value, _ = sys.exc_info()
        if exc_type:
            self.interactive_console.print_error(exc_type.__name__, exc_value)
