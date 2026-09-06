from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from core.i18n import tr
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QLabel,
)

from ui.picker_dialog import icon_for_file


# 🔴 Ограничения ширины колонок инфо-панели.
# Длинное название пресета будет переноситься по строкам,
# а не растягивать окошко.
MIN_COL_WIDTH = 180
MAX_COL_WIDTH = 320
MIN_PANEL_WIDTH = 360

# 🔴 Иконка программы/папки в строке левой колонки.
ICON_SIZE = 14
ICON_SLOT = ICON_SIZE + 4   # место строки под иконку + отступ
ROW_SPACING = 2
SECTION_SPACING = 6
HEADER_PAD = 3


class InfoPanel(QWidget):
    # Плашка с составом пресета (программы/папки + сводка).
    # ДВА режима:
    #  • parent=None — отдельное окно ПО ЦЕНТРУ ЭКРАНА (только для
    #    ПОЛНОЭКРАННОГО превью; прозрачно для мыши);
    #  • с parent — обычный дочерний виджет: встроена в нижнюю
    #    часть малого превью (под скриншотом, в скролле).

    def __init__(self, parent=None):

        top_level = parent is None
        if top_level:
            super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            # 🔴 Отдельная плашка только показывает текст — клики
            # проходят СКВОЗЬ неё к окнам под ней.
            self.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            super().__init__(parent)

        self.panelColor = QColor(50, 50, 50, 160)
        self.textSize = 18

        # 🔴 Левая колонка — структурированные строки «иконка + текст»:
        # {"programs": [(имя, exe_path)], "folders": [путь]}.
        self._left_data = {"programs": [], "folders": []}
        self._right_text = ""
        self._left_headers = []   # [(label, text)]
        self._left_rows = []      # [(icon_label, text_label, text)]

        self.contentLayout = QHBoxLayout(self)
        self.contentLayout.setContentsMargins(12, 12, 12, 12)
        self.contentLayout.setSpacing(16)

        self.leftBox = QWidget()
        self.leftBox.setStyleSheet("background: transparent;")
        self.leftLayout = QVBoxLayout(self.leftBox)
        self.leftLayout.setContentsMargins(0, 0, 0, 0)
        self.leftLayout.setSpacing(ROW_SPACING)

        self.right = QLabel()
        self.right.setWordWrap(True)
        self.right.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.right.setTextFormat(Qt.PlainText)
        self.right.setStyleSheet("background: transparent; color: white;")

        self.contentLayout.addWidget(self.leftBox)
        self.contentLayout.addWidget(self.right, 1)

    # -----------------------------

    def _font(self):

        return QFont("Segoe UI", self.textSize)

    # -----------------------------

    def _clear_left(self):

        while self.leftLayout.count():
            item = self.leftLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._left_headers = []
        self._left_rows = []

    # -----------------------------

    def _add_header(self, text):

        lbl = QLabel(text)
        lbl.setFont(self._font())
        lbl.setTextFormat(Qt.PlainText)
        lbl.setStyleSheet("background: transparent; color: rgb(160,160,160);")
        self.leftLayout.addWidget(lbl)
        self._left_headers.append((lbl, text))

    # -----------------------------

    def _add_row(self, text, icon):

        row = QWidget()
        row.setStyleSheet("background: transparent;")

        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(ICON_SIZE, ICON_SIZE)
        icon_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        icon_lbl.setStyleSheet("background: transparent;")
        if icon is not None and not icon.isNull():
            icon_lbl.setPixmap(icon.pixmap(ICON_SIZE, ICON_SIZE))

        text_lbl = QLabel(text)
        text_lbl.setFont(self._font())
        text_lbl.setTextFormat(Qt.PlainText)
        text_lbl.setWordWrap(True)
        text_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        text_lbl.setStyleSheet(
            "background: transparent; color: rgb(235,235,235);"
        )

        h.addWidget(icon_lbl)
        h.addWidget(text_lbl, 1)

        self.leftLayout.addWidget(row)
        self._left_rows.append((icon_lbl, text_lbl, text))

    # -----------------------------

    def _rebuild_left(self):

        self._clear_left()

        programs = self._left_data.get("programs", [])
        folders = self._left_data.get("folders", [])

        if programs:
            self._add_header(tr("Программы:"))
            for name, exe_path in programs:
                self._add_row(name, icon_for_file(exe_path))

        if folders:
            self._add_header(tr("Папки:"))
            for path in folders:
                self._add_row(path, icon_for_file(path))

        # 🔴 Строки — СВЕРХУ, естественной высоты, с родными
        # межстрочными отступами (как у прежней отдельной плашки):
        # лишняя высота уходит в пустой НИЗ плашки (визуальная
        # рамка), а НЕ раздвигает строки. Скролл — когда строки
        # дойдут до низа.
        self.leftLayout.addStretch(1)

    # -----------------------------

    def set_content(self, left_data, right, text_size):

        self._left_data = left_data or {"programs": [], "folders": []}
        self._right_text = right or ""
        self.textSize = text_size

        self.right.setFont(self._font())
        self.right.setText(self._right_text)

        self._rebuild_left()
        self.update()

    # -----------------------------

    def set_panel_color(self, gray, alpha):
        self.panelColor = QColor(gray, gray, gray, int(255 * (alpha / 100)))
        self.update()

    # -----------------------------

    def _text_width(self, text, fm):
        lines = text.splitlines() or [""]
        return max((fm.horizontalAdvance(line) for line in lines), default=0)

    # -----------------------------

    def _wrapped_height(self, text, fm, width):
        # Высота текста с учётом переноса по словам при фиксированной ширине.
        if not text:
            return fm.lineSpacing()
        rect = fm.boundingRect(
            QRect(0, 0, max(1, width), 100000),
            int(Qt.AlignTop | Qt.TextWordWrap),
            text,
        )
        return rect.height()

    # -----------------------------

    def _left_natural_width(self, fm):
        # 🔴 Естественная ширина левой колонки: самая широкая строка
        # С местом под иконку, плюс заголовки секций.
        natural = 0

        for _lbl, text in self._left_headers:
            natural = max(natural, fm.horizontalAdvance(text))

        for _icon, _lbl, text in self._left_rows:
            natural = max(natural, ICON_SLOT + fm.horizontalAdvance(text))

        return natural

    # -----------------------------

    def _left_height(self, fm, width):
        # 🔴 Высота левой колонки: заголовки секций + строки,
        # у строк текст переносится в ширину (width - иконка).
        height = 0
        text_w = max(1, width - ICON_SLOT)

        for _lbl, _text in self._left_headers:
            height += fm.height() + HEADER_PAD

        for _icon, _lbl, text in self._left_rows:
            rect = fm.boundingRect(
                QRect(0, 0, text_w, 100000),
                int(Qt.AlignTop | Qt.TextWordWrap),
                text,
            )
            height += max(ICON_SIZE, rect.height()) + ROW_SPACING

        if height:
            height -= ROW_SPACING

        return height

    # -----------------------------

    def _column_widths(self, fm, available_for_columns, left_natural,
                       fill_width=False):
        # 🔴 fill_width: растянуть колонки ТОЧНО на доступную ширину —
        # для встроенной в превью плашки (ровно в ширину окна).
        # Без флага (полноэкранный режим) колонки остаются
        # естественной ширины — компактный вид, как раньше.
        margins = self.contentLayout.contentsMargins()
        gap = self.contentLayout.spacing()
        inner_margin_w = margins.left() + margins.right()

        # Естественная ширина колонки — по самой длинной строке,
        # но ограничена снизу MIN и сверху MAX.
        right_natural = self._text_width(self._right_text, fm)

        left_w = min(MAX_COL_WIDTH, max(MIN_COL_WIDTH, left_natural))
        right_w = min(MAX_COL_WIDTH, max(MIN_COL_WIDTH, right_natural))

        # 🔴 РАВНОМЕРНОЕ стягивание/растягивание:
        # колонки пропорционально сжимаются, если их сумма
        # не помещается в доступную ширину, и РАСТЯГИВАЮТСЯ,
        # если места больше — плашка всегда ровно на заданную
        # ширину.
        available = available_for_columns - inner_margin_w - gap

        if available > 0:

            total_cols = left_w + right_w

            if total_cols > available:

                scale = available / total_cols

                left_w = max(1, int(left_w * scale))
                right_w = max(1, int(right_w * scale))

                # 🔴 Финальная корректировка: точно влезаем в available.
                while left_w + right_w > available and (left_w > 1 or right_w > 1):
                    if left_w >= right_w and left_w > 1:
                        left_w -= 1
                    elif right_w > 1:
                        right_w -= 1

            elif fill_width and total_cols < available:

                extra = available - total_cols
                left_w += extra // 2
                right_w += extra - extra // 2

        return left_w, right_w

    # -----------------------------

    def preferred_size(self, max_size, fill_width=False):

        # 🔴 Доступная ширина панели = то, что реально есть под неё.
        # Колонки стянутся равномерно под эту ширину.
        available_w = max(MIN_PANEL_WIDTH, max_size.width())

        fm = QFontMetrics(self._font())
        margins = self.contentLayout.contentsMargins()
        gap = self.contentLayout.spacing()
        inner_margin_w = margins.left() + margins.right()
        inner_margin_h = margins.top() + margins.bottom()

        left_w, right_w = self._column_widths(
            fm, available_w, self._left_natural_width(fm),
            fill_width=fill_width,
        )

        # Высота колонок: левая — по строкам с иконками,
        # правая — по переносу текста.
        left_h = self._left_height(fm, left_w)
        right_h = self._wrapped_height(self._right_text, fm, right_w)

        total_w = inner_margin_w + left_w + gap + right_w
        total_h = max(left_h, right_h) + inner_margin_h

        # 🔴 fill_width: ширина — РОВНО заданная (встроенная плашка
        # малого превью); без флага — естественная по содержимому
        # (отдельная плашка полноэкранного режима).
        if fill_width:
            size = QSize(available_w, total_h)
        else:
            size = QSize(total_w, total_h)

        # 🔴 Фиксируем ширины: заголовки на всю колонку, текст строк —
        # с вычетом места под иконку (там и происходит перенос).
        for lbl, _text in self._left_headers:
            lbl.setFixedWidth(left_w)

        for _icon, text_lbl, _text in self._left_rows:
            text_lbl.setFixedWidth(max(1, left_w - ICON_SLOT))

        self.right.setFixedWidth(right_w)
        self.leftBox.setFixedWidth(left_w)
        self.adjustSize()
        return size

    # -----------------------------

    def show_at(self, pos, max_size, fill_width=False):
        # 🔴 max_size: ширина ставится ровно заданной ТОЛЬКО в
        # fill_width; высота — сколько нужно содержимому, но
        # не больше потолка. В полноэкранном режиме (без флага)
        # плашка — естественного компактного размера.
        size = self.preferred_size(max_size, fill_width=fill_width)
        if fill_width:
            width = max_size.width()
        else:
            width = min(size.width(), max(1, max_size.width()))
        height = min(size.height(), max(1, max_size.height()))
        self.setGeometry(pos.x(), pos.y(), width, height)
        self.show()
        self.raise_()

    # -----------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.panelColor)


class _ShotArea(QWidget):
    # 🔴 Верхняя часть малого превью — сам скриншот. Высота — по
    # пропорции скриншота при полной ширине окна (2 монитора —
    # ниже, 1 монитор — выше). ЗОНА НАВЕДЕНИЯ для раскрытия
    # полноэкранного превью = ГРАНИЦЫ этого скриншота.

    def __init__(self, parent=None):

        super().__init__(parent)

        self.pixmap = QPixmap()
        self.backgroundGray = 60
        self.setMinimumHeight(40)

    # -----------------------------

    def fit_pixmap(self, pixmap, width):

        self.pixmap = QPixmap(pixmap) if pixmap is not None else QPixmap()

        if self.pixmap.isNull():
            # Скриншота нет — типичная пропорция монитора 16:9,
            # в области будет подсказка «Нет скриншота».
            height = max(60, round(width * 9 / 16))
        else:
            height = max(
                40,
                round(width * self.pixmap.height() / self.pixmap.width()),
            )

        self.setFixedHeight(height)
        self.update()

    # -----------------------------

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.fillRect(
            self.rect(),
            QColor(
                self.backgroundGray,
                self.backgroundGray,
                self.backgroundGray,
            ),
        )

        if self.pixmap.isNull():
            painter.setPen(QColor(160, 160, 160))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                tr("Нет скриншота\n(пересохраните пресет)"),
            )
            return

        painter.drawPixmap(
            self.rect(),
            self.pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ),
        )


class PreviewWindow(QWidget):
    # 🔴 МАЛОЕ превью = ОДНО окно высотой с главное окно программы:
    # сверху — скриншот (зона наведения для раскрытия), снизу —
    # текстовый состав пресета; если текст не влезает до низа —
    # он ПРОКРУЧИВАЕТСЯ колёсиком (внутренний скролл).
    #
    # ПОЛНОЭКРАННОЕ превью: дети скрываются, скриншот рисуется на
    # весь экран, отдельная плашка InfoPanel — по центру (как было).

    def __init__(self, parent=None):

        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint)

        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # 🔴 Защита от белой вспышки при показе/скрытии окна на Windows:
        # виджет сам закрашивает фон, система не заливает его белым.
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.pixmap = QPixmap()
        self.dimOpacity = 30
        self.fullscreen = False
        self.backgroundGray = 60

        # 🔴 Порядок в малом режиме: False — скриншот сверху, текст
        # снизу; True — текст сверху, скриншот снизу (пресет в нижней
        # половине списка).
        self.textOnTop = False

        # 🔴 Отдельная плашка — ТОЛЬКО для полноэкранного режима
        # (по центру экрана, показывает её PreviewExpander).
        self.infoPanel = InfoPanel()

        self.infoLeft = ""
        self.infoRight = ""
        self.textSize = 18

        # --- малый режим: скриншот сверху, текст снизу ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.shotArea = _ShotArea(self)
        layout.addWidget(self.shotArea)

        self.infoScroll = QScrollArea(self)
        # 🔴 widgetResizable(True): встроенная плашка держит ширину
        # окна; по высоте — свой минимум, дальше скролл.
        self.infoScroll.setWidgetResizable(True)
        self.infoScroll.setFrameShape(QFrame.Shape.NoFrame)
        self.infoScroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.infoScroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.infoScroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        self.embeddedInfo = InfoPanel(parent=self)
        self.infoScroll.setWidget(self.embeddedInfo)
        layout.addWidget(self.infoScroll, 1)

    # -----------------------------

    def set_preview(self, file_name):
        self.pixmap = QPixmap(file_name)
        if not self.fullscreen:
            self.shotArea.fit_pixmap(self.pixmap, self.width())
        self.update()

    def set_info(self, left, right):
        self.infoLeft = left or ""
        self.infoRight = right or ""
        for panel in (self.infoPanel, self.embeddedInfo):
            panel.set_content(self.infoLeft, self.infoRight, self.textSize)
        self.update()

    def set_text_size(self, size):
        self.textSize = size
        for panel in (self.infoPanel, self.embeddedInfo):
            panel.set_content(self.infoLeft, self.infoRight, self.textSize)
        self.update()

    def set_dim(self, opacity):
        self.dimOpacity = opacity
        self.update()

    def set_panel_color(self, gray, alpha=None):
        self.backgroundGray = gray
        self.shotArea.backgroundGray = gray
        if alpha is None:
            alpha = 40
        for panel in (self.infoPanel, self.embeddedInfo):
            panel.set_panel_color(gray, alpha)
        self.update()

    # -----------------------------

    def set_text_on_top(self, flag):
        # 🔴 Пресет в НИЖНЕЙ половине списка: текст сверху,
        # скриншот ВНИЗУ — курсору от строки не тянуться наверх.
        flag = bool(flag)
        if self.textOnTop == flag:
            return
        self.textOnTop = flag
        lay = self.layout()
        lay.removeWidget(self.shotArea)
        lay.removeWidget(self.infoScroll)
        if flag:
            lay.addWidget(self.infoScroll, 1)
            lay.addWidget(self.shotArea)
        else:
            lay.addWidget(self.shotArea)
            lay.addWidget(self.infoScroll, 1)
        self.update()

    # -----------------------------

    def set_fullscreen(self, state):
        self.fullscreen = state

        # 🔴 Полноэкранное превью ПРОЗРАЧНО для мыши: оно перекрывает
        # весь экран «поверх всех окон», и если оно принимает клики —
        # пользователь не может нажать никуда (наблюдалось как
        # «чёрное окно» / «невидимый слой», перехватывающий ввод).
        # Малое превью мышью интерактивно (по скриншоту раскрывается).
        self.setAttribute(Qt.WA_TransparentForMouseEvents, state)

        # 🔴 Полный режим: дети (скриншот + текст) скрываются —
        # paintEvent рисует скриншот на весь экран. Малый: дети
        # возвращаются, ОТЕЛЬНАЯ плашка гасится (она — только
        # для полного режима).
        if state:
            self.shotArea.hide()
            self.infoScroll.hide()
        else:
            self.shotArea.show()
            self.infoScroll.show()
            self.infoPanel.hide()

        self.update()

    def show_info_panel(self, pos, max_size, fill_width=False):
        self.infoPanel.show_at(pos, max_size, fill_width=fill_width)

    def hide_info_panel(self):
        self.infoPanel.hide()

    # -----------------------------

    def refresh_layout(self):
        # 🔴 Пересчёт малого режима: высота скриншота по пропорции
        # и минимум встроенной плашки (выше — скролл текста). Плашка
        # под скриншотом в прежнем формфакторе (колонки не растяги
        # ваются), заполняет ширину окна фоном и растёт вниз до
        # низа окна (widgetResizable), при длинном тексте — скролл.
        if self.fullscreen:
            return

        width = max(1, self.width())
        self.shotArea.fit_pixmap(self.pixmap, width)

        size = self.embeddedInfo.preferred_size(
            QSize(width, 1_000_000)
        )
        self.embeddedInfo.setMinimumSize(width, size.height())

    # -----------------------------

    def shot_global_rect(self):
        # 🔴 Глобальный rect зоны СКРИНШОТА (верх окна малого
        # превью) — зона наведения для раскрытия. Наведение на
        # текст НЕ раскрывает (текст читают/скроллят).
        top_left = self.shotArea.mapToGlobal(QPoint(0, 0))
        return QRect(top_left, self.shotArea.size())

    # -----------------------------

    def fullscreen_pixmap_rect(self):
        if self.pixmap.isNull():
            return QRect()

        screen = self.rect()
        scaled = self.pixmap.scaled(
            screen.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        x = (screen.width() - scaled.width()) // 2
        y = (screen.height() - scaled.height()) // 2

        return QRect(x, y, scaled.width(), scaled.height())

    # -----------------------------

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.fillRect(
            self.rect(),
            QColor(self.backgroundGray, self.backgroundGray, self.backgroundGray),
        )

        if not self.fullscreen:
            # Малый режим: скриншот и текст рисуют ДОЧЕРНИЕ виджеты.
            return

        if self.pixmap.isNull():
            painter.setPen(QColor(160, 160, 160))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                tr("Нет скриншота\n(пересохраните пресет)"),
            )
            return

        target = self.fullscreen_pixmap_rect()
        painter.drawPixmap(
            target.topLeft(),
            self.pixmap.scaled(
                target.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ),
        )
