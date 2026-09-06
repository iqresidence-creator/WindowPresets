from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.input_dialog import InputDialog
from ui.picker_dialog import IconPickerDialog, icon_for_file
from ui.settings.group import SettingsGroup
from core.i18n import tr


class SettingsIgnoreGroup(QWidget):
    """Раздел «Исключения программ».

    Список программ и папок, которые WindowPresets полностью
    игнорирует: их окна не сохраняются в пресет, не открываются
    при загрузке и никогда не закрываются. Удалил запись —
    программа снова участвует в пресетах автоматически.
    """

    changed = Signal()

    def __init__(self, settings):

        super().__init__()

        self._entries = []  # [строка: процесс / путь / заголовок]

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(6)

        layout.addWidget(
            SettingsGroup(tr("Исключения программ"))
        )

        hint = QLabel(
            tr("Программы и папки из этого списка полностью "
               "игнорируются: не сохраняются в пресет, не открываются "
               "при загрузке и никогда не закрываются.")
        )

        hint.setWordWrap(True)

        hint.setStyleSheet(
            "font-size:8pt;"
            "color:rgb(140,140,140);"
            "background:transparent;"
        )

        layout.addWidget(hint)

        self.list = QListWidget()

        self.list.setMaximumHeight(110)

        self.list.setStyleSheet(
            "QListWidget{"
            "font-size:9pt;"
            "}"
        )

        layout.addWidget(self.list)

        buttons = QHBoxLayout()

        buttons.setSpacing(6)

        self.addButton = QPushButton(tr("Добавить"))
        self.addButton.setFixedHeight(30)

        self.editButton = QPushButton(tr("Изменить"))
        self.editButton.setFixedHeight(30)

        self.removeButton = QPushButton(tr("Удалить"))
        self.removeButton.setFixedHeight(30)

        buttons.addWidget(self.addButton)
        buttons.addWidget(self.editButton)
        buttons.addWidget(self.removeButton)

        buttons.addStretch()

        layout.addLayout(buttons)

        # -----------------------------------------------------

        self.load(settings)

        self.addButton.clicked.connect(self.add_item)
        self.editButton.clicked.connect(self.edit_item)
        self.removeButton.clicked.connect(self.remove_item)

    # ----------------------------------------------------------

    def load(self, settings):

        raw = settings.get("ignore_list", []) or []

        if isinstance(raw, dict):
            raw = list(raw.keys())

        self._entries = []

        for item in raw:
            text = str(item).strip()
            if text and text not in self._entries:
                self._entries.append(text)

        self._refresh()

    # ----------------------------------------------------------

    def values(self):

        return list(self._entries)

    # ----------------------------------------------------------

    def _refresh(self):

        self.list.clear()

        for entry in sorted(self._entries):
            self.list.addItem(entry)

    # ----------------------------------------------------------

    def _selected(self):

        row = self.list.currentRow()

        if row < 0:
            return None

        item = self.list.item(row)

        if item is None:
            return None

        return item.text()

    # ----------------------------------------------------------

    @staticmethod
    def _live_window_rows():
        # Строки открытых окон С ИКОНКАМИ программ — для выбора.
        try:
            from core.window_scanner import WindowScanner

            rows = []

            for entry in WindowScanner.collect_live():
                if entry["title"]:
                    rows.append((
                        icon_for_file(entry.get("exe_path")),
                        f"{entry['title'][:45]}  —  {entry['process']}",
                    ))

            return rows

        except Exception:
            return []

    # ----------------------------------------------------------

    def _ask_entry(self, current=""):
        # Выбор исключения: из открытых окон (С ИКОНКАМИ) / вручную
        # (имя, путь, заголовок) / выбор файла или папки.
        rows = SettingsIgnoreGroup._live_window_rows()

        rows.append((QIcon(), tr("<ввести вручную…>")))
        rows.append((QIcon(), tr("<выбрать файл или папку…>")))

        text, ok = IconPickerDialog.pick_row(
            self,
            tr("Исключение"),
            tr("Выберите окно, которое нужно игнорировать\n"
               "(или введите имя процесса / путь / часть заголовка):"),
            rows,
        )

        if not ok:
            return ""

        text = text.strip()

        if text.startswith(tr("<ввести")):

            text, ok = InputDialog.get_text(
                self,
                tr("Исключение"),
                tr("Имя процесса (zcode.exe), путь к файлу/папке\n"
                   "или часть заголовка окна:"),
                text=current,
            )

            return text.strip() if ok else ""

        if text.startswith(tr("<выбрать")):

            path, _ = QFileDialog.getOpenFileName(
                self,
                tr("Файл программы"),
                current or "",
                tr("Программы (*.exe *.vbs *.bat *.cmd *.ps1 *.lnk);;")
                + tr("Все файлы (*.*)"),
            )

            if not path:
                path = QFileDialog.getExistingDirectory(
                    self,
                    tr("…или папка целиком"),
                    current or "",
                )

            return path.strip() if path else ""

        # Выбрано окно из списка — берём имя процесса,
        # либо то, что пользователь вписал сам в поле.
        if "  —  " in text:
            text = text.split("  —  ")[-1]

        return text.strip().lower()

    # ----------------------------------------------------------

    def add_item(self):

        entry = self._ask_entry()

        if not entry:
            return

        if entry not in self._entries:
            self._entries.append(entry)

        self._refresh()

        self.changed.emit()

    # ----------------------------------------------------------

    def edit_item(self):

        entry = self._selected()

        if entry is None:
            return

        new_entry = self._ask_entry(current=entry)

        if not new_entry:
            return

        if entry in self._entries:
            self._entries.remove(entry)

        if new_entry not in self._entries:
            self._entries.append(new_entry)

        self._refresh()

        self.changed.emit()

    # ----------------------------------------------------------

    def remove_item(self):

        entry = self._selected()

        if entry is None or entry not in self._entries:
            return

        self._entries.remove(entry)

        self._refresh()

        self.changed.emit()
