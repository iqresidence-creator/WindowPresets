from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
)

# 🔴 Роль для цвета плашки строки (Qt.UserRole занят данными пресета).
CHIP_COLOR_ROLE = Qt.ItemDataRole.UserRole + 101
# 🔴 Список hex-цветов вкладок пресета для полоски.
TAG_COLORS_ROLE = Qt.ItemDataRole.UserRole + 102
# 🔴 Собственный цвет подложки пресета (hex, под названием).
PRESET_COLOR_ROLE = Qt.ItemDataRole.UserRole + 103
# 🔴 Строка-разделитель («пустой пресет»-заголовок).
SEPARATOR_ROLE = Qt.ItemDataRole.UserRole + 104


class WrappingDelegate(QStyledItemDelegate):
    # --------------------------------------
    # Делегат с переносом текста строк на новую строку.
    #
    # QStyledItemDelegate сам умеет рисовать перенесённый текст,
    # если в опции стоит флаг WrapText — высота строки при этом
    # тоже считается по перенесённому тексту. В option.text —
    # КОПИЯ только для отрисовки: разрезаем «длинные слова» без
    # пробелов нулевыми пробелами (ZWSP), реальный item.text()
    # не меняется.
    #
    # Строки с цветом (CHIP_COLOR_ROLE) рисуются закрашенной
    # плашкой; цвет текста — чёрный/белый по яркости.
    # --------------------------------------

    def initStyleOption(self, option, index):

        super().initStyleOption(option, index)

        option.features |= QStyleOptionViewItem.ViewItemFeature.WrapText

        if option.text:
            option.text = "\u200b".join(option.text)

    # --------------------------------------

    def paint(self, painter, option, index):

        color = index.data(CHIP_COLOR_ROLE)
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        tag_colors = index.data(TAG_COLORS_ROLE)
        preset_color = index.data(PRESET_COLOR_ROLE)
        is_separator = bool(index.data(SEPARATOR_ROLE))
        has_strip = bool(tag_colors)
        has_preset_color = bool(preset_color)
        # 🔴 Чекбокс есть только когда у элемента ЕСТЬ данные
        # галочки (CheckStateRole) и флаг ItemIsUserCheckable —
        # в Qt6 флаг по умолчанию стоит у ВСЕХ строк, и без
        # проверки пустые чекбоксы вылезали во всех списках.
        has_check = check_state is not None and bool(
            index.flags() & Qt.ItemFlag.ItemIsUserCheckable
        )

        if (
            color is None
            and not has_check
            and not has_strip
            and not has_preset_color
            and not is_separator
        ):
            # Обычные строки всех списков — штатная отрисовка,
            # ничего поверх не дорисовываем.
            super().paint(painter, option, index)
        else:
            # 🔴 Полностью СВОЙ рендер БЕЗ super().paint: базовый
            # делегат рядом с нашим чекбоксом рисует штатный серый
            # индикатор-двойник — так он не рисуется вовсе.
            rect = option.rect.adjusted(2, 1, -2, -1)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if color is not None:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(rect, 6, 6)
            elif has_preset_color:
                # 🔴 Подложка собственного цвета пресета (под текстом).
                # 🔴 Прозрачность — настройка preset_color_opacity (%),
                # живёт на делегате (ставит apply_theme); 100 = непрозрачно.
                c = QColor(str(preset_color))
                opacity = getattr(self, "colorOpacity", 100)
                if opacity < 100:
                    c.setAlpha(max(10, int(255 * opacity / 100)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(c)
                painter.drawRoundedRect(rect, 6, 6)
            elif is_separator:
                # 🔴 Разделитель: тёмная полоса-заголовок (свой цвет
                # разделителя красится веткой has_preset_color выше).
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, 55))
                painter.drawRoundedRect(rect, 6, 6)
            # подсветка наведения/выделения — и для плашки, и для обычного фона
            selected = bool(option.state & QStyle.StateFlag.State_Selected)
            hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
            if selected or hovered:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 70 if selected else 35))
                painter.drawRoundedRect(rect, 6, 6)
            text_left = 8
            if has_check:
                # 🔴 enum≠int в PySide 6.11: сравнение только так,
                # прямое == дало бы False.
                checked = Qt.CheckState(check_state) == Qt.CheckState.Checked
                box = QRect(rect.left() + 8, rect.center().y() - 8, 16, 16)
                self._draw_check_box(painter, box, checked)
                text_left = 34
            if has_strip:
                # 🔴 Полоски ОТДОРАВНИВАЮТ название: текст начинается
                # сразу после полосок, а не поверх них (полоски:
                # 3px отступ + по 4px на цвет, см. блок ниже).
                text_left = max(
                    text_left,
                    3 + min(len(tag_colors), 8) * 4 + 4,
                )
            text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            bg_color = color if color is not None else preset_color
            if bg_color:
                chip = QColor(str(bg_color))
                luminance = (
                    0.299 * chip.red()
                    + 0.587 * chip.green()
                    + 0.114 * chip.blue()
                )
                text_color = (
                    QColor(0, 0, 0) if luminance > 140 else QColor(255, 255, 255)
                )
            else:
                # 🔴 Цвет текста — по яркости ФОНА списка: QPalette.Text
                # ненадёжен (давал серый #858585, текст сливался).
                base = option.palette.color(QPalette.ColorRole.Base)
                base_lum = (
                    0.299 * base.red()
                    + 0.587 * base.green()
                    + 0.114 * base.blue()
                )
                text_color = (
                    QColor(235, 235, 235) if base_lum < 128
                    else QColor(20, 20, 20)
                )
            painter.setPen(text_color)
            painter.setFont(option.font)
            if is_separator:
                # 🔴 Разделитель — текст как у заголовка: жирный,
                # по центру строки.
                bold = QFont(option.font)
                bold.setBold(True)
                painter.setFont(bold)
            align = Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap
            if is_separator:
                align |= Qt.AlignmentFlag.AlignHCenter
            painter.drawText(
                rect.adjusted(text_left, 0, -8, 0),
                align,
                "\u200b".join(text),
            )
            painter.restore()

        # 🔴 Полоски цветов вкладок пресета — рисуем в конце, ПОСЛЕ
        # обеих веток, чтобы они были видны поверх выделения.
        if tag_colors:
            # 🔴 Полоски цветов вкладок пресета — РЯДОМ по горизонтали:
            # каждая 2px во всю высоту строки, отступ между ними 2px.
            r = option.rect
            painter.save()
            x = r.left() + 3
            for hexc in list(tag_colors)[:8]:
                painter.fillRect(
                    QRect(x, r.top() + 2, 2, r.height() - 4),
                    QColor(str(hexc)),
                )
                x += 4  # 2px полоска + 2px отступ
            painter.restore()

    # --------------------------------------

    def _draw_check_box(self, painter, box, checked):
        # 🔴 Чекбокс, читаемый на любом фоне: тёмная подложка,
        # рамка по состоянию и белая галочка (ручная отрисовка).
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRoundedRect(box, 4, 4)
        # 🔴 Рамка по состоянию: по умолчанию (галочка не стоит) —
        # СВЕТЛО-СЕРАЯ как прежняя штатная, при установленной
        # галочке — БЕЛАЯ (галочка белая).
        pen = QPen(
            QColor(255, 255, 255) if checked else QColor(176, 176, 176),
            2,
        )
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box, 4, 4)
        # checked заранее вычислен вызывающим кодом как
        # Qt.CheckState(check_state) == Qt.CheckState.Checked —
        # 🔴 в PySide 6.11 enum НЕ равен int, прямое == дало бы False.
        if checked:
            painter.drawLine(
                box.left() + 4, box.center().y(),
                box.center().x() - 1, box.bottom() - 4,
            )
            painter.drawLine(
                box.center().x() - 1, box.bottom() - 4,
                box.right() - 3, box.top() + 3,
            )


class OrderableListWidget(QListWidget):
    # --------------------------------------
    # QListWidget с перетаскиванием строк мышью (как вкладки
    # в Google Chrome) и переносом длинных названий.
    # После перетаскивания испускает order_changed — вызывающий
    # код сохраняет новый порядок.
    # --------------------------------------

    order_changed = Signal()

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.setDefaultDropAction(Qt.MoveAction)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setItemDelegate(WrappingDelegate(self))

        # 🔴 Drag-скролл: при перетаскивании строки к краю списка
        # он сам плавно прокручивается (зона 70px) — можно доехать
        # до далёкой позиции, не отпуская захват.
        self.setAutoScroll(True)
        self.setAutoScrollMargin(70)
        self.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

    # --------------------------------------

    def dropEvent(self, event):

        super().dropEvent(event)

        # 🔴 У QListWidget InternalMove реализован через
        # dropMimeData (вставка+удаление), сигнал rowsMoved модели
        # НЕ срабатывает — поэтому сигнализируем из dropEvent.
        if event.source() is self:
            self.order_changed.emit()
