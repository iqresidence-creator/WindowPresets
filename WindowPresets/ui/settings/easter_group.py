from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
)

from ui.settings.group import SettingsGroup
from core.i18n import tr
from ui.settings.checkbox import SettingsCheckBox


class SettingsEasterGroup(QWidget):

    def __init__(self, settings):

        super().__init__()

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        layout.setSpacing(6)

        layout.addWidget(
            SettingsGroup(tr("Пасхалки"))
        )

        self.cowabunga = SettingsCheckBox(

            tr("Кавабанга !"),

            settings.get(
                "cowabunga",
                False
            )

        )

        layout.addWidget(
            self.cowabunga
        )