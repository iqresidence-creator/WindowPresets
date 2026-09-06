from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from ui.orderable_list import CHIP_COLOR_ROLE, OrderableListWidget

import time


class TabListPopup(QDialog):
    # --------------------------------------
    # Выпадающий список ВСЕХ вкладок — открывается кликом по
    # плашке с названием текущей вкладки.
    #
    # Показывается через show(), НЕ exec(): exec() делает диалог
    # модальным, и нажатия вне списка блокировались модальностью —
    # список не закрывался (баг v0.4.4). Обычный popup сам закрывает
    # себя по клику вне (нативный захват мыши Windows).
    #
    # Закрытие по клику ВНЕ — три независимых механизма:
    #   1) встроенное поведение Qt.Popup (нативный захват мыши);
    #   2) фильтр событий приложения — для кликов по окнам программы;
    #   3) таймер опроса физических кнопок мыши — для кликов по
    #      рабочему столу и чужим окнам (таких событий в Qt нет).
    #
    # ЛКМ по строке — выбрать вкладку (список закрывается).
    # ПКМ по строке — контекстное меню вкладки, СПИСОК НЕ ЗАКРЫВАЕТСЯ.
    # Строки перетаскиваются мышью — порядок вкладок меняется.
    # --------------------------------------

    # Посадочная пауза: нажатия вне списка в первые мгновения после
    # открытия не закрывают его (это «эхо» клика, которым список
    # открыли, или очень быстрый повторный клик).
    GRACE_MS = 250

    def __init__(self, parent, tabs, current, global_pos, width, height,
                 on_click, on_context, on_reorder, on_closed=None,
                 background_color=52, tab_colors=None):

        super().__init__(parent)

        self.on_click = on_click
        self.on_context = on_context
        self.on_reorder = on_reorder
        self.on_closed = on_closed

        self._shown_at = 0.0
        self._btn_was_down = False

        self.setWindowFlags(
            # 🔴 БЕЗ Qt.Popup: два popup-окна (список + QMenu) конфликтуют —
            # контекстное меню вкладки не открывалось. Обычное безрамочное
            # окно поверх; закрытие по клику вне — своими механизмами.
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
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self.list = OrderableListWidget()
        self.list.setTextElideMode(Qt.ElideNone)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list.setStyleSheet("""
QListWidget {
    background: transparent;
    border: none;
    outline: 0;
}

QListWidget::item {
    padding: 7px 10px;
    margin: 2px 2px;
    border-radius: 6px;
}

QListWidget::item:hover {
    background: rgba(255,255,255,25);
}

QListWidget::item:selected {
    background: rgba(255,255,255,40);
}
""")
        self.list.order_changed.connect(self._order_changed)

        # 🔴 Закреплённый список «Все»: отдельный виджет фиксированной
        # высоты НАД прокручиваемым списком — при листании «Все»
        # всегда остаётся наверху (перетаскивать её нельзя).
        self.pinList = OrderableListWidget()
        self.pinList.setDragDropMode(
            QAbstractItemView.DragDropMode.NoDragDrop
        )
        self.pinList.setTextElideMode(Qt.ElideNone)
        self.pinList.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pinList.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pinList.setStyleSheet(self.list.styleSheet())
        # 🔴 Закреплённая «Все» — высокая строка (в 2 раза обычной):
        # слово «Все» видно полностью, нижняя граница ниже текста.
        self.pinList.setFixedHeight(62)
        self.pinList.itemClicked.connect(self._pick)
        self.pinList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pinList.customContextMenuRequested.connect(self._context)

        layout.addWidget(self.pinList)
        layout.addWidget(self.list, 1)

        self._fill(tabs, tab_colors)

        # Ширина — как у плашки; длинные названия переносятся
        # (WrappingDelegate), а не расширяют окно.
        self.resize(width, height)

        # Текущая вкладка — выделена и видна сразу.
        self._highlight(current)

        self.list.itemClicked.connect(self._pick)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context)

        self._watch = QTimer(self)
        self._watch.setInterval(60)
        self._watch.timeout.connect(self._check_outside_click)

        self.move(*global_pos)

    # --------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._shown_at = time.monotonic()
        # Кнопка могла быть ещё зажата в момент открытия — не считать
        # её удержание «свежим нажатием» на первом такте сторожа.
        self._btn_was_down = True
        QApplication.instance().installEventFilter(self)
        self._watch.start()

    # --------------------------------------

    def _in_grace(self):
        return (
            time.monotonic() - self._shown_at
        ) < self.GRACE_MS / 1000.0

    # --------------------------------------

    def closeEvent(self, event):
        self._watch.stop()
        QApplication.instance().removeEventFilter(self)
        if self.on_closed:
            self.on_closed()
        super().closeEvent(event)

    # --------------------------------------

    def _another_popup_active(self):
        # Открыто чужое всплывающее окно (контекстное меню)?
        active = QApplication.activePopupWidget()
        return active is not None and active is not self

    # --------------------------------------

    def eventFilter(self, obj, event):
        # 🔴 Механизм 2: клик по ОКНАМ НАШЕЙ программы вне списка —
        # закрыть без выбора. В посадочной паузе — не закрывать
        # (это «эхо» клика, открывшего список).
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
        # 🔴 Механизм 3: клики по рабочему столу и ЧУЖИМ окнам —
        # таких событий в Qt нет вовсе, опрашиваем физическое
        # состояние кнопок мыши. Закрываем только на СВЕЖЕЕ нажатие
        # (не на удержание при перетаскивании строки) и только после
        # посадочной паузы. Состояние кнопки отслеживаем всегда —
        # иначе зажатие в паузе стало бы «свежим» после неё.
        if not self.isVisible():
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
            and not self._another_popup_active()
            and not self.frameGeometry().contains(QCursor.pos())
        ):
            self.close()

    # --------------------------------------

    def _highlight(self, current):
        # Текущая вкладка ищется в обоих списках («Все» — в закреплённом).
        for widget in (self.pinList, self.list):
            matches = widget.findItems(current, Qt.MatchExactly)
            if matches:
                widget.setCurrentItem(matches[0])
                widget.scrollToItem(matches[0])

    # --------------------------------------

    def _fill(self, tabs, tab_colors=None):
        # Наполняет списки: первая вкладка («Все») — в закреплённый
        # виджет, остальные — в прокручиваемый. Строкам с цветом
        # ставится роль плашки.
        tab_colors = tab_colors or {}
        self.pinList.clear()
        self.list.clear()

        for index, name in enumerate(tabs):
            item = QListWidgetItem(name)
            if index == 0:
                # Строка закреплённой «Все» — высокая, текст по центру.
                item.setSizeHint(QSize(140, 54))
            hexcolor = tab_colors.get(name)
            if hexcolor:
                item.setData(CHIP_COLOR_ROLE, QColor(hexcolor))
            target = self.pinList if index == 0 else self.list
            target.addItem(item)

    # --------------------------------------

    def refresh(self, tabs, current, tab_colors=None):
        # Перечитывает списки после действий контекстного меню
        # (дублирование / переименование / удаление / цвет).
        self.pinList.blockSignals(True)
        self.list.blockSignals(True)
        self._fill(tabs, tab_colors)
        self.pinList.blockSignals(False)
        self.list.blockSignals(False)
        self._highlight(current)

    # --------------------------------------

    def _order_changed(self):
        order = [
            self.list.item(i).text()
            for i in range(self.list.count())
        ]
        self.on_reorder(order)

    # --------------------------------------

    def _pick(self, item):
        # Выбор вкладки — одно из двух, что закрывает список при
        # клике внутри (второе — клик вне).
        chosen = item.text()
        self.close()
        self.on_click(chosen)

    # --------------------------------------

    def _context(self, pos):
        # ПКМ работает в обоих списках — закреплённом и прокручиваемом.
        widget = self.sender() if isinstance(self.sender(), QListWidget) \
            else self.list
        item = widget.itemAt(pos)
        if item is None:
            return

        global_pos = widget.viewport().mapToGlobal(pos)

        # 🔴 Список НЕ закрывается: меню поверх, после действия
        # вызывающий код обновляет список через refresh().
        self.on_context(item.text(), global_pos, self)
