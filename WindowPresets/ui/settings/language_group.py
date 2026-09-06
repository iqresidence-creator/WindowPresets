from PySide6.QtWidgets import (
    QComboBox,
    QWidget,
    QVBoxLayout,
)

from ui.settings.group import SettingsGroup


class SettingsLanguageGroup(QWidget):

    # 🔴 Выбор языка интерфейса (rus/en, config «language»).
    # Заголовок всегда двуязычный — настройку найдёт любой
    # пользователь. Смена применяется сразу: главное окно
    # переводится на лету, окно настроек открывается заново.

    def __init__(self, settings):

        super().__init__()

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(6)

        layout.addWidget(
            SettingsGroup("Язык / Language")
        )

        self.combo = QComboBox()

        self.combo.addItems(["Русский", "English"])

        self.combo.setCurrentIndex(
            1 if settings.get("language") == "en" else 0
        )

        layout.addWidget(self.combo)
