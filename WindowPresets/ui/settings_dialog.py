from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QLabel,
    QPushButton,
    QSlider,
    QHBoxLayout,
    QVBoxLayout,
)

from core.settings_manager import SettingsManager


class SettingsDialog(QDialog):

    def __init__(self, parent):
        super().__init__(parent)

        self.window = parent
        self.settings = SettingsManager.load()

        if "pixel_mode" not in self.settings:
            self.settings["pixel_mode"] = False

        self.setWindowTitle("Настройки")
        self.setFixedSize(360, 430)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ------------------------------------------------

        layout.addWidget(QLabel("Фон окна"))

        self.windowSlider = QSlider(Qt.Horizontal)
        self.windowSlider.setRange(0, 255)
        self.windowSlider.setValue(self.settings["window_color"])
        layout.addWidget(self.windowSlider)

        # ------------------------------------------------

        layout.addWidget(QLabel("Фон окна пресетов"))

        self.listSlider = QSlider(Qt.Horizontal)
        self.listSlider.setRange(0, 255)
        self.listSlider.setValue(self.settings["list_color"])
        layout.addWidget(self.listSlider)

        # ------------------------------------------------

        layout.addWidget(QLabel("Цвет иконок"))

        self.iconSlider = QSlider(Qt.Horizontal)
        self.iconSlider.setRange(0, 255)
        self.iconSlider.setValue(self.settings["icon_color"])
        layout.addWidget(self.iconSlider)

        # ------------------------------------------------

        layout.addWidget(QLabel("Масштаб иконок"))

        self.scaleLabel = QLabel()
        self.scaleLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.scaleLabel)

        self.scaleSlider = QSlider(Qt.Horizontal)
        self.scaleSlider.setRange(5, 200)
        self.scaleSlider.setValue(
            int(self.settings["icon_scale"] * 100)
        )

        layout.addWidget(self.scaleSlider)

        # ------------------------------------------------

        self.pixelMode = QCheckBox("Pixel (без сглаживания)")
        self.pixelMode.setChecked(
            self.settings["pixel_mode"]
        )

        layout.addWidget(self.pixelMode)

        # ------------------------------------------------

        layout.addWidget(QLabel("Набор иконок"))

        row = QHBoxLayout()

        self.prevButton = QPushButton("◀")
        self.prevButton.setFixedSize(80, 40)
        self.prevButton.setStyleSheet(
            "font-size:18pt;"
        )

        self.packLabel = QLabel()
        self.packLabel.setAlignment(Qt.AlignCenter)

        self.nextButton = QPushButton("▶")
        self.nextButton.setFixedSize(80, 40)
        self.nextButton.setStyleSheet(
            "font-size:18pt;"
        )

        row.addWidget(self.prevButton)
        row.addWidget(self.packLabel, 1)
        row.addWidget(self.nextButton)

        layout.addLayout(row)

        # ------------------------------------------------

        close = QPushButton("Закрыть")
        layout.addWidget(close)

        # ------------------------------------------------

        self.windowSlider.valueChanged.connect(
            self.update_preview
        )

        self.listSlider.valueChanged.connect(
            self.update_preview
        )

        self.iconSlider.valueChanged.connect(
            self.update_preview
        )

        self.scaleSlider.valueChanged.connect(
            self.update_preview
        )

        self.pixelMode.toggled.connect(
            self.update_preview
        )

        self.prevButton.clicked.connect(
            self.previous_pack
        )

        self.nextButton.clicked.connect(
            self.next_pack
        )

        close.clicked.connect(self.close)

        self.refresh_pack_name()
        self.update_preview()

    # ------------------------------------------------

    def refresh_pack_name(self):

        self.packLabel.setText(
            f"{self.settings['icon_pack']} / 4"
        )

    # ------------------------------------------------

    def previous_pack(self):

        if self.settings["icon_pack"] > 1:
            self.settings["icon_pack"] -= 1

        self.refresh_pack_name()
        self.update_preview()

    # ------------------------------------------------

    def next_pack(self):

        if self.settings["icon_pack"] < 4:
            self.settings["icon_pack"] += 1

        self.refresh_pack_name()
        self.update_preview()

    # ------------------------------------------------

    def update_preview(self):

        self.settings["window_color"] = self.windowSlider.value()
        self.settings["list_color"] = self.listSlider.value()
        self.settings["icon_color"] = self.iconSlider.value()
        self.settings["icon_scale"] = self.scaleSlider.value() / 100.0
        self.settings["pixel_mode"] = self.pixelMode.isChecked()

        self.scaleLabel.setText(
            f"{self.scaleSlider.value()} %"
        )

        SettingsManager.save(self.settings)

        self.window.apply_theme(
            self.settings
        )