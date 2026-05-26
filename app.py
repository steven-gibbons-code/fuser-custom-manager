import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import FuserApp


def main():
    app = QApplication(sys.argv)
    window = FuserApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
