from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QCursor
from core.i18n import tr
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ui.orderable_list import CHIP_COLOR_ROLE, OrderableListWidget

import time


class TagPickerPopup(QDialog):
    # --------------------------------------
    # Окно выбора ТЕГОВ пресета (бывшее подменю «Тег (вкладка)»).
    #
    # Открыто — пока сам не закроешь: клик по строке переключает
    # галочку и окно ОСТАЁТСЯ (удобно выставлять несколько тегов).
    # Ширина фиксированная (не шире главного окна), длинные названия
    # переносятся по словам, больше строк — вертикальная прокрутка.
    # Закрытие: клик вне окна, Esc или кнопка «Готово».
    #
    # Механика закрытия по клику вне — та же тройка, что у
    # TabListPopup (механизмы 2 и 3 + посадочная пауза): окно НЕ
    # Qt.Popup, иначе конфликтует с контекстными меню.
    # --------------------------------------

    GRACE_MS = 250

    def __init__(self, parent, tags, checked, global_pos, width,
                 on_toggle, on_clear, on_closed=None, background_color=52,
                 tab_colors=None, height=None):

        super().__init__(parent)

        self.on_toggle = on_toggle
        self.on_clear = on_clear
        self.on_closed = on_closed

        self._shown_at = 0.0
        self._btn_was_down = False

        self.setWindowFlags(
            Qt.Dialog
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.setStyleSheet(f"""
QDialog {{
    background: rgb({background_color},{background_color},{background_color});
    border: 1px solid rgb(110,110,110);
    border-radius: 6px;
}}
""")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.list = OrderableListWidget()
        self.list.setDragDropMode(
            OrderableListWidget.DragDropMode.NoDragDrop
        )
        self.list.setTextElideMode(Qt.ElideNone)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setStyleSheet("""
QListWidget {
    background: transparent;
    border: none;
    outline: 0;
}

QListWidget::item {
    padding: 6px 10px;
    margin: 1px 2px;
    border-radius: 6px;
}

QListWidget::item:hover {
    background: rgba(255,255,255,25);
}

QListWidget::item:selected {
    background: rgba(255,255,255,40);
}
""")
        # 🔴 Растяжка списка: окно ВСЕГДА во всю высоту монитора —
        # кнопки остаются у нижнего края, пустое место уходит списку.
        layout.addWidget(self.list, 1)

        self.clearButton = QPushButton(tr("Убрать все теги"))
        self.clearButton.setFixedHeight(48)
        self.clearButton.clicked.connect(self._clear)
        layout.addWidget(self.clearButton)

        self.doneButton = QPushButton(tr("Готово"))
        self.doneButton.setFixedHeight(48)
        self.doneButton.clicked.connect(self.close)
        layout.addWidget(self.doneButton)

        tab_colors = tab_colors or {}
        for name in tags:
            item = QListWidgetItem(name)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                Qt.CheckState.Checked
                if name in checked
                else Qt.CheckState.Unchecked
            )
            hexcolor = tab_colors.get(name)
            if hexcolor:
                item.setData(CHIP_COLOR_ROLE, QColor(hexcolor))
            self.list.addItem(item)

        # Высота: во всю высоту окна программы (height), иначе — по
        # строкам с ограничением; ширина фиксированная.
        if height is None:
            rows = max(1, len(tags))
            height = min(rows * 34 + 130, 500)
        self.resize(width, max(height, 260))

        self.list.itemClicked.connect(self._toggle)

        self._watch = QTimer(self)
        self._watch.setInterval(60)
        self._watch.timeout.connect(self._check_outside_click)

        self.move(*global_pos)

    # --------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._shown_at = time.monotonic()
        self._btn_was_down = True
        QApplication.instance().installEventFilter(self)
        self._watch.start()

    # --------------------------------------

    def closeEvent(self, event):
        self._watch.stop()
        QApplication.instance().removeEventFilter(self)
        if self.on_closed:
            self.on_closed()
        super().closeEvent(event)

    # --------------------------------------

    def _in_grace(self):
        return (time.monotonic() - self._shown_at) < self.GRACE_MS / 1000.0

    # --------------------------------------

    def _another_popup_active(self):
        active = QApplication.activePopupWidget()
        return active is not None and active is not self

    # --------------------------------------

    def eventFilter(self, obj, event):
        # Клик по окнам программы вне списка — закрыть (не в паузе
        # и не пока открыто контекстное меню).
        if (
            event.type() == QEvent.MouseButtonPress
            and self.isVisible()
            and not self._in_grace()
            and not self._another_popup_active()
        ):
            pos = event.globalPosition().toPoint()
            if not self.frameGeometry().contains(pos):
                self.close()

        return super().eventFilter(obj, event)

    # --------------------------------------

    def _check_outside_click(self):
        # Клик по рабочему столу/чужим окнам — опрос физической кнопки.
        if not self.isVisible() or self._another_popup_active():
            return

        try:
            import win32api
            import win32con

            down = bool(
                (win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000)
                or (win32api.GetAsyncKeyState(win32con.VK_RBUTTON) & 0x8000)
            )
        except Exception:
            return

        fresh = down and not self._btn_was_down
        self._btn_was_down = down

        if (
            fresh
            and not self._in_grace()
            and not self.frameGeometry().contains(QCursor.pos())
        ):
            self.close()

    # --------------------------------------

    def _toggle(self, item):
        # Клик по строке = переключить галочку; окно остаётся открытым.
        checked = item.checkState() == Qt.CheckState.Checked
        item.setCheckState(
            Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked
        )
        self.on_toggle(item.text(), not checked)

    # --------------------------------------

    def _clear(self):
        for row in range(self.list.count()):
            self.list.item(row).setCheckState(Qt.CheckState.Unchecked)
        self.on_clear()
