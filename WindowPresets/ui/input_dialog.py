from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ui.popup_geometry import clamp_point_within_screen

from core.i18n import tr


class InputDialog(QDialog):

    # --------------------------------------
    # Единое окно ввода строки — замена
    # QInputDialog (у того мелкие неудобные
    # системные кнопки). Кнопки и тёмная тема —
    # ровно как у окна переименования пресета.
    # Enter = OK, Esc = Отмена.
    # --------------------------------------

    def __init__(self, parent, title, label, text=""):

        super().__init__(parent)

        self.text_value = text

        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint
        )
        self.setModal(True)
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Подпись поля может быть многострочной.
        caption = QLabel(label)
        caption.setWordWrap(True)
        layout.addWidget(caption)

        self.input = QLineEdit(text)
        self.input.selectAll()
        self.input.returnPressed.connect(self.accept)
        layout.addWidget(self.input)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addStretch(1)

        self.btnOk = QPushButton("OK")
        self.btnOk.setFixedHeight(28)
        self.btnOk.setDefault(True)
        self.btnOk.clicked.connect(self.accept)
        buttons.addWidget(self.btnOk)

        self.btnCancel = QPushButton(tr("Отмена"))
        self.btnCancel.setFixedHeight(28)
        self.btnCancel.clicked.connect(self.reject)
        buttons.addWidget(self.btnCancel)

        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._apply_theme()
        self.input.setFocus()

    # --------------------------------------

    def _apply_theme(self):

        # Тёмная тема — как у окна переименования.
        self.setStyleSheet("""
QDialog {
    background: rgb(60, 60, 60);
    border: 1px solid rgb(110, 110, 110);
    border-radius: 8px;
}

QLabel {
    background: transparent;
    color: rgb(220, 220, 220);
    font-family: "Segoe UI";
    font-size: 10pt;
}

QLineEdit {
    background: rgb(45, 45, 45);
    color: rgb(230, 230, 230);
    border: 1px solid rgb(110, 110, 110);
    border-radius: 4px;
    padding: 4px 6px;
    font-family: "Segoe UI";
    font-size: 10pt;
    selection-background-color: rgb(80, 120, 180);
}

QLineEdit:focus {
    border: 1px solid rgb(130, 160, 200);
}

QPushButton {
    background: rgb(75, 75, 75);
    color: rgb(230, 230, 230);
    border: 1px solid rgb(110, 110, 110);
    border-radius: 4px;
    padding: 2px 16px;
    font-family: "Segoe UI";
    font-size: 9pt;
}

QPushButton:hover {
    background:rgba(255,255,255,25);
    border-radius:4px;
}

QPushButton:pressed {
    background:rgba(255,255,255,40);
    border-radius:4px;
}
""")

    # --------------------------------------

    def accept(self):

        self.text_value = self.input.text()
        super().accept()

    # --------------------------------------

    def showEvent(self, event):

        super().showEvent(event)

        # Центр родительского окна; 🔴 железное правило
        # геометрии: целиком в пределах монитора.
        parent = self.parent()

        if parent is not None:
            geo = parent.frameGeometry()
            pos = geo.center() - self.rect().center()
            self.move(clamp_point_within_screen(pos, self.size()))

    # --------------------------------------

    def keyPressEvent(self, event: QKeyEvent):

        if event.key() == Qt.Key_Escape:
            self.reject()
            return

        super().keyPressEvent(event)

    # --------------------------------------

    @staticmethod
    def get_text(parent, title, label, text=""):

        # Сигнатура ответа — как у QInputDialog.getText:
        # (строка, ok).
        dialog = InputDialog(parent, title, label, text)
        ok = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.text_value, ok
