from PySide6.QtGui import QGuiApplication, QPixmap, QPainter
from PySide6.QtCore import QRect


class ScreenshotManager:

    @staticmethod
    def save(file_name):

        screens = QGuiApplication.screens()

        if not screens:
            return False

        # общий прямоугольник всех экранов
        geometry = QRect()

        for screen in screens:
            geometry = geometry.united(
                screen.geometry()
            )

        # создаём большой pixmap
        result = QPixmap(
            geometry.width(),
            geometry.height()
        )

        result.fill()

        painter = QPainter(result)

        for screen in screens:

            pixmap = screen.grabWindow(0)

            geo = screen.geometry()

            # смещение относительно общего пространства
            x = geo.x() - geometry.x()
            y = geo.y() - geometry.y()

            painter.drawPixmap(
                x,
                y,
                pixmap
            )

        painter.end()

        return result.save(file_name, "PNG")