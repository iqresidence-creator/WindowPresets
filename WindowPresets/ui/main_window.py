from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QIcon,
    QPixmap,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QListWidgetItem,
    QMenu,
    QStyle,
    QSystemTrayIcon,
    QWidget,
)
import os
import time

from core.i18n import tr
from core.icon_manager import IconManager
from core.settings_manager import SettingsManager
from core.preset_storage import PresetStorage
from core.window_applier import WindowApplier
from core.window_closer import WindowCloser

from ui.main_window_ui import build_ui, MAIN_WIDTH
from ui.input_dialog import InputDialog
from ui.update_checker import UpdateCheckWorker
from ui.popup_geometry import (
    clamp_point_within_screen,
    fit_height_within_screen,
    screen_geometry,
)
from ui.preview_manager import PreviewManager
from ui.main_window_controller import MainWindowController
from ui.preview_expander import PreviewExpander
from ui.load_overlay import LoadOverlay
from PySide6.QtWidgets import QAbstractItemView
from ui.orderable_list import (
    TAG_COLORS_ROLE,
    PRESET_COLOR_ROLE,
    SEPARATOR_ROLE,
)


class MainWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.settings = SettingsManager.load()

        self.presets = []
        self.currentPreset = None

        # 🔴 Текущая вкладка-фильтр (вкладки = теги пресетов).
        # «Все» — переводимая строка: ставим ПЕРЕД первым
        # использованием (перекрывает классовый атрибут).
        self.ALL_TAB = tr("Все")
        self.currentTab = self.ALL_TAB

        self.setWindowTitle("WindowPresets")

        # 🔴 Ширина фиксирована, ВЫСОТА растягивается: с большим числом
        # пресетов список можно вытянуть выше. Высота запоминается.
        # 🔴 MAIN_WIDTH=360 — железная ширина (владелец): окно,
        # колонки пикера, новые элементы — всё по умолчанию 360px.
        self.setFixedWidth(MAIN_WIDTH)
        self.setMinimumHeight(330)
        self.resize(
            360,
            max(330, int(self.settings.get("window_height", 330) or 330)),
        )

        # 🔴 «Использовать цвет системы»: при старте перекладываем
        # яркости из ТЕКУЩЕЙ темы Windows (могла смениться с
        # прошлого запуска); в config хранится только галочка.
        if self.settings.get("use_system_color", False):
            from core.system_theme import system_colors

            self.settings.update(system_colors())

        # 🔴 Поверх всех окон — по настройке (window_on_top);
        # плашка загрузки и так всегда topmost независимо от неё.
        self.set_always_on_top(
            bool(self.settings.get("window_on_top", True))
        )

        # PreviewManager должен существовать до build_ui(),
        # потому что build_ui() создаёт PresetListController.
        self.previewManager = PreviewManager(self)

        build_ui(self)

        self.previewExpander = PreviewExpander(self)

        # 🔴 Плашка загрузки пресета («Загружаю...» / «Загружено»).
        self.loadOverlay = LoadOverlay(self)

        self.load_presets()

        self.apply_theme(self.settings)

        self._force_quit = False

        # 🔴 Трей с быстрым доступом (если система позволяет).
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._create_tray()

        # 🔴 Разовая проверка обновлений после старта (владелец:
        # при автозапуске с Windows). С задержкой — старт не ждёт
        # сеть; тихая: нет связи — ничего не происходит.
        self.update_tag = None
        QTimer.singleShot(3000, self._startup_update_check)

    # --------------------------------------------------

    def set_always_on_top(self, enabled):
        # 🔴 setWindowFlag на показанном окне его СКРЫВАЕТ —
        # после смены флага окно нужно показать заново.
        flag = Qt.WindowStaysOnTopHint
        if bool(self.windowFlags() & flag) == bool(enabled):
            return

        self.setWindowFlag(flag, bool(enabled))
        self.show()

    # --------------------------------------------------

    def _create_tray(self):

        icon = self.windowIcon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.SP_ComputerIcon)

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("WindowPresets")

        # 🔴 Меню с родителем self: наследует стиль окна
        # (подсветка наведения как у всех меню программы).
        menu = QMenu(self)

        show_action = menu.addAction(tr("Показать"))
        show_action.triggered.connect(self._restore_from_tray)

        settings_action = menu.addAction(tr("Настройки"))
        settings_action.triggered.connect(self.open_settings)

        menu.addSeparator()

        quit_action = menu.addAction(tr("Выход"))
        quit_action.triggered.connect(self._quit_from_tray)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    # --------------------------------------------------

    def _tray_activated(self, reason):
        # Двойной клик по иконке — показать окно.
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_from_tray()

    # --------------------------------------------------

    def _restore_from_tray(self):

        self.showNormal()
        self.raise_()
        self.activateWindow()

    # --------------------------------------------------

    def _quit_from_tray(self):
        # Выход из трея — настоящий выход, минуя сворачивание.
        self._force_quit = True
        self.close()

        # 🔴 close() недостаточно: если окно УЖЕ спрятано в трей,
        # Qt не видит закрытия видимого окна и приложение не
        # завершается (симптом — «Выход» ничего не делает).
        QGuiApplication.quit()

    # --------------------------------------------------

    def closeEvent(self, event):

        # 🔴 Сворачивать в трей вместо выхода (настройка «Поведение»).
        if not self._force_quit and self.settings.get(
            "minimize_to_tray", False
        ) and self.tray is not None:

            event.ignore()
            self.hide()
            self.tray.showMessage(
                "WindowPresets",
                tr("Программа свёрнута в трей"),
                QSystemTrayIcon.Information,
                2000,
            )
            return

        # 🔴 Запоминаем высоту окна для следующего запуска.
        try:
            settings = SettingsManager.load()
            settings["window_height"] = self.height()
            SettingsManager.save(settings)
        except Exception:
            pass

        event.accept()

    # --------------------------------------------------

    def load_presets(self):

        # 🔴 сохраняем scroll позицию
        scroll = self.presetList.verticalScrollBar().value()

        self.presets = PresetStorage.load()

        # 🔴 Заголовки блокируем от перестройки: currentRowChanged
        # во время наполнения списка ссылался бы на несуществующие строки.
        self.presetList.blockSignals(True)
        self.presetList.clear()

        # 🔴 Группировка по числу мониторов, которые ИСПОЛЬЗУЕТ пресет:
        # «1 монитор» — один или ни одного окна-монитора,
        # «Несколько мониторов» — два и больше.
        groups = [
            (tr("1 монитор"), [p for p in self.presets if p.monitor_count <= 1]),
            (tr("Несколько мониторов"), [p for p in self.presets if p.monitor_count >= 2]),
        ]

        for title, group in groups:

            if not group:
                continue

            self.presetList.addItem(self._header_item(title))

            for preset in group:
                item = QListWidgetItem(preset.name)
                # 🔴 Пресет хранится в данных элемента — заголовки
                # не ломают привязку «строка → пресет».
                item.setData(Qt.UserRole, preset)
                self.presetList.addItem(item)

    def load_presets(self):

        # 🔴 сохраняем scroll позицию
        scroll = self.presetList.verticalScrollBar().value()

        self.presets = PresetStorage.load()

        # 🔴 Вкладка-фильтр: показываем только пресеты с тегом вкладки
        # (вкладка «Все» показывает всё). РАЗДЕЛИТЕЛИ ЛОКАЛЬНЫ ДЛЯ
        # ВКЛАДКИ: видны только там, где созданы (вкладка хранится
        # в tags; пустой tags = создан в «Все»).
        visible = []
        for p in self.presets:
            if p.is_separator:
                sep_tabs = [
                    t for t in (p.tags or [])
                    if t not in ("Все", "All")
                ] or [self.ALL_TAB]
                if self.currentTab in sep_tabs:
                    visible.append(p)
            elif (
                self.currentTab == self.ALL_TAB
                or self.currentTab in (p.tags or [])
            ):
                visible.append(p)

        # 🔴 Заголовки блокируем от перестройки: currentRowChanged
        # во время наполнения списка ссылался бы на несуществующие строки.
        self.presetList.blockSignals(True)

        # 🔴 Мультивыделение переживает пересборку: запоминаем имена
        # выделенных пресетов и восстанавливаем после наполнения —
        # иначе массовая операция (теги) сбрасывала выделение и
        # следующая (цвет) уходила бы одному пресету.
        selected_names = set()

        for it in self.presetList.selectedItems():
            p = it.data(Qt.UserRole) if it is not None else None
            if p is not None:
                selected_names.add(p.name)

        self.presetList.clear()

        # 🔴 Порядок строк = порядок в presets.json. Заголовки групп
        # («1 монитор» / «Несколько мониторов») вставляются ЛЕНИВО —
        # перед первым пресетом своей группы; разделители (заголовки
        # пользователя) стоят ровно там, где их поставил владелец.
        shown_headers = set()
        pending_seps = []

        def _add_preset(preset):
            nonlocal pending_seps

            title = (
                tr("1 монитор")
                if preset.monitor_count <= 1
                else tr("Несколько мониторов")
            )
            if title not in shown_headers:
                self.presetList.addItem(self._header_item(title))
                shown_headers.add(title)

            for sep in pending_seps:
                self._add_separator_item(sep)
            pending_seps = []

            item = QListWidgetItem(preset.name)
            # 🔴 Пресет хранится в данных элемента — заголовки
            # не ломают привязку «строка → пресет».
            item.setData(Qt.UserRole, preset)
            # 🔴 Полоска цветов вкладок: цвета цветных вкладок пресета.
            strip = [
                c for c in (
                    self._tab_colors().get(t)
                    for t in (preset.tags or [])
                ) if c
            ]
            if strip:
                item.setData(TAG_COLORS_ROLE, strip)
            # 🔴 Подложка собственного цвета пресета (в любой вкладке).
            if preset.color:
                item.setData(PRESET_COLOR_ROLE, preset.color)
            self.presetList.addItem(item)

        for preset in visible:

            if preset.is_separator:
                # 🔴 Разделитель ждёт следующий пресет (встанет прямо
                # перед ним, под правильным заголовком группы).
                pending_seps.append(preset)
                continue

            _add_preset(preset)

        # Хвостовые разделители (после последнего пресета) — в конец.
        for sep in pending_seps:
            self._add_separator_item(sep)

        self.presetList.blockSignals(False)

        # 🔴 восстанавливаем scroll позицию
        self.presetList.verticalScrollBar().setValue(scroll)

        # 🔴 Первый видимый пресет выбирается программно и БЕЗ сигналов:
        # иначе при каждом запуске программы само раскрывалось превью.
        # 🔴 НО при пересборке после действий (создание/дубликат/
        # разделитель/drag) выбор НЕ сбрасывается на первый: сначала
        # возвращаем прежний текущий пресет, потом мультивыделение;
        # «первый» — только если ничего не было выбрано (старт).
        self.presetList.blockSignals(True)

        prev_current_name = (
            self.currentPreset.name if self.currentPreset else None
        )

        restored = (
            self._item_by_name(prev_current_name)
            if prev_current_name
            else None
        )

        if restored is not None:
            self.currentPreset = restored.data(Qt.UserRole)
            self.presetList.setCurrentItem(restored)
        else:
            first = self._first_preset_item()

            if first is not None:
                self.currentPreset = first.data(Qt.UserRole)
                self.presetList.setCurrentItem(first)
            else:
                self.currentPreset = None

        # 🔴 Восстановление мультивыделения (см. выше): выделенные
        # до пересборки пресеты остаются выделенными.
        if selected_names:
            for row in range(self.presetList.count()):
                it = self.presetList.item(row)
                p = it.data(Qt.UserRole) if it is not None else None
                if p is not None and p.name in selected_names:
                    it.setSelected(True)

        self.presetList.blockSignals(False)

        self._sync_tabs()
        self._update_preset_frame()

    # --------------------------------------------------

    def _add_separator_item(self, sep):
        # 🔴 Строка-разделитель: как пресет (UserRole — drag/порядок/
        # контекстное меню работают), плюс флаг SEPARATOR_ROLE для
        # отрисовки плашкой-заголовком. Цвет — как у пресета.
        item = QListWidgetItem(sep.name)
        item.setData(Qt.UserRole, sep)
        item.setData(SEPARATOR_ROLE, True)
        if sep.color:
            item.setData(PRESET_COLOR_ROLE, sep.color)
        self.presetList.addItem(item)

    # --------------------------------------------------

    ALL_TAB = "Все"

    def _tab_names(self):
        # 🔴 Вкладки = фильтры. «Все» встроена, остальные задаёт
        # пользователь в настройке preset_tabs.
        try:
            tabs = SettingsManager.load().get("preset_tabs", []) or []
        except Exception:
            tabs = []

        names = []
        for tab in tabs:
            name = str(tab).strip()
            if name and name not in names:
                names.append(name)

        return [self.ALL_TAB] + names

    def _save_tab_names(self, names):
        settings = SettingsManager.load()
        settings["preset_tabs"] = [
            n for n in names if n != self.ALL_TAB
        ]
        SettingsManager.save(settings)

    # --------------------------------------------------

    def _center_current_tab(self):
        # 🔴 Текущая вкладка — в ЦЕНТРЕ прокрутки (если есть куда
        # скроллить): так сразу видно её и соседей.
        bar = self.presetTabs
        index = bar.currentIndex()
        if index < 0:
            return

        rect = bar.tabRect(index)
        if not rect.isValid():
            return

        target = rect.center().x()
        viewport_w = self.tabsScroll.viewport().width()
        hbar = self.tabsScroll.horizontalScrollBar()
        hbar.setValue(target - viewport_w // 2)

    # --------------------------------------------------

    def _update_tabs_compact(self):
        # 🔴 Если ПОЛНЫЕ названия вкладок не помещаются в просмотровое
        # окошко — ВСЕ вкладки переходят в компактный вид (4 буквы +
        # «…»). Влезают — полные названия.
        bar = self.presetTabs
        if bar.count() == 0:
            bar.set_compact(False)
            return

        # Полная ширина всех вкладок (по тексту + запас на поля).
        fm = bar.fontMetrics()
        full_total = sum(
            fm.horizontalAdvance(bar.tabText(i)) + 36
            for i in range(bar.count())
        )
        viewport_w = self.tabsScroll.viewport().width() - 4

        new_compact = full_total > viewport_w
        changed = new_compact != bar.compact
        bar.set_compact(new_compact)

        # Перекомоновка нужна только при смене режима (иначе цикл:
        # _sync_tabs отложенно зовёт нас, мы зовём его...).
        if changed:
            self._sync_tabs()

    # --------------------------------------------------

    def resizeEvent(self, event):

        super().resizeEvent(event)
        # Ширина просмотрового окошка изменилась — пересчитать,
        # помещаются ли полные названия вкладок.
        QTimer.singleShot(0, self._update_tabs_compact)

    # --------------------------------------------------

    def _sync_tabs(self):
        # 🔴 Вкладки строятся из настроенных фильтров. «Все» живёт в
        # отдельной ЗАКРЕПЛЁННОЙ панели (pinnedTabs, всегда слева и
        # видна), остальные — в прокручиваемой presetTabs: их индексы
        # сдвинуты на 1 относительно _tab_names().
        #
        # 🔴 Когда активна «Все», выделение основной панели
        # ПОДАВЛЯЕТСЯ (suppress_current): setCurrentIndex(-1) QTabBar
        # игнорирует — панели всегда нужен выбранный элемент.
        tabs = self.presetTabs
        pinned = self.pinnedTabs

        tabs.blockSignals(True)
        while tabs.count() > 0:
            tabs.removeTab(0)

        names = self._tab_names()
        for name in names[1:]:
            tabs.addTab(name)

        pinned.blockSignals(True)

        if self.currentTab == self.ALL_TAB:
            pinned.setCurrentIndex(0)
            tabs.set_suppress_current(True)
            if tabs.count() > 0:
                tabs.setCurrentIndex(0)
        elif self.currentTab in names:
            tabs.set_suppress_current(False)
            tabs.setCurrentIndex(names.index(self.currentTab) - 1)

        pinned.blockSignals(False)
        tabs.blockSignals(False)

        # На закреплённой «Все» выделение показывается только когда
        # она активна; на основной панели — наоборот.
        pinned.set_suppress_current(self.currentTab != self.ALL_TAB)

        # Текущая вкладка — по центру прокрутки (после компоновки);
        # заодно отложенно пересчитывается компактность названий.
        QTimer.singleShot(0, self._center_current_tab)
        QTimer.singleShot(0, self._update_tabs_compact)

    # --------------------------------------------------

    def pinned_tab_changed(self, index):
        # Клик по закреплённой «Все» — сброс фильтра. Панель обычных
        # вкладок пересобирается, чтобы снять выделение (индекс -1).
        if index < 0 or self.currentTab == self.ALL_TAB:
            return

        self.currentTab = self.ALL_TAB
        self.load_presets()
        self._sync_tabs()
        self._update_preset_frame()

    # --------------------------------------------------

    def _update_preset_frame(self):
        # 🔴 Плашка показывает ТЕКУЩУЮ ВКЛАДКУ — просто название,
        # без префиксов.
        #
        # 🔴 Название режется нулевыми пробелами (ZWSP): QLabel
        # переносит только по границам «слов», а длинное название
        # без пробелов иначе не переносится и вылезает за края.
        name = self.currentTab
        self.currentPresetLabel.setText("\u200b".join(name))

        # 🔴 Цветная вкладка — плашка берёт её цвет (подложка),
        # текст чёрный/белый по яркости; обычная — как у списка.
        hexcolor = None
        if self.currentTab != self.ALL_TAB:
            hexcolor = self._tab_colors().get(self.currentTab)
        if hexcolor:
            color = QColor(hexcolor)
            luminance = (0.299 * color.red() + 0.587 * color.green()
                         + 0.114 * color.blue())
            text = "#000000" if luminance > 140 else "#ffffff"
            self.currentPresetFrame.setStyleSheet(
                "background: " + color.name() + "; "
                "border: none; border-radius: 8px;"
            )
            self.currentPresetLabel.setStyleSheet(
                "background: transparent; color: " + text + "; "
                "font-weight: bold;"
            )
        else:
            self.currentPresetFrame.setStyleSheet("")
            self.currentPresetLabel.setStyleSheet(
                "background: transparent; font-weight: bold;"
            )

    # --------------------------------------------------

    # 🔴 Значки кнопок вкладок — из ЕДИНСТВЕННОГО пака иконок
    # (те же иконки, что у нижних кнопок): «+» новый, ⧉ копия,
    # ⌶ переименование, корзина. Верхние жёстко привязаны к
    # нижним: общие настройки «Яркость/Размер иконок», размер —
    # 70% нижнего (scale_factor=0.7, владелец 03.09).
    TAB_BUTTON_ICONS = {
        "tabAddButton": "new",
        "tabCopyButton": "copy",
        "tabRenameButton": "rename",
        "tabDeleteButton": "delete",
    }

    BUTTON_LABELS = {
        "tabAddButton": "Добавить",
        "tabCopyButton": "Дублировать",
        "tabRenameButton": "Переименовать",
        "tabDeleteButton": "Удалить",
    }

    def _apply_button_texts(self):
        # 🔴 Режим кнопок вкладок: «значки» (иконки единого пака,
        # 70% размера нижних) или «текст» — настройка button_style
        # (галочка «Кнопки — значки»).
        style = self.settings.get("button_style", "icons")

        for attr, icon_name in self.TAB_BUTTON_ICONS.items():
            button = getattr(self, attr)
            if style == "icons":
                button.icon_name = icon_name
                IconManager.apply(
                    button,
                    self.settings,
                    scale_factor=0.7
                )
            else:
                button.setIcon(QIcon())
                button.setText(tr(self.BUTTON_LABELS[attr]))

    # --------------------------------------------------

    def _guard_builtin_tab(self):
        # 🔴 Встроенная вкладка «Все» не изменяется — внятный ответ
        # в строке состояния (кнопки всегда кликабельны).
        if self.currentTab == self.ALL_TAB:
            self.statusBar.setText(
                tr("Вкладка «Все» неизменяемая — сначала создайте свою "
                    "(кнопка «Добавить»)")
            )
            return True
        return False

    # --------------------------------------------------

    def tab_add(self):
        # Создание новой вкладки-фильтра.
        new_name, ok = InputDialog.get_text(
            self,
            tr("Новая вкладка"),
            tr("Название вкладки (фильтра):"),
        )

        new_name = new_name.strip()

        if not ok or not new_name:
            return

        names = self._tab_names()
        # 🔴 Имя встроенной вкладки («Все»/«All» в любом языке)
        # занимать нельзя — иначе идентичность «Все» утечёт в данные.
        if new_name in names or new_name in ("Все", "All"):
            self.statusBar.setText(tr("Вкладка «{}» уже есть").format(new_name))
            return

        names.append(new_name)
        self._save_tab_names(names)

        self.currentTab = new_name
        self.load_presets()
        self.statusBar.setText(tr("Вкладка «{}» создана").format(new_name))

    # --------------------------------------------------

    def preset_tab_changed(self, index):
        # Клик по вкладке = смена фильтра: список пересобирается
        # только из пресетов с тегом этой вкладки. Индексы панели —
        # со сдвигом на 1 (слева закреплённая «Все»).
        names = self._tab_names()

        if not (0 <= index < len(names) - 1):
            return

        self.currentTab = names[index + 1]
        self.load_presets()
        self._update_preset_frame()
        QTimer.singleShot(0, self._center_current_tab)

    # --------------------------------------------------

    @staticmethod
    def _header_item(title):

        item = QListWidgetItem(title)

        # 🔴 Заголовок нельзя выбрать — он не пресет.
        item.setFlags(Qt.NoItemFlags)
        item.setForeground(QBrush(QColor(150, 150, 150)))

        font = item.font()
        font.setBold(True)
        item.setFont(font)

        return item

    # --------------------------------------------------

    def _first_preset_item(self):

        for row in range(self.presetList.count()):
            item = self.presetList.item(row)
            if item is not None and item.data(Qt.UserRole) is not None:
                return item

        return None

    # --------------------------------------------------

    def _item_by_name(self, name):

        for row in range(self.presetList.count()):
            item = self.presetList.item(row)
            if (
                item is not None
                and item.data(Qt.UserRole) is not None
                and item.text() == name
            ):
                return item

        return None

    # --------------------------------------------------

    # 🔴 Управление вкладками-фильтрами (встроенную «Все» менять нельзя).

    def tab_copy(self):

        if self._guard_builtin_tab():
            return

        names = self._tab_names()
        new_name = tr("{} (копия)").format(self.currentTab)
        number = 1
        while new_name in names:
            number += 1
            new_name = tr("{} (копия {})").format(self.currentTab, number)

        # 🔴 Копия встаёт СРАЗУ ЗА оригиналом («Все» всегда первая).
        insert_at = names.index(self.currentTab) + 1
        names.insert(insert_at, new_name)
        self._save_tab_names(names)

        # Пресеты старой вкладки получают и тег копии.
        all_presets = PresetStorage.load()
        for preset in all_presets:
            if self.currentTab in (preset.tags or []):
                preset.tags = list(preset.tags or []) + [new_name]
        PresetStorage.save(all_presets)

        self.currentTab = new_name
        self.load_presets()

    # --------------------------------------------------

    def tab_delete(self):

        # 🔴 Ctrl+клик по корзине вкладки — удалить НЕ выбранную,
        # а ВСЕ вкладки (с усиленным подтверждением).
        if QGuiApplication.queryKeyboardModifiers() & Qt.ControlModifier:
            self.tab_delete_all()
            return

        if self._guard_builtin_tab():
            return

        from ui.confirm_dialog import ConfirmDialog

        answer = ConfirmDialog(
            self,
            tr("Удалить вкладку"),
            tr("Удалить вкладку «{}»?\nСами пресеты останутся, "
               "но потеряют эту вкладку-тег.")
            .format(self.currentTab),
            yes_text=tr("Удалить"),
            no_text=tr("Отмена"),
            big=True,
        ).exec()

        if answer != QDialog.DialogCode.Accepted:
            return

        names = self._tab_names()
        names.remove(self.currentTab)
        self._save_tab_names(names)

        all_presets = PresetStorage.load()
        for preset in all_presets:
            if self.currentTab in (preset.tags or []):
                preset.tags = [
                    t for t in (preset.tags or []) if t != self.currentTab
                ]
        PresetStorage.save(all_presets)

        self.currentTab = self.ALL_TAB
        self.load_presets()

    # --------------------------------------------------

    def tab_delete_all(self):
        # 🔴 Ctrl+клик по корзине вкладок: удалить ВСЕ вкладки-теги.
        # Сами пресеты остаются, но теряют все теги. Цвета вкладок
        # теряют смысл и чистятся, чтобы не копить мёртвые ключи.

        names = [n for n in self._tab_names() if n != self.ALL_TAB]

        if not names:
            self.statusBar.setText(tr("Вкладок нет — удалять нечего"))
            return

        from ui.confirm_dialog import ConfirmDialog

        answer = ConfirmDialog(
            self,
            tr("Удалить все вкладки"),
            tr("Зажат Ctrl: будут удалены ВСЕ вкладки ({} шт.), "
               "а не одна выбранная.\nСами пресеты останутся, "
               "но потеряют все вкладки-теги.")
            .format(len(names)),
            yes_text=tr("Удалить все"),
            no_text=tr("Отмена"),
            yes_danger=True,
            big=True,
        ).exec()

        if answer != QDialog.DialogCode.Accepted:
            return

        self._save_tab_names([])

        all_presets = PresetStorage.load()
        for preset in all_presets:
            preset.tags = []
        PresetStorage.save(all_presets)

        settings = SettingsManager.load()
        settings["tab_colors"] = {}
        SettingsManager.save(settings)
        self.settings = settings

        self.presetTabs.set_tab_colors({})
        self.pinnedTabs.set_tab_colors({})

        self.currentTab = self.ALL_TAB
        self.load_presets()

        self.statusBar.setText(tr("Удалено вкладок: {}").format(len(names)))

    # --------------------------------------------------

    def tab_rename(self, name=None):

        # 🔴 Аргумент — имя вкладки (двойной клик по вкладке);
        # без аргумента/от кнопки (clicked шлёт checked=False) —
        # текущая вкладка.
        old_name = (
            name if isinstance(name, str) and name
            else self.currentTab
        )

        if old_name == self.ALL_TAB:
            self._guard_builtin_tab()
            return

        new_name, ok = InputDialog.get_text(
            self,
            tr("Переименовать вкладку"),
            tr("Новое название вкладки:"),
            text=old_name,
        )

        new_name = new_name.strip()

        if not ok or not new_name or new_name == old_name:
            return

        names = self._tab_names()
        # 🔴 «Все»/«All» — зарезервировано (встроенная вкладка).
        if new_name in names or new_name in ("Все", "All"):
            self.statusBar.setText(tr("Вкладка «{}» уже есть").format(new_name))
            return

        names[names.index(old_name)] = new_name
        self._save_tab_names(names)

        all_presets = PresetStorage.load()
        for preset in all_presets:
            if old_name in (preset.tags or []):
                preset.tags = [
                    new_name if t == old_name else t
                    for t in (preset.tags or [])
                ]
        PresetStorage.save(all_presets)

        if self.currentTab == old_name:
            self.currentTab = new_name
        self.load_presets()

    # --------------------------------------------------

    def eventFilter(self, obj, event):
        # 🔴 Клик по плашке с названием вкладки — открыть список
        # всех вкладок (см. ui/tab_list_popup.py).
        if (
            obj is self.currentPresetFrame
            and event.type() == QEvent.MouseButtonPress
        ):
            self._open_tab_list()
            return True

        return super().eventFilter(obj, event)

    # --------------------------------------------------

    def _open_tab_list(self):
        # Список вкладок под плашкой, на всю оставшуюся высоту окна.
        #
        # Тумблер: клик по плашке при открытом списке закрывает его.
        existing = getattr(self, "_tab_popup", None)
        if existing is not None and existing.isVisible():
            existing.close()
            return

        # 🔴 Replay-защита: клик, закрывший список снаружи, Qt может
        # доставить и плашке — короткое время игнорируем открытие.
        if time.monotonic() < getattr(self, "_tab_list_block_until", 0.0):
            return

        from ui.tab_list_popup import TabListPopup

        frame = self.currentPresetFrame
        bottom_left = frame.mapToGlobal(frame.rect().bottomLeft())

        window_bottom = self.mapToGlobal(QPoint(0, self.height())).y()
        height = max(120, window_bottom - bottom_left.y() - 4)

        # 🔴 Железное правило геометрии: список — целиком в пределах
        # монитора; если внизу мало места — растёт вверх, длинный
        # список листается внутренним скроллом.
        pos = QPoint(bottom_left.x(), bottom_left.y())
        avail = screen_geometry(pos)
        x = max(
            avail.left() + 8,
            min(pos.x(), avail.right() + 1 - frame.width() - 8),
        )
        y, height = fit_height_within_screen(pos, height, min_height=120)

        def reorder(order):
            self._apply_tab_order(order)
            # «Все» возвращается на первое место — нормализуем список.
            popup.refresh(
                self._tab_names(), self.currentTab, self._tab_colors()
            )

        def closed():
            self._tab_list_block_until = time.monotonic() + 0.15
            self._tab_popup = None

        popup = TabListPopup(
            self,
            tabs=self._tab_names(),
            current=self.currentTab,
            global_pos=(x, y),
            width=frame.width(),
            height=height,
            on_click=self._switch_tab,
            on_context=self._tab_menu_from_list,
            on_reorder=reorder,
            on_closed=closed,
            background_color=self.settings.get("window_color", 52),
            tab_colors=self._tab_colors(),
        )
        self._tab_popup = popup

        # 🔴 show(), НЕ exec(): exec() делает диалог модальным —
        # нажатия вне списка блокировались модальностью, и список
        # не закрывался по клику вне. Обычный popup закрывается сам.
        popup.show()

    # --------------------------------------------------

    def _switch_tab(self, name):
        if name == self.currentTab:
            return

        self.currentTab = name
        self.load_presets()
        self._sync_tabs()
        self._update_preset_frame()

    # --------------------------------------------------

    def _apply_tab_order(self, order):
        # 🔴 Порядок вкладок после перетаскивания в списке.
        # «Все» — встроенная, всегда первая (сохранение её
        # отфильтровывает).
        order = [n for n in order if n != self.ALL_TAB]
        self._save_tab_names(order)
        self._sync_tabs()

    # --------------------------------------------------

    def _tab_menu_from_list(self, name, global_pos, popup):
        # ПКМ по вкладке в списке: выбрать её и показать то же
        # меню, что у вкладок сверху (встроенная «Все» — без меню).
        # Список НЕ закрывается — после действия обновляем его.
        if name != self.currentTab:
            self.currentTab = name
            self._sync_tabs()
            self._update_preset_frame()

        self._show_tab_menu(global_pos)

        # Дублирование/переименование/удаление/цвет могли изменить набор.
        popup.refresh(
            self._tab_names(), self.currentTab, self._tab_colors()
        )

    # --------------------------------------------------

    def tab_moved(self, from_index, to_index):
        # 🔴 Перетаскивание вкладок на прокручиваемой панели (как в
        # Chrome): сохраняем новый порядок. «Все» живёт в закреплённой
        # панели и в перетаскивании не участвует.
        names = [self.ALL_TAB] + [
            self.presetTabs.tabText(i)
            for i in range(self.presetTabs.count())
        ]
        self._save_tab_names(names)

    # --------------------------------------------------

    def _on_presets_reordered(self):
        # 🔴 Перетаскивание пресетов в списке. Отложенно: на момент
        # сигнала dropEvent ещё применяется.
        QTimer.singleShot(0, self._save_preset_order)

    # --------------------------------------------------

    def _save_preset_order(self):
        # Порядок списка = порядок в presets.json. Заголовки групп
        # («1 монитор» / «Несколько мониторов») — не пресеты.
        order = []
        for row in range(self.presetList.count()):
            item = self.presetList.item(row)
            preset = item.data(Qt.UserRole) if item is not None else None
            if preset is not None:
                order.append(preset.name)

        all_presets = PresetStorage.load()
        by_name = {p.name: p for p in all_presets}
        visible = set(order)

        reordered = [by_name[n] for n in order if n in by_name]
        # Пресеты, скрытые фильтром вкладки, дописываем в прежнем порядке.
        reordered += [p for p in all_presets if p.name not in visible]

        PresetStorage.save(reordered)

        # Пересборка: заголовки групп встанут на место, порядок внутри
        # групп — сохранённый (перетаскивание между группами бессмысленно:
        # группы определяются числом мониторов пресета).
        self.refresh_presets()

    # --------------------------------------------------

    # 🔴 Палитра для окраски вкладок (меню «Цвет»).
    TAB_PALETTE = [
        ("Красный", "#e53935"),
        ("Оранжевый", "#fb8c00"),
        ("Жёлтый", "#fdd835"),
        ("Зелёный", "#43a047"),
        ("Бирюзовый", "#00897b"),
        ("Голубой", "#00acc1"),
        ("Синий", "#1e88e5"),
        ("Индиго", "#3949ab"),
        ("Фиолетовый", "#8e24aa"),
        ("Розовый", "#d81b60"),
        ("Лайм", "#7cb342"),
        ("Коричневый", "#6d4c41"),
        ("Серый", "#757575"),
    ]

    @staticmethod
    def _color_icon(hexcolor):
        pixmap = QPixmap(14, 14)
        pixmap.fill(QColor(hexcolor))
        return QIcon(pixmap)

    # --------------------------------------------------

    def _tab_colors(self):
        return self.settings.get("tab_colors", {}) or {}

    # --------------------------------------------------

    def _set_tab_color(self, name, color):
        # color: QColor или None (вернуть цвет по умолчанию).
        settings = SettingsManager.load()
        colors = dict(settings.get("tab_colors", {}) or {})

        if color is None:
            colors.pop(name, None)
        else:
            colors[name] = color.name(QColor.NameFormat.HexRgb)

        settings["tab_colors"] = colors
        SettingsManager.save(settings)
        self.settings = settings

        self.presetTabs.set_tab_colors(colors)

        # 🔴 Смена цвета перекрашивает плашку и полоски.
        self.load_presets()
        self._update_preset_frame()

    # --------------------------------------------------

    def _selected_presets(self, anchor=None):
        # 🔴 Мультивыделение: все выделенные пресеты (заголовки групп
        # не пресеты). anchor — пресет правого клика/кнопки: если он
        # ВНЕ текущего выделения, работаем только с ним (стандартное
        # поведение контекстных меню Windows).
        presets = []
        for it in self.presetList.selectedItems():
            p = it.data(Qt.UserRole) if it is not None else None
            if p is not None:
                presets.append(p)
        if anchor is not None and all(
            p.name != anchor.name for p in presets
        ):
            return [anchor]
        if presets:
            return presets
        return [anchor] if anchor is not None else []

    # --------------------------------------------------

    def _set_preset_color(self, preset, color):
        # color: QColor или None (вернуть «по умолчанию» — без подложки).
        # 🔴 Цвет хранится В ПРЕСЕТЕ (presets.json): не зависит от
        # вкладок, переживает переключение фильтров и перезапуск.
        # 🔴 Мультивыделение: цвет ставится ВСЕМ выделенным.
        targets = self._selected_presets(preset)
        value = "" if color is None else color.name(QColor.NameFormat.HexRgb)

        names = {p.name for p in targets}
        for p in targets:
            p.color = value

        presets = PresetStorage.load()
        for p in presets:
            if p.name in names:
                p.color = value
        PresetStorage.save(presets)

        self.load_presets()
        if len(targets) > 1:
            self.statusBar.setText(
                tr("Цвет применён к {} пресетам").format(len(targets))
            )

    # --------------------------------------------------

    def _show_tab_menu(self, global_pos):
        # Контекстное меню текущей вкладки (общее для вкладок
        # сверху и списка по клику на плашку).
        menu = QMenu(self)
        name = self.currentTab

        a_copy = a_rename = a_delete = None
        act_color_default = act_color_other = None
        color_actions = {}

        if name != self.ALL_TAB:
            a_copy = menu.addAction(tr("Дублировать вкладку"))
            a_rename = menu.addAction(tr("Переименовать вкладку"))
            a_delete = menu.addAction(tr("Удалить вкладку"))
            menu.addSeparator()

            color_menu = menu.addMenu(tr("Цвет"))
            act_color_default = color_menu.addAction(tr("По умолчанию"))
            color_menu.addSeparator()
            for title, hexcolor in self.TAB_PALETTE:
                title = tr(title)
                act = color_menu.addAction(
                    self._color_icon(hexcolor), title
                )
                act.setData(hexcolor)
                color_actions[act] = hexcolor
            color_menu.addSeparator()
            act_color_other = color_menu.addAction(tr("Другой цвет..."))

        # 🔴 Меню — целиком в пределах монитора (железное правило
        # геометрии); длинное меню QMenu скроллит сам.
        pos = clamp_point_within_screen(global_pos, menu.sizeHint())
        chosen = menu.exec(pos)

        if chosen is None:
            return

        if chosen is a_copy:
            self.tab_copy()
        elif chosen is a_rename:
            self.tab_rename()
        elif chosen is a_delete:
            self.tab_delete()
        elif chosen is act_color_default:
            self._set_tab_color(name, None)
        elif chosen is act_color_other:
            initial = QColor(self._tab_colors().get(name, "#1e88e5"))
            color = QColorDialog.getColor(initial, self, tr("Цвет вкладки"))
            if color.isValid():
                self._set_tab_color(name, color)
        elif chosen in color_actions:
            self._set_tab_color(name, QColor(color_actions[chosen]))

    # --------------------------------------------------

    def tab_context_menu(self, pos):
        # Правый клик по вкладке — управление вкладкой. Работает на
        # обеих панелях: закреплённой «Все» (меню без действий) и
        # прокручиваемой с обычными вкладками (индекс со сдвигом 1).
        bar = self.sender()
        if bar is self.pinnedTabs:
            name = self.ALL_TAB
        else:
            index = self.presetTabs.tabAt(pos)
            names = self._tab_names()
            if not (0 <= index < len(names) - 1):
                return
            name = names[index + 1]

        self.currentTab = name
        self._sync_tabs()
        self._update_preset_frame()

        self._show_tab_menu(bar.mapToGlobal(pos))

    # --------------------------------------------------

    def preset_context_menu(self, pos):
        # 🔴 Правый клик по пресету: все действия с ним.
        # 🔴 Правый клик по ПУСТОМУ месту: только «Добавить
        # разделитель» (встанет в конец списка).
        item = self.presetList.itemAt(pos)

        if item is None or item.data(Qt.UserRole) is None:
            menu = QMenu(self)
            act_add_end = menu.addAction(tr("Добавить разделитель"))
            menu_pos = clamp_point_within_screen(
                self.presetList.viewport().mapToGlobal(pos),
                menu.sizeHint(),
            )
            if menu.exec(menu_pos) is act_add_end:
                self.add_separator(None)
            return

        preset = item.data(Qt.UserRole)

        is_sep = bool(preset.is_separator)

        # 🔴 Мультивыделение: правый клик по ВЫДЕЛЕННОМУ пресету
        # сохраняет выделение (действия пойдут ко всем); по
        # невыделянному — выделяет только его, как в проводнике.
        selected = {
            it.data(Qt.UserRole).name
            for it in self.presetList.selectedItems()
            if it is not None and it.data(Qt.UserRole) is not None
        }
        if preset.name not in selected:
            self.presetList.setCurrentItem(item)
        self.currentPreset = preset

        menu = QMenu(self)

        if is_sep:
            # 🔴 Меню разделителя: только то, что для него имеет смысл.
            act_duplicate = menu.addAction(tr("Дублировать"))
            menu.addSeparator()
            act_rename = menu.addAction(tr("Переименовать"))
            act_delete = menu.addAction(tr("Удалить"))
            menu.addSeparator()
        else:
            act_launch = menu.addAction(tr("Загрузить"))
            act_configure = menu.addAction(tr("Настроить"))
            act_duplicate = menu.addAction(tr("Дублировать"))
            act_close = menu.addAction(tr("Закрыть окна пресета"))
            act_refresh = menu.addAction(tr("Обновить из текущих окон"))
            menu.addSeparator()
            act_rename = menu.addAction(tr("Переименовать"))
            act_delete = menu.addAction(tr("Удалить"))
            menu.addSeparator()
            act_tags = menu.addAction(tr("Тег (вкладка)..."))

        # 🔴 Разделитель добавляется снизу текущего элемента.
        act_add_sep = menu.addAction(tr("Добавить разделитель"))

        # 🔴 Мультивыделение: в подписи удаления — число выделенных.
        n_selected = len(self._selected_presets(preset))
        act_delete.setText(
            tr("Удалить ({})").format(n_selected)
            if n_selected > 1
            else tr("Удалить")
        )

        # 🔴 Собственный цвет: подложка под названием, видна в любой
        # вкладке — У ПРЕСЕТОВ И У РАЗДЕЛИТЕЛЕЙ (хранится на диске).
        color_menu = menu.addMenu(tr("Цвет"))
        preset_color_default = color_menu.addAction(tr("По умолчанию"))
        color_menu.addSeparator()
        preset_color_actions = {}
        for title, hexcolor in self.TAB_PALETTE:
            title = tr(title)
            act = color_menu.addAction(self._color_icon(hexcolor), title)
            act.setData(hexcolor)
            preset_color_actions[act] = hexcolor
        color_menu.addSeparator()
        preset_color_other = color_menu.addAction(tr("Другой цвет..."))

        # 🔴 Меню — целиком в пределах монитора.
        menu_pos = clamp_point_within_screen(
            self.presetList.viewport().mapToGlobal(pos), menu.sizeHint()
        )
        chosen = menu.exec(menu_pos)

        if chosen is None:
            return

        if chosen is act_add_sep:
            self.add_separator(preset)
        elif chosen is act_duplicate:
            duplicate = PresetStorage.duplicate(preset.name)
            if duplicate is not None:
                self.refresh_presets()
                item_dup = self._item_by_name(duplicate.name)
                if item_dup is not None:
                    self.presetList.setCurrentItem(item_dup)
                self.statusBar.setText(tr("Создана копия «{}»").format(duplicate.name))
        elif chosen is act_rename:
            self.rename_preset(item)
        elif chosen is act_delete:
            self.delete_current_preset()
        elif chosen is preset_color_default:
            self._set_preset_color(preset, None)
        elif chosen is preset_color_other:
            initial = QColor(preset.color or "#43a047")
            color = QColorDialog.getColor(initial, self, tr("Цвет пресета"))
            if color.isValid():
                self._set_preset_color(preset, color)
        elif chosen in preset_color_actions:
            self._set_preset_color(preset, QColor(preset_color_actions[chosen]))
        elif not is_sep:
            # 🔴 Действия, которых у разделителя нет и быть не может.
            if chosen is act_launch:
                self.load_current_preset()
            elif chosen is act_configure:
                self.configure_preset(preset)
            elif chosen is act_close:
                self.close_current_preset()
            elif chosen is act_refresh:
                self.refresh_current_preset()
            elif chosen is act_tags:
                self._open_tag_picker(
                    preset, self.presetList.viewport().mapToGlobal(pos)
                )

    # --------------------------------------------------

    def add_separator(self, target):
        # 🔴 «Добавить разделитель»: вставляется СРАЗУ ПОД пресетом
        # target (или в конец списка, если target None — клик по
        # пустому месту). Сразу запрашивается имя (можно отменить —
        # останется «Разделитель»).
        # 🔴 Разделитель ЛОКАЛЕН ДЛЯ ВКЛАДКИ: запоминаем текущую
        # вкладку (в «Все» — глобальный для «Все», в фильтре — только
        # для него), в других вкладках он не показывается.
        sep = PresetStorage.add_separator(
            after_name=target.name if target is not None else None,
        )
        sep_tags = (
            [] if self.currentTab == self.ALL_TAB
            else [self.currentTab]
        )
        sep.tags = sep_tags

        all_presets = PresetStorage.load()
        for p in all_presets:
            if p.name == sep.name:
                p.tags = sep_tags
                break
        PresetStorage.save(all_presets)

        self.load_presets()

        item = self._item_by_name(sep.name)

        from ui.rename_dialog import RenameDialog

        global_pos = self.presetList.mapToGlobal(QPoint(12, 12))
        if item is not None:
            rect = self.presetList.visualItemRect(item)
            if rect.isValid():
                global_pos = self.presetList.mapToGlobal(rect.topLeft())

        dialog = RenameDialog(self, sep.name, global_pos)

        if dialog.exec() == QDialog.DialogCode.Accepted and (
            dialog.new_name.strip()
        ):
            new_name = dialog.new_name.strip()
            PresetStorage.rename(sep.name, new_name)
            sep.name = new_name

        self.load_presets()
        self.statusBar.setText(tr("Добавлен разделитель «{}»").format(sep.name))

    # --------------------------------------------------

    def _open_tag_picker(self, preset, global_pos):
        # 🔴 Окно выбора тегов: галочки переключаются без закрытия
        # (можно выставить несколько), ширина — как у окна программы,
        # длинные названия переносятся, лишние строки скроллятся.
        from ui.tag_picker_popup import TagPickerPopup

        tags = [
            t for t in self._tab_names() if t != self.ALL_TAB
        ]

        def toggle(name, checked):
            current = set(preset.tags or [])
            if checked:
                current.add(name)
            else:
                current.discard(name)
            self._set_preset_tags(preset, sorted(current))

        def clear():
            self._set_preset_tags(preset, [])

        pos = QPoint(global_pos.x(), global_pos.y())
        width = min(self.width(), 420)
        avail = screen_geometry(pos)
        x = max(
            avail.left() + 8,
            min(pos.x(), avail.right() + 1 - width - 8),
        )
        # 🔴 Окно тегов: от ВЕРХНЕГО КРАЯ главного окна, высотой
        # с программу (актуальную).
        y = self.frameGeometry().top()
        height = self.height()
        if y + height > avail.bottom() + 1:
            y = max(avail.top() + 8, avail.bottom() + 1 - height)

        picker = TagPickerPopup(
            self,
            tags=tags,
            checked=set(preset.tags or []),
            global_pos=(x, y),
            width=width,
            height=height,
            on_toggle=toggle,
            on_clear=clear,
            background_color=self.settings.get("window_color", 52),
            tab_colors=self._tab_colors(),
        )
        picker.show()

    # --------------------------------------------------

    def _set_preset_tags(self, preset, tags):
        # 🔴 Сохраняет теги и пересобирает список (фильтр вкладки
        # мог стать другим).
        # 🔴 Мультивыделение: набор тегов присваивается ВСЕМ
        # выделенным пресетам (выделение от правого клика).
        # 🔴 Разделители исключены: их теги — привязка к вкладке,
        # массовая операция сломала бы локальность.
        targets = [
            t for t in self._selected_presets(preset)
            if not getattr(t, "is_separator", False)
        ]
        names = {p.name for p in targets}

        for p in targets:
            p.tags = list(tags)

        all_presets = PresetStorage.load()
        for p in all_presets:
            if p.name in names:
                p.tags = list(tags)
        PresetStorage.save(all_presets)

        self.load_presets()

        if len(targets) > 1:
            self.statusBar.setText(
                tr("Теги применены к {} пресетам").format(len(targets))
            )

    # --------------------------------------------------

    def refresh_presets(self):

        current = None

        if self.currentPreset:
            current = self.currentPreset.name

        self.load_presets()

        if current:
            item = self._item_by_name(current)
            if item is not None:
                # 🔴 Программное выделение — без сигналов (без превью).
                self.presetList.blockSignals(True)
                self.currentPreset = item.data(Qt.UserRole)
                self.presetList.setCurrentItem(item)
                self.presetList.blockSignals(False)

        self._sync_tabs()
        self._update_preset_frame()

    # --------------------------------------------------

    # --------------------------------------------------

    def configure_preset(self, preset):
        # 🔴 «Настроить»: окно со списком программ/папок пресета;
        # галочка = удалить. После подтверждения пресет правится
        # (включая его окна) и сохраняется на диск БЕЗ пересканирования.
        from ui.preset_editor_popup import PresetEditorPopup

        from ui.picker_dialog import icon_for_file

        editor = PresetEditorPopup(
            self,
            preset,
            icon_for_file=icon_for_file,
        )

        if editor.exec() != QDialog.DialogCode.Accepted:
            return

        removed_programs, removed_folders = editor.removed_selection()

        if not removed_programs and not removed_folders:
            return

        removed_progs_lower = {
            p.strip().lower() for p in removed_programs
        }
        removed_folders_set = set(removed_folders)

        new_programs = [
            p for p in (preset.programs or [])
            if p.strip().lower() not in removed_progs_lower
        ]
        new_folders = [
            f for f in (preset.folders or [])
            if f not in removed_folders_set
        ]
        new_windows = [
            w for w in (preset.windows or [])
            if (w.process or "").strip().lower() not in removed_progs_lower
            and w.folder not in removed_folders_set
        ]

        PresetStorage.update_fields(
            preset.name, new_programs, new_folders, new_windows
        )

        preset.programs = new_programs
        preset.folders = new_folders
        preset.windows = new_windows

        self.refresh_presets()

        self.statusBar.setText(
            tr("«{}»: удалено программ {}, папок {}").format(
                preset.name,
                len(removed_programs),
                len(removed_folders),
            )
        )

    # --------------------------------------------------

    def open_preset_picker(self):
        # 🔴 Двойной клик по «Все»: попап быстрого поиска со ВСЕМИ
        # пресетами (окно само подбирает колонки/размер, см. класс).
        from ui.preset_picker_popup import PresetPickerPopup

        presets = [p for p in self.presets if not p.is_separator]

        if not presets:
            self.statusBar.setText(tr("Пресетов пока нет"))
            return

        # Якорь — вкладка «Все» (первая в закреплённой панели).
        rect = self.pinnedTabs.tabRect(0)
        anchor = self.pinnedTabs.mapToGlobal(rect.center())

        popup = PresetPickerPopup(
            presets,
            anchor,
            on_colors=lambda p: [
                c for c in (
                    self._tab_colors().get(t)
                    for t in (p.tags or [])
                ) if c
            ],
            # 🔴 Минимальный размер = актуальный размер программы:
            # курсор гарантированно внутри окна по открытию.
            min_size=(self.width(), self.height()),
            # Прозрачность цветовых подложек — как в главном списке.
            color_opacity=self.settings.get(
                "preset_color_opacity", 100
            ),
        )
        popup.picked.connect(self.reveal_preset)
        popup.show()

        self._preset_picker = popup

    # --------------------------------------------------

    def reveal_preset(self, preset):
        # 🔴 Выбор в попапе быстрого поиска: если пресет скрыт
        # фильтром вкладки — переключаемся на его первую вкладку
        # (или «Все»), затем прокручиваем список и выделяем.
        if preset is None:
            return

        visible_here = (
            self.currentTab == self.ALL_TAB
            or self.currentTab in (preset.tags or [])
        )

        if not visible_here:
            target_tab = (
                preset.tags[0] if preset.tags else self.ALL_TAB
            )
            self.currentTab = target_tab
            self.load_presets()

        item = self._item_by_name(preset.name)

        if item is None:
            return

        self.presetList.setCurrentItem(item)
        self.currentPreset = preset
        self.presetList.scrollToItem(
            item, QAbstractItemView.ScrollHint.PositionAtCenter
        )
        self.statusBar.setText(tr("Найден: «{}»").format(preset.name))

    # --------------------------------------------------

    def _active_preset(self):
        # Реально показанный пресет (то, что в превью), а не currentPreset,
        # который меняется только по клику в списке.
        shown = self.previewManager._shown_preset
        if shown is not None:
            return shown
        return self.currentPreset

    # --------------------------------------------------

    def _own_hwnds(self):
        # 🔴 hwnd окна WindowPresets + связанные (консоль).
        # Эти окна нельзя закрывать никогда.
        hwnds = []
        try:
            wid = int(self.winId())
            hwnds.append(wid)
        except Exception:
            pass
        return hwnds

    # --------------------------------------------------

    def load_current_preset(self):
        # 🔴 btnLoad — восстановить рабочее место из пресета.
        #
        # Обычный клик:  просто загрузить окна пресета поверх
        #                текущих (ничего не закрывает).
        # CTRL + клик:   полное восстановление — закрыть все окна,
        #                которых нет в пресете, потом загрузить его.
        # 🔴 Мультивыделение: загружаются ВСЕ выделенные пресеты
        # последовательно; при Ctrl «лишним» не считается ни одно
        # окно ЛЮБОГО из выделенных (программы/папки объединяются).

        preset = self._active_preset()

        if preset is None:
            self.statusBar.setText(tr("Сначала выберите пресет"))
            return

        targets = [
            t for t in self._selected_presets(preset)
            if not getattr(t, "is_separator", False)
        ]

        if not targets:
            self.statusBar.setText(
                tr("Разделитель не загружается — это просто заголовок")
            )
            return

        # 🔴 Защита от повторного запуска: воркер уже грузит пресет.
        worker = getattr(self, "_load_worker", None)
        if worker is not None and worker.isRunning():
            self.statusBar.setText(tr("Дождитесь окончания загрузки"))
            return

        full_restore = bool(
            QGuiApplication.queryKeyboardModifiers()
            & Qt.ControlModifier
        )

        # 🔴 Игнорируем клавишу просмотра пару секунд: запускаемые
        # программы (геймпад-скрипты с UIA) шлют синтетические
        # нажатия клавиш в момент запуска — превью не должно
        # самораскрываться и залипать.
        self.previewExpander.arm_cooldown(3.0)

        exclude = self._own_hwnds()

        # 🔴 Плашка «Загружаю...» висит поверх всех окон, пока ВСЕ
        # пресеты полностью не применены.
        self.loadOverlay.show_loading()

        # 🔴 НЕБЛОКИРУЮЩАЯ ЗАГРУЗКА: применение пресета (win32-
        # закрытие лишнего, запуск программ, геометрия) — в QThread,
        # UI живёт (окно больше не «не отвечает» на 2–10 с). Прогресс
        # — сигналы воркера -> плашка/статус.
        from PySide6.QtCore import QThread, Signal as _Signal
        from types import SimpleNamespace

        class LoadWorker(QThread):
            progress = _Signal(int, int, str)
            done = _Signal(object)

            def __init__(self, targets, merged, full, exclude):
                super().__init__(None)
                self._targets = targets
                self._merged = merged
                self._full = full
                self._exclude = exclude

            def run(self):
                totals = {"applied": 0, "launched": 0, "folders": 0}
                close_msg = tr("текущие окна не закрыты")

                try:
                    if self._full:
                        closed = WindowCloser.close_others(
                            self._merged, exclude_hwnds=self._exclude
                        )
                        close_msg = tr("закрыто лишних {}").format(closed["closed"])

                    total_count = len(self._targets)

                    for index, t in enumerate(self._targets, start=1):
                        self.progress.emit(index, total_count, t.name)
                        result = WindowApplier.apply(t)
                        for key in totals:
                            totals[key] += result.get(key, 0)

                    self.done.emit(
                        {
                            "totals": totals,
                            "close_msg": close_msg,
                            "targets": [t.name for t in self._targets],
                        }
                    )
                except Exception as exc:
                    self.done.emit({"error": str(exc)})

        if len(targets) > 1:
            merged = SimpleNamespace(
                programs=[pr for t in targets for pr in t.programs],
                folders=[f for t in targets for f in t.folders],
            )
        else:
            merged = targets[0]

        self._load_worker = LoadWorker(
            targets, merged, full_restore, exclude
        )
        self._load_worker.progress.connect(self._on_load_progress)
        self._load_worker.done.connect(self._on_load_done)
        self._load_worker.start()

    # --------------------------------------------------

    def _on_load_progress(self, index, total, name):

        # 🔴 Прогресс на плашке (сигнал из воркера — уже в UI-потоке).
        if total > 1:
            self.loadOverlay.label.setText(
                tr("Загружаю... {}/{}\n{}")
                .format(index, total, name)
            )
        self.statusBar.setText(tr("Загружаю «{}» ({}/{})...").format(name, index, total))

    # --------------------------------------------------

    def _on_load_done(self, result):

        # «Загружено» гаснет плавно, не блокируя UI.
        self.loadOverlay.show_done()
        self.loadOverlay.hide_soon()

        self._load_worker = None

        if "error" in result:
            self.statusBar.setText(tr("Ошибка загрузки: {}").format(result["error"]))
            return

        targets = result.get("targets", [])
        totals = result["totals"]
        close_msg = result["close_msg"]

        if len(targets) > 1:
            names = ", ".join(targets[:3])
            more = (
                tr(" …и ещё {}").format(len(targets) - 3)
                if len(targets) > 3
                else ""
            )
            self.statusBar.setText(
                tr("Загружено пресетов: {} ({}{}); {}; поставлено {}, "
                   "запущено {}, папок {}")
                .format(
                    len(targets),
                    names,
                    more,
                    close_msg,
                    totals["applied"],
                    totals["launched"],
                    totals["folders"],
                )
            )
        elif targets:
            self.statusBar.setText(
                tr("Применён «{}»: {}; поставлено {}, запущено {}, папок {}")
                .format(
                    targets[0],
                    close_msg,
                    totals["applied"],
                    totals["launched"],
                    totals["folders"],
                )
            )

    # --------------------------------------------------

    def refresh_current_preset(self):
        # 🔴 btnRefresh — пересканировать окна и обновить пресет.

        preset = self._active_preset()

        if preset is None:
            self.statusBar.setText(tr("Сначала выберите пресет"))
            return

        # 🔴 Кулдаун клавиши просмотра на время пересканирования.
        self.previewExpander.arm_cooldown(3.0)

        PresetStorage.update(preset, exclude_hwnds=self._own_hwnds())

        self.refresh_presets()

        self.statusBar.setText(tr("Пресет «{}» обновлён").format(preset.name))

    # --------------------------------------------------

    def close_current_preset(self):
        # 🔴 btnClose — закрыть окна/папки, входящие в пресет.
        # Само окно WindowPresets и консоль НЕ закрываются.

        preset = self._active_preset()

        if preset is None:
            self.statusBar.setText(tr("Сначала выберите пресет"))
            return

        # 🔴 Кулдаун клавиши просмотра на время закрытия окон.
        self.previewExpander.arm_cooldown(3.0)

        exclude = self._own_hwnds()

        result = WindowCloser.close(preset, exclude_hwnds=exclude)

        self.statusBar.setText(
            tr("Закрыто {} окон пресета «{}»").format(result["closed"], preset.name)
        )

    # --------------------------------------------------

    def create_preset(self):

        preset = PresetStorage.new(exclude_hwnds=self._own_hwnds())

        # 🔴 Новый пресет получает тег текущей вкладки (если фильтр
        # активен) — чтобы сразу был виден в этой вкладке.
        if self.currentTab != self.ALL_TAB:
            all_presets = PresetStorage.load()
            for p in all_presets:
                if p.name == preset.name:
                    p.tags = [self.currentTab]
                    break
            PresetStorage.save(all_presets)

        self.refresh_presets()

    # --------------------------------------------------

    def delete_current_preset(self):

        # 🔴 Ctrl+клик по корзине — удалить НЕ выбранный, а ВСЕ
        # пресеты (с усиленным подтверждением).
        if QGuiApplication.queryKeyboardModifiers() & Qt.ControlModifier:
            self.delete_all_presets(via_ctrl=True)
            return

        # 🔴 Мультивыделение: удаляются ВСЕ выделенные пресеты.
        targets = self._selected_presets(self.currentPreset)

        if not targets:
            return

        # 🔴 Обязательное подтверждение: удаление необратимо.
        from ui.confirm_dialog import ConfirmDialog

        if len(targets) > 1:
            names = ", ".join(p.name for p in targets[:5])
            more = (
                tr(" …и ещё {}").format(len(targets) - 5)
                if len(targets) > 5
                else ""
            )
            answer = ConfirmDialog(
                self,
                tr("Удалить пресеты"),
                tr("Удалить {} выделенных пресетов?\n\n{}{}")
                .format(len(targets), names, more),
                yes_text=tr("Удалить"),
                no_text=tr("Отмена"),
                big=True,
            ).exec()
        else:
            answer = ConfirmDialog(
                self,
                tr("Удалить пресет"),
                tr("Удалить пресет «{}»?").format(targets[0].name),
                yes_text=tr("Удалить"),
                no_text=tr("Отмена"),
                big=True,
            ).exec()

        if answer != QDialog.DialogCode.Accepted:
            return

        for p in targets:
            PresetStorage.delete(p.name)

        self.currentPreset = None

        self.previewManager.hide()

        self.refresh_presets()

        if len(targets) > 1:
            self.statusBar.setText(tr("Удалено пресетов: {}").format(len(targets)))

    # --------------------------------------------------

    def delete_all_presets(self, via_ctrl=False):
        # 🔴 Удалить ВСЕ пресеты. Вызывается по Ctrl+клику на
        # корзине пресетов (кнопки в настройках больше нет).

        count = len(PresetStorage.load())

        if count == 0:
            self.statusBar.setText(tr("Пресетов нет — удалять нечего"))
            return

        from ui.confirm_dialog import ConfirmDialog

        if via_ctrl:
            text = (
                tr("Зажат Ctrl: будут удалены ВСЕ пресеты ({} шт.), "
                   "а не один выбранный.\nЭто действие необратимо.")
                .format(count)
            )
        else:
            text = (
                tr("Удалить ВСЕ пресеты ({} шт.)?\n"
                   "Это действие необратимо.").format(count)
            )

        answer = ConfirmDialog(
            self,
            tr("Удалить все пресеты"),
            text,
            yes_text=tr("Удалить все"),
            no_text=tr("Отмена"),
            yes_danger=True,
            big=True,
        ).exec()

        if answer != QDialog.DialogCode.Accepted:
            return

        for preset in PresetStorage.load():
            image = PresetStorage.preview_path(preset.name)
            if os.path.exists(image):
                try:
                    os.remove(image)
                except Exception:
                    pass

        PresetStorage.save([])

        self.currentPreset = None

        self.previewManager.hide()

        self.refresh_presets()

        self.statusBar.setText(tr("Удалено пресетов: {}").format(count))

    # --------------------------------------------------

    def rename_preset(self, item):

        # Двойной клик по пресету → попап переименования,
        # появляется на том же месте относительно экрана.

        if not self.settings.get("double_click_edit", True):
            return

        # 🔴 Пресет лежит в данных элемента (заголовки групп —
        # не пресеты и переименованию не подлежат).
        if item is None:
            return

        preset = item.data(Qt.UserRole)

        if preset is None:
            return

        # Глобальные координаты элемента списка.
        rect = self.presetList.visualItemRect(item)
        global_pos = self.presetList.mapToGlobal(rect.topLeft())

        from ui.rename_dialog import RenameDialog

        dialog = RenameDialog(self, preset.name, global_pos)

        if dialog.exec():

            new_name = dialog.new_name

            # 🔴 Имя не изменилось — ничего не делаем.
            if new_name == preset.name:
                return

            ok = PresetStorage.rename(preset.name, new_name)

            if not ok:
                self.statusBar.setText(
                    tr("Имя «{}» уже занято").format(new_name)
                )
                return

            self.refresh_presets()

            # 🔴 Восстанавливаем выделение на переименованном.
            renamed = self._item_by_name(new_name)
            if renamed is not None:
                # 🔴 Программное выделение — без сигналов (без превью).
                self.presetList.blockSignals(True)
                self.currentPreset = renamed.data(Qt.UserRole)
                self.presetList.setCurrentItem(renamed)
                self.presetList.blockSignals(False)

            if hasattr(self, "statusBar"):
                self.statusBar.setText(tr("Переименовано"))

    # --------------------------------------------------

    def preset_changed(self):

        MainWindowController.preset_changed(self)

        # 🔴 Синхронизируем вкладки и рамку названия с выделением.
        self._update_preset_frame()
        self._sync_tabs()

    # --------------------------------------------------

    def _retranslate_ui(self):
        # 🔴 Смена языка на лету: статичные надписи окна
        # (тултипы, «Все», статус), подписи кнопок вкладок и
        # список (заголовки групп) — переведённые значения
        # подхватятся при пересборке.
        from ui.main_window_ui import retranslate_ui

        old_all = self.ALL_TAB
        self.ALL_TAB = tr("Все")

        if self.currentTab == old_all:
            self.currentTab = self.ALL_TAB

        retranslate_ui(self)
        self._apply_button_texts()
        self._update_preset_frame()
        self._sync_tabs()
        self.load_presets()

    # --------------------------------------------------

    def open_settings(self):

        MainWindowController.open_settings(self)

    # --------------------------------------------------

    def _startup_update_check(self):
        # 🔴 Один раз за запуск (владелец: при автозапуске с
        # Windows программа сама связывается с GitHub). Сеть —
        # в QThread; нет связи — тихо ничего не делаем.

        self._update_worker = UpdateCheckWorker()
        self._update_worker.done.connect(self._on_startup_check_done)
        self._update_worker.start()

    # --------------------------------------------------

    def _on_startup_check_done(self, result):

        if isinstance(result, dict) and result.get("newer"):
            self.mark_update_available(result["tag"])

    # --------------------------------------------------

    def mark_update_available(self, tag):
        # Найдена новая версия: запоминаем (настройки откроются
        # с зелёной кнопкой) и показываем зелёную заметку в
        # нижней строке — в режиме ожидания.

        self.update_tag = tag

        if hasattr(self, "statusBar"):
            self.statusBar.set_update_tag(tag)

    # --------------------------------------------------

    def apply_theme(self, settings):

        self.settings = settings

        windowColor = settings.get("window_color", 60)
        listColor = settings.get("list_color", 50)
        iconColor = settings.get("icon_color", 220)

        # 🔴 Прозрачность цветовых подложек пресетов/разделителей:
        # живёт на делегате списка (рисуется при каждой отрисовке).
        delegate = self.presetList.itemDelegate()
        if delegate is not None:
            delegate.colorOpacity = settings.get(
                "preset_color_opacity", 100
            )

        self.setStyleSheet(f"""
QWidget {{
    background: rgb({windowColor},{windowColor},{windowColor});
    color: rgb({iconColor},{iconColor},{iconColor});
    font-family: "Segoe UI";
    font-size: 11pt;
}}

QListWidget {{
    background: rgb({listColor},{listColor},{listColor});
    border: 1px solid rgb(110,110,110);
    border-radius: 8px;
    padding: 4px;
}}

QFrame#currentPresetFrame {{
    /* 🔴 Серая подложка как у списка, но БЕЗ рамки — не выглядит
       интерактивным блоком. */
    background: rgb({listColor},{listColor},{listColor});
    border: none;
    border-radius: 8px;
}}

QLabel {{
    background: transparent;
}}

QPushButton {{
    background: transparent;
    border: none;
}}

/* 🔴 Подсветка наведения — единая для ВСЕХ кнопок программы
   (кнопки вкладок, диалоги) — как у нижних кнопок пресетов
   (IconButton). */
QPushButton:hover {{
    background:rgba(255,255,255,25);
    border-radius:6px;
}}

QPushButton:pressed {{
    background:rgba(255,255,255,40);
    border-radius:6px;
}}

/* 🔴 Контекстные меню (пресет, вкладка, трей): те же плашки
   наведения на пунктах. */
QMenu {{
    background: rgb({windowColor},{windowColor},{windowColor});
    border: 1px solid rgb(110,110,110);
    padding: 4px;
}}

QMenu::item {{
    background: transparent;
    padding: 4px 24px 4px 12px;
    margin: 1px 2px;
    border-radius: 6px;
}}

QMenu::item:selected {{
    background:rgba(255,255,255,40);
}}

QMenu::item:pressed {{
    background:rgba(255,255,255,60);
}}

QMenu::separator {{
    height: 1px;
    background: rgb(110,110,110);
    margin: 4px 8px;
}}
""")

        for button in [
            self.btnNew,
            self.btnLoad,
            self.btnRefresh,
            self.btnClose,
            self.btnDelete,
            self.btnSettings,
        ]:
            button.update_icon(settings)

        # 🔴 Кнопки вкладок: значки или текст (настройка button_style).
        self._apply_button_texts()

        # 🔴 Цвета вкладок (настройка tab_colors).
        self.pinnedTabs.set_tab_colors(self._tab_colors())
        self.presetTabs.set_tab_colors(self._tab_colors())

        self.update()