from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QPushButton

from core.i18n import tr
from core.icon_manager import IconManager


class IconButton(QPushButton):

    def __init__(self, icon_name, status_label, hint):

        super().__init__()

        self.icon_name = icon_name
        self.status_label = status_label
        self.hint = hint

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFocusPolicy(Qt.NoFocus)
        self.setFlat(True)

        self.setMinimumWidth(10)
        self.setMinimumHeight(10)

        self.setStyleSheet("""

QPushButton{

    border:none;
    background:transparent;

}

QPushButton:hover{

    background:rgba(255,255,255,25);
    border-radius:6px;

}

QPushButton:pressed{

    background:rgba(255,255,255,40);

}

""")

    # ---------------------------------------------------------

    def update_icon(self, settings):

        IconManager.apply(
            self,
            settings
        )

    # ---------------------------------------------------------

    def enterEvent(self, event):

        if self.status_label:

            self.status_label.setText(
                tr(self.hint)
            )

        super().enterEvent(event)

    # ---------------------------------------------------------

    def leaveEvent(self, event):

        if self.status_label:

            # Возврат в режим ожидания (зелёная заметка об
            # обновлении или «Готово»).
            if hasattr(self.status_label, "set_idle"):
                self.status_label.set_idle()
            else:
                self.status_label.setText(
                    tr("Готово", "status")
                )

        super().leaveEvent(event)