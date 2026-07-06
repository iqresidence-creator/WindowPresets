from PySide6.QtWidgets import QWidget

from core.settings_manager import SettingsManager
from ui.main_window_ui import build_ui
from ui.settings_dialog import SettingsDialog


class MainWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.settings = SettingsManager.load()

        self.build_window()

        build_ui(self)

        self.apply_theme(
            self.settings
        )

    # --------------------------------------------------

    def build_window(self):

        self.setWindowTitle(
            "WindowPresets"
        )

        self.setFixedSize(
            360,
            330
        )

    # --------------------------------------------------

    def open_settings(self):

        dialog = SettingsDialog(self)

        dialog.exec()

    # --------------------------------------------------

    def apply_theme(self, settings):

        self.settings = settings

        windowColor = settings["window_color"]
        listColor = settings["list_color"]
        iconColor = settings["icon_color"]

        self.setStyleSheet(f"""

QWidget{{

background:rgb({windowColor},{windowColor},{windowColor});
color:rgb({iconColor},{iconColor},{iconColor});
font-family:"Segoe UI";
font-size:11pt;

}}

QListWidget{{

background:rgb({listColor},{listColor},{listColor});

border:1px solid rgb(110,110,110);

border-radius:8px;

padding:4px;

}}

QLabel{{

background:transparent;

color:rgb({iconColor},{iconColor},{iconColor});

}}

QFrame{{

color:rgb(120,120,120);

}}

QPushButton{{

background:transparent;

border:none;

}}

""")

        buttons = [

            self.btnNew,
            self.btnLoad,
            self.btnRefresh,
            self.btnClose,
            self.btnDelete,
            self.btnSettings

        ]

        for button in buttons:

            button.update_icon(
                settings
            )

        self.update()