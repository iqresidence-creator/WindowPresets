from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QPushButton


class HoverLabel(QPushButton):

    def __init__(self, text, status, hint):
        super().__init__(text)

        self.status = status
        self.hint = hint

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFlat(True)
        self.setFocusPolicy(Qt.NoFocus)

    def enterEvent(self, event):
        self.status.setText(self.hint)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.status.setText("Готово")
        super().leaveEvent(event)