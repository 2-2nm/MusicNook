import sys

from PySide6.QtWidgets import QApplication

from ui import theme
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AudioPlayer")
    app.setFont(theme.font(13))
    app.setStyleSheet(theme.STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
