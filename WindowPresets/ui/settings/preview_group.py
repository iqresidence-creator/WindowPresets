from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
)

from ui.settings.group import SettingsGroup
from core.i18n import tr
from ui.settings.slider import SettingsSlider


class SettingsPreviewGroup(QWidget):

    def __init__(self, settings):

        super().__init__()

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(SettingsGroup(tr("Превью")))

        # 🔴 Клавиша раскрытия превью — всегда ПРОБЕЛ (зашита в коде),
        # выбора CTRL/ALT больше нет.
        self.size = SettingsSlider(
            tr("Размер превью (пока не действует)"),
            150,
            800,
            settings.get("preview_size", 320),
            " px",
        )

        self.dim = SettingsSlider(
            tr("Затемнение скриншота превью"),
            0,
            40,
            settings.get("preview_dim", 15),
            " %",
        )

        self.textSize = SettingsSlider(
            tr("Размер текста инфо-плашки"),
            9,
            18,
            settings.get("preview_text_size", 18),
            " px",
        )

        self.panelOpacity = SettingsSlider(
            tr("Прозрачность инфо-плашки"),
            0,
            100,
            settings.get("preview_panel_alpha", 40),
            " %",
        )

        layout.addWidget(self.size)
        layout.addWidget(self.dim)
        layout.addWidget(self.textSize)
        layout.addWidget(self.panelOpacity)

    def values(self):

        return {
            "preview_size": self.size.value(),
            "preview_dim": self.dim.value(),
            "preview_text_size": self.textSize.value(),
            "preview_panel_alpha": self.panelOpacity.value(),
        }
