from pyx64dbg.GUI.main_window import MainWindow
from PySide6.QtWidgets import QApplication
import PySide6.QtAsyncio as QtAsyncio
import asyncio
from PySide6.QtCore import qInstallMessageHandler

def qt_message_handler(mode, context, message: str) -> None:
    """
    Ignore specific warning/error messages that are harmless and expected in certain scenarios.
    """
    # Ignore the QSocketNotifier: Invalid socket <num> and type 'Read', disabling... warning.
    # It can be triggered when the PTY is closed by the debugger before we close the notifier.
    # Also ignore the "This plugin supports grabbing the mouse only for popup windows" warning when randomly tapping stuff
    blacklist = [
        "QSocketNotifier: Invalid socket",
        "This plugin supports grabbing the mouse only for popup windows"
    ]
    if any(keyword in message for keyword in blacklist):
        return
    
    # Print all other messages normally
    print(message)


def main() -> None:
    # disable specific warning/error messages that are harmless
    qInstallMessageHandler(qt_message_handler)
    app = QApplication([])
    app.setOrganizationName("PyX64Dbg")
    app.setApplicationName("PyX64Dbg")
    # create the main window
    window = MainWindow()
    # Create a QAsyncio event loop and set it as the event loop for the current thread
    # avoids setting a global policy, as it conflicts with how ipython behaves
    qt_loop = QtAsyncio.QAsyncioEventLoop(app)
    asyncio.set_event_loop(qt_loop)
    # start the event loop
    qt_loop.run_forever()

if __name__ == "__main__":
    main()