import time

from PySide6.QtCore import QObject, QEvent, Qt, QPoint, QSize, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication


# 🔴 Клавиша раскрытия превью — ТОЛЬКО ПРОБЕЛ (раньше был SHIFT).
# Пробел — НЕ модификатор, поэтому «всё ещё зажата?» проверяется
# напрямую через GetAsyncKeyState (VK_SPACE), а не через
# queryKeyboardModifiers (тот видит только Shift/Ctrl/Alt).
PREVIEW_KEY_CODE = 32                        # Qt.Key_Space
PREVIEW_KEY_VK = 0x20                        # VK_SPACE для GetAsyncKeyState

# Частота опроса состояния (мс).
POLL_INTERVAL = 100


class PreviewExpander(QObject):

    def __init__(self, window):

        super().__init__(window)

        self.window = window
        self.preview = window.previewManager.preview

        self.expanded = False
        self.smallGeometry = None

        # 🔴 Каким способом раскрыли: клавишей или наведением мыши.
        # От этого зависит, как сворачивать.
        self.expand_by_key = False

        # 🔴 Кулдаун клавиши просмотра после действий (Загрузить/
        # Обновить/Закрыть): запускаемые программы (геймпад-скрипты
        # с UIA и т.п.) шлют СИНТЕТИЧЕСКИЕ нажатия клавиш ровно в
        # момент, когда наше окно в фокусе, — превью раскрывалось
        # само и залипало. В кулдаун клавиша игнорируется.
        self._key_cooldown_until = 0.0

        # 🔴 Единый опрос состояния (вместо ненадёжных событий):
        #   • раскрытие по клавише: сворачиваем, когда клавиша
        #     реально отпущена (KeyRelease на Windows теряется);
        #   • раскрытие по наведению: курсор ушёл из зоны малого
        #     превью — сворачиваем. Полноэкранное превью прозрачно
        #     для мыши и НЕ ПРИНИМАЕТ события мыши — только опрос;
        #   • раскрытие по наведению: курсор НАД малым превью —
        #     раскрываем (не ждём MouseMove).
        # Также рассинхрон: превью скрыли извне — сбрасываем состояние.
        self.pollTimer = QTimer(self)
        self.pollTimer.setInterval(POLL_INTERVAL)
        self.pollTimer.timeout.connect(self._poll)
        self.pollTimer.start()

        QGuiApplication.instance().installEventFilter(self)

    # -----------------------------

    def arm_cooldown(self, seconds):
        # Игнорировать клавишу просмотра N секунд (после Загрузить/
        # Обновить/Закрыть — на время запуска программ).
        self._key_cooldown_until = time.monotonic() + seconds

    # -----------------------------

    def _in_cooldown(self):
        return time.monotonic() < self._key_cooldown_until

    # -----------------------------

    def _popup_or_modal_open(self):
        # 🔴 Открыто ли какое-то «чужое» окно программы: контекстное
        # меню (пресета/вкладки/трея), список вкладок, модальный
        # диалог (переименование, настройки). Пока оно открыто, превью
        # НЕ раскрывается — иначе меню над превью перехватывало курсор
        # и раскрывало превью на весь экран под собой.
        app = QApplication.instance()
        if app is None:
            return False
        return (
            app.activePopupWidget() is not None
            or app.activeModalWidget() is not None
        )

    # -----------------------------

    def _modifier_still_pressed(self):
        # Реальное состояние клавиши раскрытия прямо сейчас.
        # Пробел — не модификатор: queryKeyboardModifiers его не
        # видит, опрашиваем WinAPI напрямую (как в tab_list_popup).
        try:
            import win32api
            import win32con

            return bool(
                win32api.GetAsyncKeyState(PREVIEW_KEY_VK) & 0x8000
            )
        except Exception:
            return False

    # -----------------------------

    def _poll(self):

        try:
            self._poll_safe()
        except RuntimeError:
            # C++ объекты Qt уже удалены (закрытие приложения).
            self.pollTimer.stop()

    # -----------------------------

    def _poll_safe(self):

        cursor = QCursor.pos()

        if self.expanded:

            # Превью скрыли извне (таймер списка) — рассинхрон.
            # 🔴 Если раскрытие по клавише и она ещё зажата —
            # немедленно возвращаем полноэкранный режим. Иначе
            # автоповтор пробела ловил цикл «скрыто → раскрыто»
            # (мерцание полный↔малый, грабли п.36 HANDOFF).
            if not self.preview.isVisible():
                if self.expand_by_key and self._modifier_still_pressed():
                    self.expand(by_key=True)
                else:
                    self.expanded = False
                    self.smallGeometry = None
                return

            # Раскрытие по клавише: сворачиваем, когда отпущена.
            if self.expand_by_key:
                if not self._modifier_still_pressed():
                    self.restore()
                return

            # Раскрытие по наведению: открыт контекст/модал —
            # сворачиваем, чтобы не мешал работать с меню.
            if self._popup_or_modal_open():
                self.restore()
                return

            # Раскрытие по наведению: держим, пока курсор в зоне
            # малого превью (большое окно занимает весь экран,
            # его геометрия не годится — курсор всегда внутри).
            if not (self.smallGeometry and self.smallGeometry.contains(cursor)):
                self.restore()

            return

        # 🔴 Не раскрыто: курсор над СКРИНШОТОМ малого превью (верхняя
        # часть окна) — раскрываем. Наведение на текст под скриншотом
        # НЕ раскрывает (текст читают и скроллят).
        # Пока открыт контекст/модал — НЕ раскрываем (курсор над меню
        # поверх превью не должен запускать раскрытие на весь экран).
        if (
            not self._in_cooldown()
            and not self._popup_or_modal_open()
        ):
            if (
                self.preview.isVisible()
                and self.preview.shot_global_rect().contains(cursor)
            ):
                self.expand(by_key=False)

    # -----------------------------

    def get_key(self):

        # 🔴 Клавиша просмотра — всегда ПРОБЕЛ (настройка удалена).
        return PREVIEW_KEY_CODE

    # -----------------------------

    def _panel_position_for_fullscreen(self, screen, panel_size):

        shot = self.preview.fullscreen_pixmap_rect()
        gap = 6

        left_space = shot.left() - screen.left()
        right_space = screen.right() - shot.right()

        if right_space >= panel_size.width() + gap + 12:
            start_x = shot.right() + gap
            end_x = screen.right() - panel_size.width() - 12
            x = start_x if end_x <= start_x else start_x + (end_x - start_x) // 2
        elif left_space >= panel_size.width() + gap + 12:
            start_x = screen.left() + 12
            end_x = shot.left() - gap - panel_size.width()
            x = start_x if end_x <= start_x else start_x + (end_x - start_x) // 2
        else:
            x = max(
                screen.left() + 12,
                min(
                    shot.center().x() - (panel_size.width() // 2),
                    screen.right() - panel_size.width() - 12,
                ),
            )

        center_y = shot.center().y() - (panel_size.height() // 2)
        y = max(
            screen.top() + 12,
            min(center_y, screen.bottom() - panel_size.height() - 12),
        )

        return QPoint(x, y)

    # -----------------------------

    def eventFilter(self, obj, event):

        # 🔴 При закрытии приложения C++ объекты Qt уже могут быть
        # удалены — не падаем, просто пропускаем событие.
        try:
            return self._handle_event(obj, event)
        except RuntimeError:
            return False

    # -----------------------------

    def _handle_event(self, obj, event):

        from PySide6.QtWidgets import QApplication

        # Если открыт модальный диалог (например, переименование),
        # не вмешиваемся в клавиатуру — пусть текст вводится нормально.
        if QApplication.activeModalWidget() is not None:
            return False

        selected = self.get_key()

        if event.type() == QEvent.KeyPress:

            # 🔴 Кулдаун: сразу после Загрузить/Обновить/Закрыть
            # клавиша просмотра игнорируется (защита от синтетических
            # нажатий запущенных программ).
            if self._in_cooldown():
                return False

            # 🔴 Пока открыт контекст/попап — клавиша раскрытия
            # не работает (пробел при открытом меню не должен
            # разворачивать превью на весь экран).
            if self._popup_or_modal_open():
                return False

            # 🔴 Пробел перехватываем только при живом превью или
            # активном раскрытии: иначе съедим активацию
            # сфокусированной кнопки / скролл списка пробелом.
            # expanded учитываем: окно могли мигом скрыть извне —
            # автоповторы не должны проваливаться в список.
            if event.key() == selected and (
                self.preview.isVisible() or self.expanded
            ):
                self.expand(by_key=True)
                return True

            return False

        if event.type() == QEvent.KeyRelease:

            # 🔴 На Windows автоповтор клавиши приходит ПАРОЙ
            # KeyRelease+KeyPress (оба с isAutoRepeat=True) —
            # проверено пробой: без этого фильтра каждый автоповтор
            # пробела сворачивал превью, следующий — раскрывал
            # (= МЕРЦАНИЕ ~12 Гц через ~1с после зажатия, когда
            # клавиатура начинает повтор). Сворачиваем ТОЛЬКО
            # настоящее отпускание. Надёжная страховка — опрос
            # GetAsyncKeyState в poll.
            if self.expanded and self.expand_by_key and event.key() == selected:
                if not event.isAutoRepeat():
                    self.restore()
                return True

            return False

        return False

    # -----------------------------

    def _active_preset(self):
        # 🔴 Реально показанный в превью пресет — источник истины.
        # window.currentPreset обновляется только по клику в списке,
        # а наведение мыши меняет превью напрямую. Поэтому берём
        # то, что действительно сейчас показано в previewManager.
        shown = self.window.previewManager._shown_preset
        if shown is not None:
            return shown
        return self.window.currentPreset

    # -----------------------------

    def expand(self, by_key=True):

        if self.expanded:
            # 🔴 Уже раскрыто. ПОВТОРНОЕ нажатие клавиши (а пробел
            # АВТОПОВТОРЯЕТСЯ ~30/с, в отличие от SHIFT!) переводит
            # раскрытие в режим «по клавише». Иначе hover-логика poll
            # сворачивала окно (курсор вне smallGeometry), автоповтор
            # тут же раскрывал снова = МЕРЦАНИЕ полный↔малый (п.36).
            if by_key:
                self.expand_by_key = True
            return

        active = self._active_preset()
        if active is None:
            return

        # 🔴 Флаг ставим ЗАРАНЕЕ: любое исключение дальше не должно
        # оставить полноэкранное окно без признака «раскрыто»
        # (иначе оно больше никогда не свернётся).
        self.expanded = True
        self.expand_by_key = by_key

        try:
            # 🔴 Зона удержания раскрытия (наведение) — РОВНО скриншот
            # малого превью, не всё окно с текстом.
            self.smallGeometry = self.preview.shot_global_rect()

            screen = self.window.screen().availableGeometry()

            # 🔴 Принудительно обновляем контент плашки из РЕАЛЬНО
            # показанного пресета (тот, что сейчас в малом превью).
            self.window.previewManager.refresh_info(active)

            # 🔴 Сначала ставим fullscreen-флаг и геометрию, ПОТОМ показ —
            # иначе виджет мелькает белым в старом размере перед перерисовкой.
            self.preview.set_fullscreen(True)
            self.preview.setGeometry(screen)
            self.preview.update()

            # 🔴 Сначала показываем и поднимаем большое окно, ПОТОМ плашку —
            # иначе большое окно закрывало плашку собой.
            self.preview.raise_()
            self.preview.show()

            # 🔴 Плашка — по центру экрана (с разумными отступами от краёв).
            # Считаем размер под доступную ширину (с отступами по бокам),
            # чтобы колонки текста стягивались равномерно.
            panel_max_w = screen.width() - 48
            panel_size = self.preview.infoPanel.preferred_size(
                QSize(panel_max_w, screen.height() - 48)
            )

            panel_x = screen.center().x() - (panel_size.width() // 2)
            panel_y = screen.center().y() - (panel_size.height() // 2)

            # Держим в пределах экрана.
            panel_x = max(
                screen.left() + 24,
                min(panel_x, screen.right() - panel_size.width() - 24),
            )
            panel_y = max(
                screen.top() + 24,
                min(panel_y, screen.bottom() - panel_size.height() - 24),
            )

            # 🔴 show_info_panel поднимет плашку ПОВЕРХ большого окна.
            self.preview.show_info_panel(QPoint(panel_x, panel_y), panel_size)

        except Exception:
            # Не оставляем полу-раскрытое состояние — сворачиваем всё.
            self.restore()
            raise

    # -----------------------------

    def restore(self):

        if not self.expanded:
            return

        # 🔴 Сбрасываем признаки ДОРИСОВКИ состояния, чтобы никакое
        # исключение в показе не оставило окно «раскрытым навсегда».
        self.expanded = False
        self.smallGeometry = None

        try:
            self.preview.set_fullscreen(False)

            # 🔴 Возвращаем маленькое превью того пресета, что был раскрыт.
            # Сбрасываем кэш, чтобы show() гарантированно перерисовал.
            active = self._active_preset()
            if active is not None:
                self.window.previewManager._shown_preset = None
                self.window.previewManager.show(active)
            else:
                # Показывать нечего — полностью прячем, никакого
                # полноэкранного остатка.
                self.window.previewManager.hide()

        except Exception:
            self.window.previewManager.hide()
