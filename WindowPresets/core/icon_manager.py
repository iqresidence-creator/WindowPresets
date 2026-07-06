from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPixmap,
)


class IconManager:

    TARGET_SIZE = 48

    @staticmethod
    def icon_path(pack, name):

        return (
            Path("assets")
            / "icons"
            / f"pack_{pack}"
            / f"{name}.png"
        )

    # ---------------------------------------------------------

    @staticmethod
    def load(pack, name):

        return QPixmap(
            str(
                IconManager.icon_path(
                    pack,
                    name
                )
            )
        )

    # ---------------------------------------------------------

    @staticmethod
    def auto_scale_factor(pixmap):

        if pixmap.isNull():
            return 1.0

        side = max(
            pixmap.width(),
            pixmap.height()
        )

        if side <= 0:
            return 1.0

        return IconManager.TARGET_SIZE / side

    # ---------------------------------------------------------

    @staticmethod
    def recolor(pixmap, gray):

        if pixmap.isNull():
            return pixmap

        result = QPixmap(pixmap.size())

        result.fill(Qt.transparent)

        painter = QPainter(result)

        painter.drawPixmap(
            0,
            0,
            pixmap
        )

        painter.setCompositionMode(
            QPainter.CompositionMode_SourceIn
        )

        painter.fillRect(
            result.rect(),
            QColor(
                gray,
                gray,
                gray
            )
        )

        painter.end()

        return result

    # ---------------------------------------------------------

    @staticmethod
    def scale(
        pixmap,
        user_scale,
        pixel_mode
    ):

        if pixmap.isNull():
            return pixmap

        auto = IconManager.auto_scale_factor(
            pixmap
        )

        scale = auto * user_scale

        width = max(
            4,
            int(
                pixmap.width() * scale
            )
        )

        height = max(
            4,
            int(
                pixmap.height() * scale
            )
        )

        mode = (
            Qt.FastTransformation
            if pixel_mode
            else Qt.SmoothTransformation
        )

        return pixmap.scaled(

            width,

            height,

            Qt.KeepAspectRatio,

            mode

        )

    # ---------------------------------------------------------

    @staticmethod
    def build(settings, name):

        pix = IconManager.load(

            settings["icon_pack"],

            name

        )

        pix = IconManager.scale(

            pix,

            settings["icon_scale"],

            settings.get(
                "pixel_mode",
                False
            )

        )

        pix = IconManager.recolor(

            pix,

            settings["icon_color"]

        )

        return pix

    # ---------------------------------------------------------

    @staticmethod
    def apply(button, settings):

        pix = IconManager.build(

            settings,

            button.icon_name

        )

        button.setIcon(
            QIcon(pix)
        )

        button.setIconSize(
            QSize(
                pix.width(),
                pix.height()
            )
        )

        button.setText("")