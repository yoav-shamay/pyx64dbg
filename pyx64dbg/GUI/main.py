
from pyx64dbg.GUI.main_window import MainWindow
from PyQt6.QtWidgets import QApplication

def main() -> None:
    app = QApplication([])
    app.setOrganizationName("PyX64Dbg")
    app.setApplicationName("PyX64Dbg")
    window = MainWindow()
    window.showMaximized()
    app.exec()

if __name__ == "__main__":
    main()