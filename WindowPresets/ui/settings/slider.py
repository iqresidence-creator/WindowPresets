from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QSlider,
    QVBoxLayout,
)


class SettingsSlider(QWidget):

    def __init__(
        self,
        title,
        minimum,
        maximum,
        value,
        suffix=""
    ):

        super().__init__()

        self.suffix = suffix

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        layout.setSpacing(3)

        self.title = QLabel(title)

        layout.addWidget(
            self.title
        )

        self.valueLabel = QLabel()

        self.valueLabel.setAlignment(
            Qt.AlignCenter
        )

        layout.addWidget(
            self.valueLabel
        )

        self.slider = QSlider(
            Qt.Horizontal
        )

        self.slider.setRange(
            minimum,
            maximum
        )

        self.slider.setValue(
            value
        )

        layout.addWidget(
            self.slider
        )

        self.slider.valueChanged.connect(
            self.updateLabel
        )

        self.updateLabel(
            value
        )

    def updateLabel(
        self,
        value
    ):

        self.valueLabel.setText(
            f"{value}{self.suffix}"
        )

    def value(self):

        return self.slider.value()

    def setValue(
        self,
        value
    ):

        self.slider.setValue(
            value
        )