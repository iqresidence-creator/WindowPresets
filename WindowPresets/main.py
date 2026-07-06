"""
WindowPresets
Version 0.1.0

Точка входа в программу.
"""

import sys

from PySide6.QtWidgets import QApplication

from core.app import App


def main():

    app = QApplication(sys.argv)

    application = App()
    application.run()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()