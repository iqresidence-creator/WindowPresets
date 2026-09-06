from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QCheckBox,
)


class SettingsCheckBox(QWidget):

    def __init__(
        self,
        text,
        checked=False
    ):

        super().__init__()

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        layout.setSpacing(0)

        self.checkbox = QCheckBox(text)

        self.checkbox.setChecked(
            checked
        )

        layout.addWidget(
            self.checkbox
        )

    def isChecked(self):

        return self.checkbox.isChecked()

    def setChecked(
        self,
        checked
    ):

        self.checkbox.setChecked(
            checked
        )

    @property
    def toggled(self):

        return self.checkbox.toggled