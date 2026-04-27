from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from .console_controller import ConsoleController

class InteractiveConsoleView(QWidget):
    def __init__(self, debugger, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = ConsoleController(debugger)
        self._init_layout()

    def _init_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 1. Setup the Kernel
        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = 'qt'
        
        # 2. Get the actual shell object from the kernel
        # This is where we apply your IPython-specific configurations
        self.shell = self.kernel_manager.kernel.shell
        self.shell.autocall = 2  # Your preference
        
        # 3. Inject your aliases and commands
        self.shell.push(self.controller.get_initial_ns())

        # 4. Setup the Widget
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()

        self.console = RichJupyterWidget()
        self.console.kernel_manager = self.kernel_manager
        self.console.kernel_client = self.kernel_client
        
        # Apply your banner and custom prompt
        self.console.banner = self.controller.banner
        # qtconsole uses 'in_prompt' instead of custom Prompt classes
        self.console.in_prompt = "PyX64Dbg> "
        
        self.console.set_default_style('linux')
        layout.addWidget(self.console)
    
    def refresh_aliases(self):
        """Call this when debugger state changes (e.g. process starts/stops)"""
        self.shell.push(self.controller.get_initial_ns())