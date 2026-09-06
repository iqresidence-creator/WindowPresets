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

from core.i18n import tr
from ui.popup_geometry import clamp_point_within_screen


class RenameDialog(QDialog):

    # --------------------------------------
    # Попап переименования пресета.
    # Появляется в глобальных координатах,
    # которые передаёт вызывающий код
    # (на том же месте, где находится пресет).
    # --------------------------------------

    def __init__(self, parent, old_name, global_pos):

        super().__init__(parent)

        self.old_name = old_name
        self.new_name = old_name

        self.setWindowTitle(tr("Переименовать"))
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint
        )
        self.setModal(True)
        self.setFixedWidth(220)

        self._build_ui(old_name)
        self._apply_theme()
        self._position(global_pos)

    # --------------------------------------

    def _build_ui(self, old_name):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(tr("Переименовать пресет"))
        layout.addWidget(title)

        self.input = QLineEdit(old_name)
        self.input.selectAll()
        self.input.returnPressed.connect(self._accept_rename)
        layout.addWidget(self.input)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addStretch(1)

        self.btnOk = QPushButton("OK")
        self.btnOk.setFixedHeight(28)
        self.btnOk.clicked.connect(self._accept_rename)
        buttons.addWidget(self.btnOk)

        self.btnCancel = QPushButton(tr("Отмена"))
        self.btnCancel.setFixedHeight(28)
        self.btnCancel.clicked.connect(self.reject)
        buttons.addWidget(self.btnCancel)

        layout.addLayout(buttons)

        self.input.setFocus()

    # --------------------------------------

    def _apply_theme(self):

        # Тёмная тема — как у главного окна.
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
    padding: 2px 12px;
    font-family: "Segoe UI";
    font-size: 9pt;
}

QPushButton:hover {
    background:rgba(255,255,255,25);
    border-radius:6px;
}

QPushButton:pressed {
    background:rgba(255,255,255,40);
    border-radius:6px;
}
""")

    # --------------------------------------

    def _position(self, global_pos):

        # Попап появляется там же, где находится пресет
        # относительно экрана.
        # 🔴 Железное правило геометрии: целиком в пределах монитора.
        self.move(
            clamp_point_within_screen(global_pos, self.sizeHint())
        )

    # --------------------------------------

    def _accept_rename(self):

        text = self.input.text().strip()

        if not text:
            return

        self.new_name = text
        self.accept()

    # --------------------------------------

    def keyPressEvent(self, event: QKeyEvent):

        if event.key() == Qt.Key_Escape:
            self.reject()
            return

        super().keyPressEvent(event)
