from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from core.i18n import tr


class PresetEditorPopup(QDialog):
    """«Настроить» (ПКМ по пресету): список программ и папок
    сохранённого пресета. Галочка = УДАЛИТЬ из пресета. После
    подтверждения вызывающий код правит пресет и сохраняет диск.
    """

    def __init__(self, parent, preset, icon_for_file=None):

        super().__init__(parent)

        self.setWindowTitle(tr("Настроить пресет"))
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint
        )
        self.setModal(True)

        self._preset = preset

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(
            tr("«{}» — снимите галочки с лишнего").format(preset.name)
        )
        title.setWordWrap(True)
        title.setStyleSheet("color: rgb(160,160,160); border: none;")
        layout.addWidget(title)

        self.list = QListWidget()
        self.list.setVerticalScrollMode(
            QListWidget.ScrollMode.ScrollPerPixel
        )
        layout.addWidget(self.list, 1)

        self._fill(icon_for_file)

        buttons = QHBoxLayout()

        self.deleteButton = QPushButton(tr("Удалить выбранные"))
        self.deleteButton.setMinimumHeight(38)
        self.deleteButton.clicked.connect(self.accept)
        buttons.addWidget(self.deleteButton, 1)

        self.cancelButton = QPushButton(tr("Готово"))
        self.cancelButton.setMinimumHeight(38)
        self.cancelButton.clicked.connect(self.reject)
        buttons.addWidget(self.cancelButton, 1)

        layout.addLayout(buttons)

        self.resize(430, 520)

    # --------------------------------------------------

    def _fill(self, icon_for_file):

        programs = list(self._preset.programs or [])
        folders = list(self._preset.folders or [])

        if not programs and not folders:
            item = QListWidgetItem(tr("В пресете нет программ и папок"))
            item.setFlags(Qt.NoItemFlags)
            self.list.addItem(item)
            return

        if programs:
            header = QListWidgetItem(
                tr("Программы ({})").format(len(programs))
            )
            header.setFlags(Qt.NoItemFlags)
            header.setForeground(Qt.GlobalColor.gray)
            self.list.addItem(header)

            for name in programs:
                item = QListWidgetItem(name)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(Qt.CheckState.Unchecked)
                if icon_for_file:
                    try:
                        exe = next(
                            (
                                w.exe_path
                                for w in self._preset.windows or []
                                if (w.process or "").strip().lower()
                                == name.strip().lower()
                                and w.exe_path
                            ),
                            "",
                        )
                        if exe:
                            icon = icon_for_file(exe)
                            if icon is not None and not icon.isNull():
                                item.setIcon(icon)
                    except Exception:
                        pass
                self.list.addItem(item)

        if folders:
            header = QListWidgetItem(
                tr("Папки ({})").format(len(folders))
            )
            header.setFlags(Qt.NoItemFlags)
            header.setForeground(Qt.GlobalColor.gray)
            self.list.addItem(header)

            for folder in folders:
                item = QListWidgetItem(folder)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(Qt.CheckState.Unchecked)
                self.list.addItem(item)

    # --------------------------------------------------

    def removed_selection(self):

        # (удалённые программы, удалённые папки) — отмеченные
        # галочкой строки.
        removed_programs = []
        removed_folders = []
        section = None

        for row in range(self.list.count()):
            item = self.list.item(row)
            text = item.text()

            if text.startswith(tr("Программы (")):
                section = "programs"
                continue
            if text.startswith(tr("Папки (")):
                section = "folders"
                continue

            if item.checkState() == Qt.CheckState.Checked:
                if section == "programs":
                    removed_programs.append(text)
                elif section == "folders":
                    removed_folders.append(text)

        return removed_programs, removed_folders
