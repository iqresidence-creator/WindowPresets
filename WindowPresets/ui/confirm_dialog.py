from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class ConfirmDialog(QDialog):
    # --------------------------------------
    # Подтверждение действия.
    #
    # 🔴 big=True — САМЫЕ большие кнопки (высота 44, широкое
    # поле нажатия 10x30) — ТОЛЬКО для запросов УДАЛЕНИЯ.
    # Остальные подтверждения (например, скачивание обновления)
    # получают компактные кнопки как у окна переименования
    # пресета (высота 28).
    #
    # Отличия от QMessageBox: кнопки ПО ЦЕНТРУ.
    # Enter = «Да», Esc = «Нет».
    # --------------------------------------

    def __init__(self, parent, title, text,
                 yes_text=None, no_text=None, yes_danger=False,
                 big=False):

        super().__init__(parent)

        from core.i18n import tr

        if yes_text is None:
            yes_text = tr("Да")
        if no_text is None:
            no_text = tr("Нет")

        if big:
            btn_h, btn_w, btn_pad = 44, 130, "10px 30px"
        else:
            btn_h, btn_w, btn_pad = 28, 110, "4px 22px"

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(label, 1)

        # Кнопки по центру: растяжки по краям ряда.
        buttons = QHBoxLayout()
        buttons.setSpacing(18)
        buttons.addStretch(1)

        self.btnYes = QPushButton(yes_text)
        self.btnYes.setMinimumHeight(btn_h)
        self.btnYes.setMinimumWidth(btn_w)
        self.btnYes.setDefault(True)
        # 🔴 yes_danger: массовое удаление — КРАСНЫМ выделяется само
        # действие («Удалить все»), «Отмена» обычного цвета.
        if yes_danger:
            self.btnYes.setObjectName("dangerYesButton")
        self.btnYes.clicked.connect(self.accept)
        buttons.addWidget(self.btnYes)

        self.btnNo = QPushButton(no_text)
        self.btnNo.setMinimumHeight(btn_h)
        self.btnNo.setMinimumWidth(btn_w)
        self.btnNo.clicked.connect(self.reject)
        buttons.addWidget(self.btnNo)

        buttons.addStretch(1)
        layout.addLayout(buttons)

        # objectName для QSS-селектора — ДО применения стилей.
        # 🔴 dangerYesButton важнее bigButton: красная рамка
        # массового удаления не затирается режимом big.
        if big:
            self.btnNo.setObjectName("bigButton")
            if not yes_danger:
                self.btnYes.setObjectName("bigButton")

        self.setStyleSheet("""
QDialog {
    background: rgb(52, 52, 52);
}

QLabel {
    color: rgb(220, 220, 220);
    font-size: 11pt;
}

/* 🔴 Широкое поле нажатия: padding вокруг текста команды
   (~140% размера слова по обеим осям) — режим big (удаления);
   остальные подтверждения — компактнее (как переименование). */
QPushButton {
    color: rgb(230, 230, 230);
    background: rgb(75, 75, 75);
    border: 1px solid rgb(110, 110, 110);
    border-radius: 6px;
    padding: 4px 22px;
    font-size: 10pt;
}

QPushButton#bigButton {
    padding: 10px 30px;
}

QPushButton:hover {
    background: rgba(255,255,255,25);
    border-radius: 6px;
}

QPushButton:pressed {
    background: rgba(255,255,255,40);
    border-radius: 6px;
}

/* 🔴 Массовое удаление: КРАСНЫМ выделено само действие
   («Удалить все»), «Отмена» — обычного цвета. Широкий padding —
   режим big (эта кнопка не получает bigButton). */
QPushButton#dangerYesButton {
    border: 2px solid rgb(229, 57, 53);
    color: rgb(255, 138, 128);
    padding: 10px 30px;
}

QPushButton#dangerYesButton:hover {
    border: 2px solid rgb(255, 82, 82);
    background: rgba(255, 82, 82, 40);
}

QPushButton#dangerYesButton:pressed {
    border: 2px solid rgb(255, 82, 82);
    background: rgba(255, 82, 82, 70);
}
""")

    # --------------------------------------

    def keyPressEvent(self, event: QKeyEvent):

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
            return

        if event.key() == Qt.Key_Escape:
            self.reject()
            return

        super().keyPressEvent(event)
