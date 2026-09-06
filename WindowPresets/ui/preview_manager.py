from PySide6.QtCore import QPoint

from core.preset_storage import PresetStorage

from core.i18n import tr
from ui.preview_window import PreviewWindow


class PreviewManager:

    def __init__(self, window):

        self.window = window
        self.preview = PreviewWindow(window)

        # 🔴 Кэш показанного пресета: защищает от перезагрузки
        # превью при каждом движении мыши (главная причина мелькания).
        self._shown_preset = None

        # 🔴 Последний порядок текст/скриншот — для показа без флага
        # (например, возврат из полного экрана).
        self._last_text_on_top = False

    # ----------------------------------------------------

    def _build_info(self, preset):

        # 🔴 exe-пути процессов — чтобы в плашке у каждой программы
        # была своя иконка (берётся из exe первого окна процесса).
        exe_by_process = {}

        for w in preset.windows:
            proc = (w.process or "").strip().lower()
            if proc and proc not in exe_by_process and w.exe_path:
                exe_by_process[proc] = w.exe_path

        programs = [
            (name, exe_by_process.get(name.strip().lower(), ""))
            for name in preset.programs
        ]

        left = {
            "programs": programs,
            "folders": list(preset.folders),
        }

        right = []
        right.append(preset.name)

        if preset.updated:
            right.append(tr("\nИзменён:\n{}").format(preset.updated))

        right.append("")
        right.append(tr("Программ: {}").format(len(preset.programs)))
        right.append(tr("Папок: {}").format(len(preset.folders)))
        right.append("")
        right.append(tr("Мониторов: {}").format(preset.monitor_count))

        return left, "\n".join(right)

    # ----------------------------------------------------

    # ----------------------------------------------------

    def refresh_info(self, preset):
        # 🔴 Обновляет ТОЛЬКО текст плашки из пресета (без перезагрузки
        # пиксмапа и пересчёта позиции). Используется при раскрытии
        # большого окна, чтобы плашка была актуальна под текущий пресет.
        if preset is None:
            return
        left, right = self._build_info(preset)
        self.preview.set_info(left, right)

    # ----------------------------------------------------

    def show(self, preset, text_on_top=None):

        # 🔴 Порядок текст/скриншот: явный флаг от вызывающего или
        # последний сохранённый (показ без флага — возврат
        # из полного экрана).
        flag = text_on_top if text_on_top is not None else self._last_text_on_top

        if preset is None:
            self.hide()
            return

        # 🔴 Превью РАСКРЫТО на весь экран (пробел): НЕ трогаем ни
        # геометрию, ни контент. Раньше show() ужимал fullscreen-окно
        # до малого (resize ниже) при шевелении мыши над списком —
        # окно уходило из-под курсора, список его прятал, автоповтор
        # пробела снова раскрывал = МЕРЦАНИЕ полный↔малый.
        # Актуальный контент вернёт restore() при сворачивании.
        if self.preview.fullscreen:
            return

        # 🔴 Тот же пресет — ничего не делаем. Полную перезагрузку
        # (пиксмап, пересчёт позиции, show) выполняем только при смене.
        # Это убирает мелькание при наведении мыши на список.
        # Ранний возврат работает ТОЛЬКО если и порядок текст/скриншот
        # совпал (сравнение ДО записи нового флага в кэш — иначе при
        # том же пресете порядок не переключится).
        if self._shown_preset is preset and flag == self._last_text_on_top:
            if not self.preview.isVisible():
                self.preview.show()
                self.preview.raise_()
            return

        self._last_text_on_top = flag
        self._shown_preset = preset

        main = self.window.frameGeometry()
        screen = self.window.screen().availableGeometry()

        gap = 6
        margin = 12

        # ════════════════════════════════════════════════════
        # 🔴 Размер малого превью: ширина = ширине главного окна;
        # скриншот занимает фиксированную часть (высота по пропорции:
        # 2 монитора — ниже, 1 — выше), текст состава — в остатке окна;
        # если текст не влезает — скролл.
        # ════════════════════════════════════════════════════
        base_w = self.window.width()
        # 🔴 Высота превью = визуальному окну списка пресетов
        # (виджет presetList), а не всему окну программы.
        base_h = self.window.presetList.height()

        # Порядок текст/скриншот применяем ДО resize/показа.
        self.preview.set_text_on_top(flag)

        self.preview.resize(base_w, base_h)

        self.preview.set_preview(
            PresetStorage.preview_path(preset.name)
        )

        left, right = self._build_info(preset)
        self.preview.set_info(left, right)

        settings = self.window.settings
        self.preview.set_text_size(
            settings.get("preview_text_size", 18)
        )
        self.preview.set_dim(
            settings.get("preview_dim", 30)
        )
        self.preview.set_panel_color(
            settings.get("window_color", 60),
            settings.get("preview_panel_alpha", 40),
        )

        self.preview.refresh_layout()

        preview_w = self.preview.width()
        preview_h = self.preview.height()

        # ════════════════════════════════════════════════════
        # ПРИОРИТЕТ №1: малое превью скриншота.
        # Железно появляется в свободном от программы месте.
        # ════════════════════════════════════════════════════
        space_right = screen.right() - main.right() - gap
        space_left = main.left() - screen.left() - gap

        if space_right >= preview_w:
            preview_x = main.right() + gap
        elif space_left >= preview_w:
            preview_x = main.left() - gap - preview_w
        elif space_right >= space_left:
            # Справа места больше — прижимаем к правому краю экрана.
            preview_x = screen.right() - margin - preview_w
        else:
            preview_x = screen.left() + margin

        # 🔴 Превью по вертикали — НА УРОВНЕ СПИСКА ПРЕСЕТОВ:
        # верх превью = верх списка, не ездит за строкой пресета;
        # у краёв монитора — кламп.
        list_top = self.window.presetList.mapToGlobal(QPoint(0, 0)).y()
        preview_y = max(
            screen.top() + margin,
            min(list_top, screen.bottom() + 1 - margin - preview_h),
        )

        self.preview.move(preview_x, preview_y)
        self.preview.show()
        self.preview.raise_()

        # 🔴 Отдельная плашка в малом режиме НЕ используется (текст
        # встроен под скриншот) — гасим на случай остатка после
        # полноэкранного режима.
        self.preview.hide_info_panel()

    # ----------------------------------------------------

    def hide(self):

        self.preview.hide()
        self.preview.hide_info_panel()

        # 🔴 Сбрасываем кэш, чтобы следущий show() точно перерисовал.
        self._shown_preset = None
