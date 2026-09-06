from math import ceil

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter
from core.i18n import tr
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollBar,
    QVBoxLayout,
    QWidget,
)

from ui.main_window_ui import MAIN_WIDTH


class _PickerCell(QFrame):
    """Строка пресета в пикере: плашка с названием (перенос по
    словам — высота по ФАКТИЧЕСКОМУ тексту), полоски цветов
    вкладок слева, hover-подсветка."""

    clicked = Signal(object)

    # Отступы текста внутри плашки (слева под полоски, справа).
    PAD_L = 14
    PAD_R = 8
    PAD_V = 8

    def __init__(self, preset, strip, color_opacity=100):

        super().__init__()

        self.preset = preset
        self._strip = list(strip or [])
        self._hover = False
        self._color_opacity = color_opacity

        self.setFixedWidth(MAIN_WIDTH)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.PAD_L, self.PAD_V // 2, self.PAD_R, self.PAD_V // 2
        )

        self.label = QLabel(preset.name)
        self.label.setWordWrap(True)
        self.label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        # 🔴 Собственный цвет пресета — подложка плашки (как в
        # главном списке); текст чёрный/белый по яркости цвета.
        self._color = QColor(preset.color) if preset.color else None

        if self._color is not None and self._color.isValid():
            luminance = (
                0.299 * self._color.red()
                + 0.587 * self._color.green()
                + 0.114 * self._color.blue()
            )
            text_rgb = (
                "0, 0, 0" if luminance > 140 else "255, 255, 255"
            )
            self.label.setStyleSheet(
                "background: transparent; border: none; "
                f"color: rgb({text_rgb});"
            )
        else:
            self.label.setStyleSheet(
                "background: transparent; border: none;"
            )

        layout.addWidget(self.label)

        # 🔴 Высота по ФАКТИЧЕСКОМУ переносу слов: считаем САМИ по
        # метрике шрифта (QLabel.heightForWidth в конструкторе
        # врал одной строкой — имя обрезалось). Плашка растёт,
        # пока имя не поместится ПОЛНОСТЬЮ (без потолка строк).
        inner_w = MAIN_WIDTH - self.PAD_L - self.PAD_R

        fm = self.label.fontMetrics()
        text_h = self._wrapped_height(fm, preset.name, inner_w)

        self.label.setMinimumHeight(text_h)
        self.setFixedHeight(text_h + self.PAD_V)

    # --------------------------------------------------

    @staticmethod
    def _wrapped_height(fm, text, width):
        # Жадный перенос по словам; слово шире колонки делится
        # по символам. Возврат — полная высота текста в пикселях.

        def advance(s):
            return fm.horizontalAdvance(s)

        lines = 0

        for paragraph in text.split("\n"):

            words = paragraph.split()

            if not words:
                lines += 1
                continue

            current = ""
            count = 1

            for word in words:
                candidate = (
                    word if not current else current + " " + word
                )

                if advance(candidate) <= width or not current:
                    # Одно слово шире колонки — режется по символам.
                    if not current and advance(word) > width:
                        count += advance(word) // width
                    current = candidate
                else:
                    count += 1
                    current = word

            lines += count

        return max(1, lines) * fm.height()

    # --------------------------------------------------

    def enterEvent(self, event):

        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):

        self._hover = False
        self.update()
        super().leaveEvent(event)

    # --------------------------------------------------

    def mousePressEvent(self, event):

        self.clicked.emit(self)

    # --------------------------------------------------

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        painter.setPen(Qt.PenStyle.NoPen)

        # 🔴 Подложка: собственный цвет пресета (с настройкой
        # прозрачности) или лёгкая нейтральная плашка.
        if self._color is not None and self._color.isValid():
            plate = QColor(self._color)

            if self._color_opacity < 100:
                plate.setAlpha(
                    max(10, int(255 * self._color_opacity / 100))
                )

            painter.setBrush(plate)
        else:
            painter.setBrush(QColor(255, 255, 255, 18))

        painter.drawRoundedRect(rect, 6, 6)

        if self._hover:
            painter.setBrush(QColor(255, 255, 255, 42))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 6, 6)

        # Полоски цветов вкладок — 2px, слева (как в главном списке).
        x = rect.left() + 3

        for hexc in self._strip[:8]:
            painter.fillRect(
                QRect(x, rect.top() + 2, 2, rect.height() - 4),
                QColor(str(hexc)),
            )
            x += 4

        painter.end()

        super().paintEvent(event)


class PresetPickerPopup(QWidget):
    """Быстрый поиск пресета (двойной клик по вкладке «Все»).

    Раскладка (железно, по ТЗ владельца):
      • колонки заполняются СВЕРХУ-ВНИЗ от левого края, следующая
        колонка — справа; высота каждой строки — по её тексту
        (перенос по словам, без обрезки);
      • окно растёт под количество (высота -> потом колонки);
      • скролл — ТОЛЬКО когда окно упёрлось в монитор со всех
        сторон; колесо/скролл ЛИСТАЮТ СТРАНИЦЫ КОЛОНОК.

    Закрытие: курсор покинул окно, Esc, или выбор пресета.
    """

    picked = Signal(object)

    SEARCH_H = 34
    MARGIN = 8
    GAP = 2
    SCROLL_W = 14

    # Пауза перед проверкой «курсор ушёл».
    GRACE_MS = 300
    LEAVE_MS = 200

    def __init__(self, presets, global_pos, on_colors=None, min_size=None, color_opacity=100, parent=None):

        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)

        self._presets = list(presets)
        self._closing = False
        self._min_size = min_size
        self._strip_of = on_colors or (lambda p: [])
        self._color_opacity = color_opacity
        self._page = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN
        )
        layout.setSpacing(6)

        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Поиск пресета..."))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._pick_first)
        self.search.setFixedHeight(self.SEARCH_H)
        layout.addWidget(self.search)

        body = QHBoxLayout()
        body.setSpacing(4)
        body.setContentsMargins(0, 0, 0, 0)

        self.columnsHost = QWidget()
        self.body = QHBoxLayout(self.columnsHost)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(self.GAP)
        self.body.addStretch(1)
        body.addWidget(self.columnsHost, 1)

        self.pageScroll = QScrollBar(Qt.Orientation.Vertical)
        self.pageScroll.setMinimumWidth(self.SCROLL_W)
        self.pageScroll.setPageStep(1)
        self.pageScroll.valueChanged.connect(self._on_page)
        body.addWidget(self.pageScroll)

        layout.addLayout(body, 1)

        self._leave_timer = QTimer(self)
        self._leave_timer.setInterval(self.LEAVE_MS)
        self._leave_timer.timeout.connect(self._check_leave)

        self._rebuild(self._presets, keep_page=False)

    # --------------------------------------------------

    def _rebuild(self, items, keep_page=True):
        # Раскладка: сначала строим ВСЕ ячейки (их высоты разные),
        # затем жадно заполняем колонки по бюджету высоты; когда
        # колонок становится больше, чем влезает в ширину монитора,
        # — закрывается страница.

        from ui.popup_geometry import (
            clamp_point_within_screen,
            screen_geometry,
        )

        anchor = QCursor.pos()
        screen = screen_geometry(anchor)

        max_h = screen.height() - 16
        max_w = screen.width() - 16

        chrome = self.SEARCH_H + 2 * self.MARGIN + 12
        budget_h = max(60, max_h - chrome)

        cols_fit = max(
            1,
            int(
                (max_w - 2 * self.MARGIN - self.SCROLL_W - 6)
                // (MAIN_WIDTH + self.GAP)
            ),
        )

        cells = [
            _PickerCell(
                p, self._strip_of(p), self._color_opacity
            )
            for p in items
        ]

        # 🔴 Жадное заполнение: страница -> колонки -> ячейки.
        pages = [[]]  # page = [column, column...]; column = [cells]
        column = []
        column_h = 0

        for cell in cells:

            if (
                column
                and column_h + cell.height() + self.GAP > budget_h
            ):
                pages[-1].append(column)
                column = []
                column_h = 0

                if len(pages[-1]) >= cols_fit:
                    pages.append([])

            column.append(cell)
            column_h += cell.height() + self.GAP

        if column:
            pages[-1].append(column)

        pages = [p for p in pages if p]

        if not keep_page:
            self._page = 0

        self._page = max(0, min(self._page, len(pages) - 1))

        page = pages[self._page]
        paged = len(pages) > 1

        # Высота окна = самой высокой колонке страницы (не бюджет!),
        # если всё влезает без пейджера.
        if paged:
            content_h = budget_h
            w = max_w
            h = max_h
        else:
            content_h = max(
                sum(c.height() + self.GAP for c in col) - self.GAP
                for col in page
            )
            n_cols = len(page)
            w = (
                2 * self.MARGIN
                + n_cols * MAIN_WIDTH
                + (n_cols - 1) * self.GAP
                + (self.SCROLL_W + 6 if False else 0)
            )
            h = content_h + chrome

        # 🔴 Минимальный размер = окно программы (курсор внутри).
        min_w, min_h = self._min_size or (0, 0)
        w = max(w, min_w)
        h = max(h, min_h)
        w = min(w, max_w)
        h = min(h, max_h)

        self.setFixedSize(w, h)

        # Пейджер.
        self.pageScroll.setRange(0, len(pages) - 1)
        self.pageScroll.setValue(self._page)
        self.pageScroll.setVisible(paged)

        # Сетка -> чистим старые колонки.
        while self.body.count() > 1:
            item = self.body.takeAt(0)

            if item.widget() is not None:
                item.widget().deleteLater()

        for col_cells in page:
            col_host = QWidget()
            col_layout = QVBoxLayout(col_host)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(self.GAP)
            col_layout.addStretch(1)

            for cell in col_cells:
                cell.clicked.connect(self._pick_cell)
                col_layout.insertWidget(col_layout.count() - 1, cell)

            self.body.insertWidget(self.body.count() - 1, col_host)

        # Позиция: чуть выше-левее курсора, целиком в мониторе.
        pos = clamp_point_within_screen(
            QPoint(anchor.x() - 24, anchor.y() - 24), self.size()
        )
        self.move(pos)

    # --------------------------------------------------

    def wheelEvent(self, event):

        # 🔴 Колесо листает СТРАНИЦЫ (колонок), когда пейджер активен.
        # ВНИЗ (отрицательный delta) = СЛЕДУЮЩАЯ страница.
        if self.pageScroll.isVisible() or self.pageScroll.maximum() > 0:
            step = 1 if event.angleDelta().y() < 0 else -1
            self.pageScroll.setValue(self._page + step)
            event.accept()
            return

        super().wheelEvent(event)

    # --------------------------------------------------

    def _on_page(self, page):

        if self._closing:
            return

        self._page = page
        self._rebuild(self._matching(), keep_page=True)

    # --------------------------------------------------

    def _matching(self):

        text = (self.search.text() or "").strip().lower()

        if not text:
            return self._presets

        return [
            p for p in self._presets
            if text in p.name.lower()
        ]

    # --------------------------------------------------

    def _filter(self, _text):

        self._rebuild(self._matching(), keep_page=False)

    # --------------------------------------------------

    def showEvent(self, event):

        super().showEvent(event)

        self.search.setFocus()
        QTimer.singleShot(self.GRACE_MS, self._leave_timer.start)

    # --------------------------------------------------

    def hideEvent(self, event):

        self._leave_timer.stop()
        super().hideEvent(event)

    # --------------------------------------------------

    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return

        super().keyPressEvent(event)

    # --------------------------------------------------

    def _check_leave(self):

        if not self.isVisible():
            self._leave_timer.stop()
            return

        if not self.frameGeometry().contains(QCursor.pos()):
            self.close()

    # --------------------------------------------------

    def _pick_first(self):

        items = self._matching()

        if items:
            self._emit_preset(items[0])

    # --------------------------------------------------

    def _pick_cell(self, cell):

        self._emit_preset(cell.preset)

    # --------------------------------------------------

    def _emit_preset(self, preset):

        if self._closing:
            return

        self._closing = True
        self.close()
        self.picked.emit(preset)
