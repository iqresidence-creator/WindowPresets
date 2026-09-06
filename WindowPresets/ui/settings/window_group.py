from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
)

from ui.settings.checkbox import SettingsCheckBox
from ui.settings.group import SettingsGroup
from core.i18n import tr
from ui.settings.slider import SettingsSlider


class SettingsWindowGroup(QWidget):

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

        # 🔴 САМЫЙ ПЕРВЫЙ раздел настроек: автозапуск при старте
        # Windows (реестр HKCU Run) — над «Главным окном».
        layout.addWidget(
            SettingsGroup(tr("Автозапуск"))
        )

        self.autostart = SettingsCheckBox(
            tr("Запускать при старте системы"),
            settings.get("autostart", False)
        )

        layout.addWidget(self.autostart)

        layout.addWidget(
            SettingsGroup(tr("Главное окно"))
        )

        # 🔴 Цвета под тему Windows: когда включено, яркости
        # окна/списка и цвет текста берутся из темы системы,
        # бегунки яркости не действуют (и гасятся).
        self.useSystemColor = SettingsCheckBox(
            tr("Использовать цвет системы"),
            settings.get("use_system_color", False)
        )

        layout.addWidget(self.useSystemColor)

        # 🔴 Поверх всех окон: если галочка снята — окно ведёт себя
        # как обычное; плашка загрузки всё равно всегда поверх.
        self.windowOnTop = SettingsCheckBox(
            tr("Поверх всех окон"),
            settings.get("window_on_top", True)
        )

        layout.addWidget(
            self.windowOnTop
        )

        self.windowBrightness = SettingsSlider(

            tr("Яркость главного окна"),

            0,

            255,

            settings.get(
                "window_color",
                185
            )

        )

        self.listBrightness = SettingsSlider(

            tr("Яркость списка пресетов"),

            0,

            255,

            settings.get(
                "list_color",
                215
            )

        )

        # 🔴 Прозрачность цветовых подложек пресетов и разделителей.
        self.colorOpacity = SettingsSlider(

            tr("Прозрачность цвета пресетов"),

            0,

            100,

            settings.get(
                "preset_color_opacity",
                100
            ),

            " %"

        )

        layout.addWidget(
            self.windowBrightness
        )

        layout.addWidget(
            self.listBrightness
        )

        # 🔴 «Цвет системы» включает/гасит бегунки яркости
        # (при системных цветах они не действуют).
        def _sync_brightness_enabled(checked):
            self.windowBrightness.setEnabled(not checked)
            self.listBrightness.setEnabled(not checked)

        self.useSystemColor.toggled.connect(
            _sync_brightness_enabled
        )
        _sync_brightness_enabled(self.useSystemColor.isChecked())

        layout.addWidget(
            self.colorOpacity
        )

        # 🔴 Режим кнопок вкладок: значки (символы) или текст.
        self.iconButtons = SettingsCheckBox(
            tr("Кнопки вкладок — значки (иначе текст)"),
            settings.get("button_style", "icons") == "icons"
        )

        layout.addWidget(
            self.iconButtons
        )