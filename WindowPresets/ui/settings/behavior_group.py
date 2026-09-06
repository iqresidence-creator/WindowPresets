from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
)

from ui.settings.group import SettingsGroup
from core.i18n import tr
from ui.settings.checkbox import SettingsCheckBox


class SettingsBehaviorGroup(QWidget):

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
            SettingsGroup(tr("Поведение"))
        )

        self.showPreview = SettingsCheckBox(

            tr("Показывать превью"),

            settings.get(
                "show_preview",
                True
            )

        )

        self.minimizeToTray = SettingsCheckBox(

            tr("Сворачивать в трей"),

            settings.get(
                "minimize_to_tray",
                False
            )

        )

        self.rememberPosition = SettingsCheckBox(

            tr("Запоминать положение окон"),

            settings.get(
                "remember_window_position",
                True
            )

        )

        layout.addWidget(self.showPreview)

        layout.addWidget(self.minimizeToTray)

        layout.addWidget(self.rememberPosition)
        # 🔴 «Удалить все пресеты...» отсюда убрана: массовое удаление
        # теперь по Ctrl+клику на корзине пресетов в главном окне.