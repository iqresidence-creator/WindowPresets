import os

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QDialogButtonBox,
)

# Кэш иконок по пути exe (извлечение из файла не мгновенное).
_icon_cache = {}


def icon_for_file(path):
    """Иконка исполняемого файла или папки (кэшируется).

    Несколько способов извлечения (см. core/file_icons.py):
    Store-программы (WindowsApps) получают свой настоящий значок
    из логотипа пакета, а не значок «по умолчанию».
    """

    if not path:
        return QIcon()

    key = str(path).strip().lower()

    if key in _icon_cache:
        return _icon_cache[key]

    from core.file_icons import robust_icon

    icon = robust_icon(key)

    _icon_cache[key] = icon
    return icon


class IconPickerDialog(QDialog):
    """Выбор строки из списка с ИКОНКАМИ программ + поле ручного ввода.
    Замена QInputDialog.getItem, который иконки не поддерживает."""

    def __init__(self, parent, title, label_text, rows, initial=""):

        super().__init__(parent)

        # rows: [(QIcon, текст), ...]
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedWidth(520)

        layout = QVBoxLayout(self)

        tip = QLabel(label_text)
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self.list = QListWidget()
        self.list.setIconSize(QSize(20, 20))

        for icon, text in rows:
            self.list.addItem(QListWidgetItem(icon, text))

        layout.addWidget(self.list, 1)

        self.edit = QLineEdit(initial)
        layout.addWidget(self.edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Выбор строки подставляет её текст в поле — можно отредактировать.
        self.list.currentTextChanged.connect(self.edit.setText)
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())

        if self.list.count():
            self.list.setCurrentRow(0)

    # ----------------------------------------------------------

    def chosen_text(self):
        # То, что в поле: подставленный текст строки или своя правка.
        return self.edit.text().strip()

    # ----------------------------------------------------------

    @staticmethod
    def pick_row(parent, title, label_text, rows, initial=""):
        """Возвращает (текст, ok) — как QInputDialog.getItem."""

        dialog = IconPickerDialog(parent, title, label_text, rows, initial)

        accepted = dialog.exec() == QDialog.Accepted

        return dialog.chosen_text(), accepted
