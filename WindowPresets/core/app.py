"""
WindowPresets
Version 0.1.0

Главное приложение.
"""

from ui.main_window import MainWindow


class App:

    def __init__(self):

        self.window = MainWindow()

    def run(self):

        self.window.show()