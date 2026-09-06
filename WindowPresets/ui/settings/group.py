from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class SettingsGroup(QLabel):

    def __init__(self, title):

        # 🔴 Заголовок отбивается тире с двух сторон.
        super().__init__(f"-------- {title} --------")

        self.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        self.setStyleSheet(
            """
            QLabel{

                font-size:9pt;

                font-weight:bold;

                color:rgb(150,150,150);

                padding-top:10px;

                padding-bottom:3px;

                padding-left:2px;

                background:transparent;

            }
            """
        )