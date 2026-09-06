from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
)

from ui.settings.group import SettingsGroup
from ui.settings.slider import SettingsSlider

from core.i18n import tr


class SettingsIconsGroup(QWidget):

    # 🔴 Настроек иконок ровно ДВЕ: яркость и размер. Пак
    # иконок единственный (настройки паков удалены). Обе
    # настройки действуют сразу на нижние кнопки пресетов
    # и на верхние кнопки вкладок — верхние жёстко привязаны
    # к нижним (те же яркость/масштаб, размер — 70% нижнего).

    def __init__(self, settings):

        super().__init__()

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(6)

        layout.addWidget(
            SettingsGroup(tr("Иконки"))
        )

        self.brightness = SettingsSlider(

            tr("Яркость иконок"),

            0,

            100,

            settings.get(

                "icon_brightness",

                50

            ),

            " %"

        )

        self.scale = SettingsSlider(

            tr("Размер иконок"),

            5,

            200,

            int(

                settings.get(

                    "icon_scale",

                    1.0

                ) * 100

            ),

            " %"

        )

        layout.addWidget(self.brightness)

        layout.addWidget(self.scale)
