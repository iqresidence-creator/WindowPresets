from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
)

from core.settings_manager import SettingsManager
from ui.icon_button import IconButton


def build_ui(window):

    settings = SettingsManager.load()

    layout = QVBoxLayout(window)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    # -------------------------------------------------
    # Список пресетов
    # -------------------------------------------------

    window.presetList = QListWidget()
    layout.addWidget(window.presetList, 1)

    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    layout.addWidget(line)

    # -------------------------------------------------
    # Верхняя панель кнопок
    # -------------------------------------------------

    row = QHBoxLayout()
    row.setSpacing(4)

    window.btnNew = IconButton(
        "new",
        None,
        "Новый пресет"
    )

    window.btnLoad = IconButton(
        "load",
        None,
        "Загрузить пресет"
    )

    window.btnRefresh = IconButton(
        "refresh",
        None,
        "Обновить пресет"
    )

    window.btnClose = IconButton(
        "close",
        None,
        "Закрыть пресет"
    )

    window.btnDelete = IconButton(
        "delete",
        None,
        "Удалить пресет"
    )

    buttons = [

        window.btnNew,
        window.btnLoad,
        window.btnRefresh,
        window.btnClose,
        window.btnDelete

    ]

    for button in buttons:

        button.setMinimumHeight(34)

        button.update_icon(settings)

        row.addWidget(button)

    layout.addLayout(row)

    # -------------------------------------------------

    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    layout.addWidget(line)

    # -------------------------------------------------
    # Нижняя строка
    # -------------------------------------------------

    bottom = QHBoxLayout()

    window.statusBar = QLabel("Готово")

    bottom.addWidget(
        window.statusBar,
        1
    )

    window.btnSettings = IconButton(

        "settings",

        window.statusBar,

        "Настройки"

    )

    window.btnSettings.setFixedSize(
        80,
        34
    )

    window.btnSettings.update_icon(
        settings
    )

    bottom.addWidget(
        window.btnSettings
    )

    layout.addLayout(bottom)

    # -------------------------------------------------

    for button in buttons:

        button.status_label = window.statusBar

    window.btnSettings.clicked.connect(
        window.open_settings
    )