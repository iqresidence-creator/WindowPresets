from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QPixmap,
)

from core.app_paths import resource_dir


class IconManager:

    TARGET_SIZE = 48

    # 🔴 Единственный пак иконок (символьный: + ↓ ↻ ✕ корзина
    # шестерёнка ⧉ ⌶ + иконка программы). Настройка выбора паков
    # удалена: все кнопки программы (нижние и вкладки) рисуются
    # только отсюда.
    PACK = 5

    @staticmethod
    def icon_path(name):

        return (
            resource_dir()
            / "assets"
            / "icons"
            / f"pack_{IconManager.PACK}"
            / f"{name}.png"
        )

    # ---------------------------------------------------------

    @staticmethod
    def load(name):

        return QPixmap(
            str(
                IconManager.icon_path(
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
    def recolor(pixmap, brightness):

        if pixmap.isNull():
            return pixmap

        image = pixmap.toImage().convertToFormat(
            QImage.Format_ARGB32
        )

        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)

                if color.alpha() == 0:
                    continue

                if brightness <= 50:
                    factor = brightness / 50.0
                    red = int(color.red() * factor)
                    green = int(color.green() * factor)
                    blue = int(color.blue() * factor)
                else:
                    factor = (brightness - 50) / 50.0
                    red = int(color.red() + (255 - color.red()) * factor)
                    green = int(color.green() + (255 - color.green()) * factor)
                    blue = int(color.blue() + (255 - color.blue()) * factor)

                image.setPixelColor(
                    x,
                    y,
                    QColor.fromRgb(
                        max(0, min(255, red)),
                        max(0, min(255, green)),
                        max(0, min(255, blue)),
                        color.alpha()
                    ),
                )

        return QPixmap.fromImage(image)

    # ---------------------------------------------------------

    @staticmethod
    def scale(
        pixmap,
        user_scale
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

        return pixmap.scaled(

            width,

            height,

            Qt.KeepAspectRatio,

            Qt.SmoothTransformation

        )

    # ---------------------------------------------------------

    @staticmethod
    def build(settings, name, scale_factor=1.0):

        # 🔴 scale_factor: 1.0 — нижние кнопки пресетов; 0.7 —
        # верхние кнопки вкладок (жёсткая привязка: те же
        # настройки «Яркость/Размер иконок», размер — 70%
        # нижнего).
        pix = IconManager.load(
            name
        )

        pix = IconManager.scale(

            pix,

            settings.get(
                "icon_scale",
                1.0
            ) * scale_factor

        )

        pix = IconManager.recolor(

            pix,

            settings.get(
                "icon_brightness",
                50
            )

        )

        return pix

    # ---------------------------------------------------------

    @staticmethod
    def apply(button, settings, scale_factor=1.0):

        pix = IconManager.build(
            settings,
            button.icon_name,
            scale_factor
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
