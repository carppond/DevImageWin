import sys

from PySide6.QtWidgets import QApplication

from ui import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("iOS开发者设置工具")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
