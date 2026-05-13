
from pyx64dbg.GUI.main_window import MainWindow
from PySide6.QtWidgets import QApplication
import PySide6.QtAsyncio as QtAsyncio
import asyncio


def main() -> None:
    app = QApplication([])
    app.setOrganizationName("PyX64Dbg")
    app.setApplicationName("PyX64Dbg")
    # create the main window
    window = MainWindow()
    # Create a QAsyncio event loop and set it as the event loop for the current thread
    # avoids setting a global policy, as it conflicts with how ipython kernel behaves
    qt_loop = QtAsyncio.QAsyncioEventLoop(app)
    asyncio.set_event_loop(qt_loop)
    # start the event loop
    qt_loop.run_forever()

if __name__ == "__main__":
    main()