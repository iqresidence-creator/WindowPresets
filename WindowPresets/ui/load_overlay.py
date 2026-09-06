from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.i18n import tr


class LoadOverlay(QWidget):
    """Плашка загрузки пресета: «Загружаю...» поверх ВСЕХ окон в центре
    монитора, пока пресет полностью не применён (программы, папки,
    геометрия), затем «Загружено» на секунду и исчезает."""

    def __init__(self, window):

        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint)

        self.window = window

        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        # 🔴 Вдвое меньше прежних 600x400.
        self.setFixedSize(300, 200)

        layout = QVBoxLayout(self)

        self.label = QLabel(tr("Загружаю..."))

        font = QFont("Segoe UI", 11)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "color: rgb(235,235,235); background: transparent;"
        )

        layout.addWidget(self.label)

        # 🔴 Главное окно программы тоже «всегда поверх» — между двумя
        # topmost-окнами побеждает поднятый последним. Пока плашка
        # видима, периодически поднимаем её выше всего.
        self.raiseTimer = QTimer(self)
        self.raiseTimer.setInterval(250)
        self.raiseTimer.timeout.connect(self._raise_if_visible)

        # 🔴 «Загружено» медленно гаснет ~1.5 с (прозрачность окна).
        self.fadeAnim = QPropertyAnimation(self, b"windowOpacity", self)
        self.fadeAnim.setDuration(1500)
        self.fadeAnim.setStartValue(1.0)
        self.fadeAnim.setEndValue(0.0)
        self.fadeAnim.setEasingCurve(QEasingCurve.InOutQuad)
        self.fadeAnim.finished.connect(self._on_fade_done)

    def _on_fade_done(self):
        self.raiseTimer.stop()
        self.hide()
        self.setWindowOpacity(1.0)

    # ----------------------------------------------------------

    def _raise_if_visible(self):

        if self.isVisible():
            self.raise_()

    # ----------------------------------------------------------

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(38, 38, 38))

    # ----------------------------------------------------------

    def _place_center(self):
        # Центр монитора, на котором стоит главное окно программы.
        screen = self.window.screen().availableGeometry()

        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    # ----------------------------------------------------------

    def show_loading(self):
        # 🔴 Показ и ПЕРЕРИСОВКА до начала блокирующей загрузки:
        # иначе окно не успеет появиться и будет висеть пустой экран.
        from PySide6.QtWidgets import QApplication

        self.fadeAnim.stop()
        self.setWindowOpacity(1.0)
        self.label.setText(tr("Загружаю..."))
        self._place_center()
        self.show()
        self.raise_()
        self.raiseTimer.start()
        QApplication.processEvents()
        QApplication.processEvents()

    # --------------------------------------------------

    def show_done(self):
        from PySide6.QtWidgets import QApplication

        self.label.setText(tr("Загружено"))
        self.raise_()
        QApplication.processEvents()

    # --------------------------------------------------

    def hide_soon(self):
        # «Загружено» висит мгновение, затем медленно гаснет ~1.5 с;
        # пока гаснет — остаётся поверх всего (raiseTimer живёт).
        QTimer.singleShot(400, self.fadeAnim.start)
