from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyleOptionTab,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from core.settings_manager import SettingsManager
from core.i18n import tr
from ui.icon_button import IconButton
from ui.orderable_list import OrderableListWidget
from ui.preset_list import PresetListController

# 🔴 ЖЕЛЕЗНАЯ ШИРИНА (владелец): главное окно, колонки пикера,
# любые новые элементы — по умолчанию ВСЕ 360px.
MAIN_WIDTH = 360


class TabsScrollArea(QScrollArea):
    """Горизонтальная прокрутка панели вкладок.

    Своя (а не встроенная QTabBar): текущая вкладка ЦЕНТРИРУЕТСЯ
    при переключении, колесо мыши листает вкладки влево/вправо
    (встроенный скролл QTabBar колесом не листает).
    """

    def wheelEvent(self, event):

        bar = self.widget()
        if bar is not None:
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value()
                - event.angleDelta().y() // 2
            )
            event.accept()
            return

        super().wheelEvent(event)


class ColoredTabBar(QTabBar):

    # 🔴 Двойной клик по вкладке — быстрый поиск пресета
    # (MainWindow.open_preset_picker, см. подключение ниже).
    allDoubleClicked = Signal(int)

    # 🔴 Двойной клик по обычной вкладке — переименование
    # (MainWindow.tab_rename, подключается у presetTabs).
    tabDoubleClicked = Signal(int)

    """QTabBar с поддержкой цвета вкладок (настройка tab_colors):
    окрашенная вкладка рисуется плашкой, цвет текста — чёрный/белый
    по яркости.

    Флаг suppress_current: «текущая» вкладка рисуется БЕЗ выделения —
    нужно, чтобы при активной закреплённой «Все» основная панель не
    выглядела выбранной (QTabBar не позволяет снять выделение через
    setCurrentIndex(-1)). Клик по такой вкладке всё равно обрабатывается
    (см. mousePressEvent).
    """

    def __init__(self, parent=None):

        super().__init__(parent)

        self._colors = {}
        self.suppress_current = False
        # 🔴 Компакт-режим: ВСЕ вкладки по 4 буквы + «…». Включается
        # владельцем окна, когда полные имена не помещаются в
        # просмотровое окошко (см. _update_tabs_compact).
        self.compact = False

    # --------------------------------------------------

    def tabSizeHint(self, index):

        if self.compact:
            return self.minimumTabSizeHint(index)

        return super().tabSizeHint(index)

    # --------------------------------------------------

    def set_compact(self, flag):

        flag = bool(flag)
        if self.compact != flag:
            self.compact = flag

    # --------------------------------------------------

    def set_tab_colors(self, colors):

        self._colors = {
            str(k): v for k, v in (colors or {}).items()
        }
        self.update()

    # --------------------------------------------------

    def set_suppress_current(self, flag):

        flag = bool(flag)
        if self.suppress_current != flag:
            self.suppress_current = flag
            self.update()

    # --------------------------------------------------

    def mousePressEvent(self, event):

        index = self.tabAt(event.position().toPoint())
        suppressed_click = (
            self.suppress_current and index == self.currentIndex()
        )

        super().mousePressEvent(event)

        # Клик по подавленной вкладке: currentIndex не меняется,
        # currentChanged не придёт — сигнал подаём сами.
        if suppressed_click and index >= 0:
            self.currentChanged.emit(index)

    # --------------------------------------------------

    def mouseDoubleClickEvent(self, event):

        index = self.tabAt(event.position().toPoint())

        super().mouseDoubleClickEvent(event)

        # 🔴 Двойной клик по вкладке (используется «Все» в
        # закреплённой панели) — быстрый поиск пресета.
        if index >= 0:
            self.allDoubleClicked.emit(index)
            # 🔴 Двойной клик по обычной вкладке — переименование
            # (подключается у панели presetTabs).
            self.tabDoubleClicked.emit(index)

    # --------------------------------------------------

    def minimumTabSizeHint(self, index):
        # 🔴 Минимальная ширина вкладки: 4 первых буквы + «…» —
        # при нехватке места вкладки сокращаются, но остаются
        # опознаваемыми.
        #
        # 🔴 БЕЗ super().minimumTabSizeHint(): он внутри зовёт
        # виртуальный tabSizeHint (наш override) — бесконечная
        # рекурсия. Высоту считаем от шрифта сами.
        fm = self.fontMetrics()
        text = self.tabText(index)
        short = (text[:4] + "…") if len(text) > 4 else text
        width = fm.horizontalAdvance(short) + 28
        height = fm.height() + 14
        return QSize(max(width, 40), height)

    # --------------------------------------------------

    def paintEvent(self, event):

        painter = QPainter(self)

        for index in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, index)

            if self.suppress_current and index == self.currentIndex():
                option.state &= ~QStyle.StateFlag.State_Selected
                option.state &= ~QStyle.StateFlag.State_HasFocus
                option.state &= ~QStyle.StateFlag.State_Active

            option.rect = self.tabRect(index)
            self.style().drawControl(
                QStyle.ControlElement.CE_TabBarTab, option, painter, self
            )

            hexcolor = self._colors.get(self.tabText(index))
            if not hexcolor:
                continue

            color = QColor(hexcolor)
            if not color.isValid():
                continue

            rect = self.tabRect(index).adjusted(1, 2, -1, -2)
            if rect.width() <= 0 or rect.height() <= 0:
                continue

            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            fill = QColor(color)
            fill.setAlpha(200)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 5, 5)

            window = QColor(self.palette().color(QPalette.ColorRole.Window))
            blended = QColor(
                int(color.red() * 0.78 + window.red() * 0.22),
                int(color.green() * 0.78 + window.green() * 0.22),
                int(color.blue() * 0.78 + window.blue() * 0.22),
            )
            luminance = (
                0.299 * blended.red()
                + 0.587 * blended.green()
                + 0.114 * blended.blue()
            )
            painter.setPen(
                QColor(0, 0, 0) if luminance > 140 else QColor(255, 255, 255)
            )
            # При узкой вкладке текст сокращается (элайд), как у стиля.
            text = painter.fontMetrics().elidedText(
                self.tabText(index), Qt.TextElideMode.ElideRight,
                rect.width() - 8,
            )
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


class StatusBar(QLabel):
    # --------------------------------------
    # Нижняя информационная строка. Поверх обычных сообщений
    # знает про СОСТОЯНИЕ ОЖИДАНИЯ: если при старте найдено
    # обновление — в ожидании горит зелёная заметка с номером
    # версии (просьба владельца), иначе — «Готово».
    # Рабочие сообщения поверх заметки обычные, при возврате
    # в ожидание (наведение/уход с кнопок, старт) заметка
    # возвращается.
    # --------------------------------------

    def __init__(self):

        super().__init__(tr("Готово", "status"))

        self.update_tag = None

    # --------------------------------------------------

    def set_idle(self):
        # Режим ожидания: зелёная заметка об обновлении или «Готово».
        if self.update_tag:
            self.setText(
                tr("Есть новая версия «{}»").format(self.update_tag)
            )
            self.setStyleSheet("color: rgb(102, 187, 106);")
        else:
            self.setStyleSheet("")
            self.setText(tr("Готово", "status"))

    # --------------------------------------------------

    def set_update_tag(self, tag):

        self.update_tag = tag
        self.set_idle()

    # --------------------------------------------------

    def clear_update_tag(self):

        self.update_tag = None
        self.set_idle()


def build_ui(window):

    settings = SettingsManager.load()

    layout = QVBoxLayout(window)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    # ---------------------------
    # Вкладки пресетов (сверху)
    # ---------------------------

    # 🔴 Один ряд: [◀] «Все» (закреплена, с отступом) | остальные
    # вкладки (горизонтальный скролл) [▶]. «Все» не прокручивается —
    # всегда слева; стрелки и колесо листают только остальные.
    window.pinnedTabs = ColoredTabBar()
    window.pinnedTabs.setExpanding(False)
    window.pinnedTabs.setDrawBase(False)
    window.pinnedTabs.setUsesScrollButtons(False)
    window.pinnedTabs.setMovable(False)
    window.pinnedTabs.setMinimumHeight(34)
    window.pinnedTabs.addTab(tr("Все"))

    window.presetTabs = ColoredTabBar()
    window.presetTabs.setExpanding(False)
    window.presetTabs.setDrawBase(True)
    # Скролл — свой (TabsScrollArea): центрирование текущей
    # вкладки и колесо мыши (стрелки ◀ ▶ убраны по решению
    # владельца — листание только колесом).
    window.presetTabs.setUsesScrollButtons(False)
    window.presetTabs.setMovable(True)
    window.presetTabs.setMinimumHeight(34)
    # 🔴 При нехватке места вкладки сокращаются до 4 первых букв + «…».
    window.presetTabs.setElideMode(Qt.ElideRight)

    window.tabsScroll = TabsScrollArea()
    window.tabsScroll.setWidget(window.presetTabs)
    # 🔴 widgetResizable(True): скролл-область сама держит размер
    # панели по ее sizeHint (сумма вкладок). При False размер бара
    # сбрасывался до ширины вьюпорта при каждой пересборке вкладок —
    # прокрутка не появлялась.
    window.tabsScroll.setWidgetResizable(True)
    window.tabsScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    window.tabsScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    window.tabsScroll.setFrameShape(QFrame.NoFrame)
    window.tabsScroll.setFixedHeight(38)

    # 🔴 Один ряд: «Все» (закреплена у ЛЕВОГО края окна, всегда
    # видна) | остальные вкладки в горизонтальном скролле.
    # Прокручиваются ТОЛЬКО остальные вкладки — «Все» на месте.
    # 🔴 НЕ добавлять эти же виджеты в другой layout повторно:
    # Qt переподчиняет виджет новому layout'у — бар выпадает из
    # скролл-области (вкладки обрезаются краем окна, скролл мёртв).
    tab_row = QHBoxLayout()
    tab_row.setContentsMargins(0, 0, 0, 0)
    tab_row.setSpacing(2)
    tab_row.addWidget(window.pinnedTabs)
    tab_row.addSpacing(6)
    tab_row.addWidget(window.tabsScroll, 1)

    layout.addLayout(tab_row)
    # 🔴 Перетаскивание вкладок мышью (как в Chrome); порядок
    # сохраняет MainWindow.tab_moved.
    window.presetTabs.setMovable(True)

    # ---------------------------
    # Плашка текущей вкладки.
    # 🔴 Плоская, БЕЗ рамки — визуально не интерактивная (в отличие
    # от списка пресетов). Текст — просто название вкладки, длинное
    # переносится. Клик открывает список всех вкладок (eventFilter
    # в MainWindow).
    # ---------------------------

    window.currentPresetFrame = QFrame()
    window.currentPresetFrame.setObjectName("currentPresetFrame")
    window.currentPresetFrame.setCursor(QCursor(Qt.PointingHandCursor))
    frame_layout = QVBoxLayout(window.currentPresetFrame)
    frame_layout.setContentsMargins(8, 4, 8, 4)

    window.currentPresetLabel = QLabel(tr("Все"))
    window.currentPresetLabel.setAlignment(Qt.AlignCenter)
    window.currentPresetLabel.setTextFormat(Qt.PlainText)
    window.currentPresetLabel.setWordWrap(True)

    # 🔴 Без этого layout не учитывает heightForWidth: длинное
    # название переносится, но плашка не растягивается по вертикали.
    label_policy = window.currentPresetLabel.sizePolicy()
    label_policy.setHeightForWidth(True)
    window.currentPresetLabel.setSizePolicy(label_policy)

    window.currentPresetLabel.setStyleSheet(
        "background: transparent; font-weight: bold;"
    )
    frame_layout.addWidget(window.currentPresetLabel)

    layout.addWidget(window.currentPresetFrame)

    window.currentPresetFrame.installEventFilter(window)

    # ---------------------------
    # Кнопки управления вкладкой
    # ---------------------------

    tab_buttons = QHBoxLayout()
    tab_buttons.setSpacing(4)

    window.tabAddButton = QPushButton(tr("Добавить"))
    window.tabCopyButton = QPushButton(tr("Дублировать"))
    window.tabRenameButton = QPushButton(tr("Переименовать"))
    window.tabDeleteButton = QPushButton(tr("Удалить"))

    for button in (
        window.tabAddButton,
        window.tabCopyButton,
        window.tabRenameButton,
        window.tabDeleteButton,
    ):
        button.setToolTip(tr("Управление вкладками-фильтрами"))
        # 🔴 Фиксированная высота: в режиме значков текст пуст и без
        # этого кнопка схлопывается до высоты иконки (иконки вкладок
        # заметно меньше нижних) — зона клика стала бы ~20px.
        button.setMinimumHeight(30)
        tab_buttons.addWidget(button, 1)

    window.tabDeleteButton.setToolTip(
        tr("Удалить вкладку (Ctrl+клик — удалить ВСЕ вкладки)")
    )

    layout.addLayout(tab_buttons)

    # ---------------------------
    # Список пресетов — с перетаскиванием строк (порядок
    # сохраняется в MainWindow._save_preset_order).
    # ---------------------------

    window.presetList = OrderableListWidget()
    window.presetList.setMouseTracking(True)
    # 🔴 Мультивыделение (Ctrl/Shift+клик): удаление, теги и цвет
    # применяются ко ВСЕМ выделенным; перетаскивание тащит всё
    # выделение (InternalMove у Qt двигает выделенные строки).
    window.presetList.setSelectionMode(
        QAbstractItemView.SelectionMode.ExtendedSelection
    )

    layout.addWidget(window.presetList, 1)

    window.presetListController = PresetListController(window)

    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    layout.addWidget(line)

    # ---------------------------
    # Кнопки
    # ---------------------------

    row = QHBoxLayout()
    row.setSpacing(4)

    window.btnNew = IconButton("new", None, tr("Новый пресет"))
    # 🔴 Кнопка «Загрузить» — иконка ПРОГРАММЫ (app.png в паке,
    # 256px-копия ico/logo.png): та же логика размера/яркости,
    # что у всех кнопок.
    window.btnLoad = IconButton("app", None, tr("Загрузить пресет"))
    window.btnRefresh = IconButton("refresh", None, tr("Обновить пресет"))
    window.btnClose = IconButton("close", None, tr("Закрыть пресет"))
    window.btnDelete = IconButton(
        "delete", None,
        tr("Удалить пресет (Ctrl+клик — удалить ВСЕ пресеты)")
    )

    buttons = [
        window.btnNew,
        window.btnLoad,
        window.btnRefresh,
        window.btnClose,
        window.btnDelete
    ]

    for button in buttons:
        button.setMinimumHeight(34)
        button.update_icon(settings)
        row.addWidget(button)

    layout.addLayout(row)

    # ---------------------------

    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    layout.addWidget(line)

    # ---------------------------
    # Нижняя панель
    # ---------------------------

    bottom = QHBoxLayout()

    window.statusBar = StatusBar()

    bottom.addWidget(window.statusBar, 1)

    window.btnSettings = IconButton(
        "settings",
        window.statusBar,
        tr("Настройки")
    )

    window.btnSettings.setFixedSize(80, 34)
    window.btnSettings.update_icon(settings)

    bottom.addWidget(window.btnSettings)

    layout.addLayout(bottom)

    # ---------------------------

    for button in buttons:
        button.status_label = window.statusBar

    # ---------------------------
    # Подключения
    # ---------------------------

    window.btnSettings.clicked.connect(window.open_settings)
    window.btnNew.clicked.connect(window.create_preset)
    window.btnDelete.clicked.connect(window.delete_current_preset)

    # 🔴 Загрузка / обновление / закрытие пресета.
    window.btnLoad.clicked.connect(window.load_current_preset)
    window.btnRefresh.clicked.connect(window.refresh_current_preset)
    window.btnClose.clicked.connect(window.close_current_preset)

    window.presetList.itemDoubleClicked.connect(
        window.rename_preset
    )

    window.presetTabs.currentChanged.connect(window.preset_tab_changed)
    window.pinnedTabs.currentChanged.connect(window.pinned_tab_changed)

    # 🔴 Двойной клик по «Все» — быстрый поиск пресета.
    window.pinnedTabs.allDoubleClicked.connect(
        lambda _index: window.open_preset_picker()
    )

    # 🔴 Двойной клик по вкладке — переименовать её.
    window.presetTabs.tabDoubleClicked.connect(
        lambda index: window.tab_rename(
            window.presetTabs.tabText(index)
        )
    )
    window.presetTabs.tabMoved.connect(window.tab_moved)

    # 🔴 Диапазон прокрутки обновляется асинхронно (после компоновки
    # панели) — центрируем текущую вкладку ещё раз по готовности.
    window.tabsScroll.horizontalScrollBar().rangeChanged.connect(
        lambda *_: window._center_current_tab()
    )

    # 🔴 Перетаскивание пресетов: сохранить новый порядок.
    window.presetList.order_changed.connect(window._on_presets_reordered)

    # 🔴 Контекстное меню пресета (правый клик по строке списка).
    window.presetList.setContextMenuPolicy(Qt.CustomContextMenu)
    window.presetList.customContextMenuRequested.connect(
        window.preset_context_menu
    )

    # 🔴 Контекстное меню вкладки (правый клик по вкладке; работает
    # и на закреплённой «Все», и на обычных вкладках).
    window.pinnedTabs.setContextMenuPolicy(Qt.CustomContextMenu)
    window.pinnedTabs.customContextMenuRequested.connect(
        window.tab_context_menu
    )
    window.presetTabs.setContextMenuPolicy(Qt.CustomContextMenu)
    window.presetTabs.customContextMenuRequested.connect(
        window.tab_context_menu
    )

    window.tabAddButton.clicked.connect(window.tab_add)
    window.tabCopyButton.clicked.connect(window.tab_copy)
    window.tabDeleteButton.clicked.connect(window.tab_delete)
    window.tabRenameButton.clicked.connect(window.tab_rename)

    window.presetList.currentRowChanged.connect(
        lambda _: window.preset_changed()
    )

def retranslate_ui(window):
    # 🔴 Перевод СТАТИЧНЫХ надписей окна после смены языка
    # (динамические — меню, статусы, диалоги — переводятся сами:
    # их строки проходят через tr() в момент создания/вызова).
    window.pinnedTabs.setTabText(0, tr("Все"))

    window.tabAddButton.setToolTip(tr("Управление вкладками-фильтрами"))
    window.tabDeleteButton.setToolTip(
        tr("Удалить вкладку (Ctrl+клик — удалить ВСЕ вкладки)")
    )

    for button, hint in (
        (window.btnNew, tr("Новый пресет")),
        (window.btnLoad, tr("Загрузить пресет")),
        (window.btnRefresh, tr("Обновить пресет")),
        (window.btnClose, tr("Закрыть пресет")),
        (window.btnDelete,
         tr("Удалить пресет (Ctrl+клик — удалить ВСЕ пресеты)")),
        (window.btnSettings, tr("Настройки")),
    ):
        button.hint = hint

    window.statusBar.set_idle()
