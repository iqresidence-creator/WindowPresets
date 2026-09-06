import os

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


class SettingsLaunchGroup(QWidget):
    """Раздел «Пути запуска программ».

    Ручное сопоставление «программа -> файл/команда запуска» для
    программ, которые открываются неправильно: скрипты, программы
    с аргументами, запуск через песочницу Sandboxie. При загрузке
    пресета такая программа запускается точно указанным способом.
    """

    changed = Signal()

    def __init__(self, settings):

        super().__init__()

        self._paths = {}  # {ключ: файл или команда запуска}

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(6)

        layout.addWidget(
            SettingsGroup(tr("Пути запуска программ"))
        )

        hint = QLabel(
            tr("Если программа из пресета открывается неправильно — "
               "укажите для неё файл запуска или целую команду "
               "(exe, vbs, lnk или команда с аргументами, например "
               "для запуска через песочницу).")
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

        raw = settings.get("launch_paths", {}) or {}

        self._paths = {
            str(name).strip(): str(path)
            for name, path in raw.items()
            if str(name).strip() and str(path).strip()
        }

        self._refresh()

    # ----------------------------------------------------------

    def values(self):

        return dict(self._paths)

    # ----------------------------------------------------------

    def _refresh(self):

        self.list.clear()

        for name in sorted(self._paths):

            path = self._paths[name]

            self.list.addItem(f"{name}  →  {path}")

    # ----------------------------------------------------------

    def _selected_name(self):

        row = self.list.currentRow()

        if row < 0:
            return None

        item = self.list.item(row)

        if item is None:
            return None

        return item.text().split("  →  ")[0]

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

    def _ask_program(self):
        # Шаг 1: выбрать программу — теми же способами, что и
        # в «Исключениях»: из открытых окон (С ИКОНКАМИ) / по имени /
        # выбрать exe в проводнике (имя возьмётся из файла, а сам файл
        # сразу подставится в команду запуска).
        # Возвращает (имя, путь-подстановка для команды).
        rows = SettingsLaunchGroup._live_window_rows()

        rows.append((QIcon(), tr("<ввести вручную…>")))
        rows.append((QIcon(), tr("<выбрать файл программы…>")))

        text, ok = IconPickerDialog.pick_row(
            self,
            tr("Программа"),
            tr("Выберите окно программы, для которой задаётся запуск\n"
               "(впишите имя процесса или выберите exe-файл):"),
            rows,
        )

        if not ok:
            return "", ""

        text = text.strip()

        # Файл, выбранный в проводнике: имя программы — из файла,
        # путь — заготовка для команды запуска.
        if text.startswith(tr("<выбрать")):

            path, _ = QFileDialog.getOpenFileName(
                self,
                tr("Программа (её exe)"),
                "",
                tr("Программы (*.exe *.vbs *.vbe *.bat *.cmd *.ps1 "
                   "*.js *.hta *.lnk);;")
                + tr("Все файлы (*.*)"),
            )

            if not path:
                return "", ""

            return os.path.basename(path).strip().lower(), path

        if text.startswith(tr("<ввести")):
            text, ok = InputDialog.get_text(
                self,
                tr("Программа"),
                tr("Имя процесса программы (как в диспетчере задач),\n"
                   "например: powershell.exe"),
            )
            return (text.strip().lower(), "") if ok else ("", "")

        # Выбрано окно из списка — берём имя процесса,
        # либо то, что пользователь вписал сам в поле.
        if "  —  " in text:
            text = text.split("  —  ")[-1]

        return text.strip().lower(), ""

    # ----------------------------------------------------------

    def _ask_command(self, current=""):
        # Шаг 2: файл запуска ИЛИ команда с аргументами.
        # Можно выбрать файл кнопкой (или папку — если файл
        # отменили), а затем отредактировать текст
        # (например, дописать аргументы песочницы).
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Файл запуска (можно потом отредактировать команду)"),
            current or "",
            tr("Программы, скрипты, ярлыки (*.exe *.vbs *.vbe *.bat "
               "*.cmd *.ps1 *.js *.hta *.lnk);;")
            + tr("Все файлы (*.*)"),
        )

        if not path:
            # Файл не выбрали — можно выбрать папку (откроется
            # в проводнике при запуске).
            folder = QFileDialog.getExistingDirectory(
                self,
                tr("…или папка"),
                current or "",
            )
            path = folder or ""

        initial = path or current

        text, ok = InputDialog.get_text(
            self,
            tr("Команда запуска"),
            tr("Путь к файлу запуска или команда (можно с аргументами).\n"
               "Пример песочницы:\n"
               '"C:\\Program Files\\Sandboxie-Plus\\SandMan.exe" '
               '/box:DefaultBox "C:\\путь\\программа.exe"'),
            text=initial,
        )

        if not ok:
            return ""

        return text.strip()

    # ----------------------------------------------------------

    def add_item(self):

        name, prefill = self._ask_program()

        if not name:
            return

        command = self._ask_command(prefill)

        if not command:
            return

        self._paths[name] = command

        self._refresh()

        self.changed.emit()

    # ----------------------------------------------------------

    def edit_item(self):

        name = self._selected_name()

        if name is None or name not in self._paths:
            return

        command = self._ask_command(self._paths[name])

        if not command:
            return

        self._paths[name] = command

        self._refresh()

        self.changed.emit()

    # ----------------------------------------------------------

    def remove_item(self):

        name = self._selected_name()

        if name is None or name not in self._paths:
            return

        del self._paths[name]

        self._refresh()

        self.changed.emit()
