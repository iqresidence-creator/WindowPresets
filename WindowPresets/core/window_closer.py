import logging
import time

try:
    import win32gui
    import win32con
except Exception:
    win32gui = None
    win32con = None

from core.folder_scanner import FolderScanner
from core.ignore_list import IgnoreList
from core.window_filters import WindowFilters
from core.window_scanner import WindowScanner


logger = logging.getLogger(__name__)

# Пауза между WM_CLOSE для вкладок одного окна проводника (сек).
TAB_CLOSE_DELAY = 0.35


class WindowCloser:
    """Закрывает окна, входящие в пресет (или не входящие в него).

    Стратегия:
      • close()      — закрыть окна, входящие в пресет;
      • close_others — закрыть окна, НЕ входящие в пресет
                       (используется при загрузке нового пресета);
      • никогда не закрывает само окно программы WindowPresets
        и связанную с ним консоль (через exclude_hwnds);
      • мягкое закрытие через WM_CLOSE — программы сохраняют данные.
    """

    # ----------------------------------------------------------

    @staticmethod
    def _is_available():
        return all((
            win32gui is not None,
            win32con is not None,
            WindowFilters.is_available(),
        ))

    # ----------------------------------------------------------

    @staticmethod
    def _is_console(hwnd, proc):
        # 🔴 Консоль, в которой запущена программа.
        # python.exe / py.exe вешает консольное окно с заголовком-командой.
        if proc in ("python.exe", "py.exe", "pythonw.exe", "cmd.exe"):
            return True
        try:
            cls = WindowFilters.class_name(hwnd)
            if cls in ("ConsoleWindowClass", "TTY"):
                return True
        except Exception:
            pass
        return False

    # ----------------------------------------------------------

    @staticmethod
    def _collect_live():
        # [(process_lower, title, hwnd), ...] из общего снимка окон.
        return [
            (entry["process"], entry["title"], entry["hwnd"])
            for entry in WindowScanner.collect_live()
        ]

    # ----------------------------------------------------------

    @staticmethod
    def _close_hwnd(hwnd):
        # 🔴 ЖЕЛЕЗНОЕ ПРАВИЛО (финальный шлюз): окно самой программы
        # WindowPresets, её консоль и окна терминалов не закрываются
        # НИКОГДА, кем бы ни была вызвана закрытие.
        try:
            if WindowFilters.is_console_class(hwnd):
                logger.info("отказ закрытия консоли: %s", hwnd)
                return False
            proc = WindowFilters.process_name(hwnd)
            if WindowFilters.is_self(proc):
                logger.info("отказ закрытия самой программы: %s", hwnd)
                return False
            if WindowFilters.is_terminal_host(proc):
                logger.info("отказ закрытия терминала: %s", hwnd)
                return False
        except Exception:
            # Не удалось определить процесс — не рискуем.
            return False

        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE)
            return True
        except Exception as exc:
            logger.warning("close %s failed: %s", hwnd, exc)
            return False

    # ----------------------------------------------------------

    @staticmethod
    def _close_explorer_hwnd(hwnd):
        # 🔴 Win11: WM_CLOSE закрывает только АКТИВНУЮ вкладку окна
        # проводника. Сколько вкладок — столько и закрытий.
        tabs = FolderScanner.scan_hwnd_map().get(hwnd, [])
        attempts = max(1, len(tabs))

        for _ in range(attempts):
            if not win32gui.IsWindow(hwnd):
                break
            if not WindowCloser._close_hwnd(hwnd):
                break
            if attempts > 1:
                time.sleep(TAB_CLOSE_DELAY)

    # ----------------------------------------------------------

    @staticmethod
    def _close_window(proc, hwnd):
        if proc == "explorer.exe":
            WindowCloser._close_explorer_hwnd(hwnd)
            return True
        return WindowCloser._close_hwnd(hwnd)

    # ----------------------------------------------------------

    @staticmethod
    def _is_protected(proc, title, hwnd, exclude_hwnds):
        # Окно, которое нельзя закрывать ни при каких условиях.
        if exclude_hwnds and hwnd in exclude_hwnds:
            return True
        # 🔴 Сама программа WindowPresets и терминалы — железно защищены.
        if WindowFilters.is_self(proc):
            return True
        if WindowFilters.is_terminal_host(proc):
            return True
        if WindowCloser._is_console(hwnd, proc):
            return True
        return False

    # ----------------------------------------------------------

    @staticmethod
    def _folder_variants(folders):
        # Нормализованные варианты путей для сравнения с заголовками.
        variants = set()
        for f in folders:
            clean = (f or "").strip().rstrip("\\/").lower()
            if clean:
                variants.add(clean)
                variants.add((f or "").replace("\\", "/").rstrip("/").lower())
        return variants

    # ----------------------------------------------------------

    @staticmethod
    def _folder_ignored(hwnd, tabs_map):
        # 🔴 Окно проводника, среди вкладок которого есть папка
        # из исключений, никогда не закрывается.
        tabs = tabs_map.get(hwnd, [])
        if not tabs:
            return False
        return any(IgnoreList.matches(folders=[t]) for t in tabs)

    # ----------------------------------------------------------

    @staticmethod
    def close(preset, exclude_hwnds=None):
        """Закрывает окна пресета. exclude_hwnds — список hwnd, которые
        нельзя трогать (например, само окно WindowPresets + консоль)."""
        result = {
            "closed": 0,
            "programs_closed": 0,
            "folders_closed": 0,
            "protected": 0,
        }

        if not WindowCloser._is_available():
            logger.error("WindowCloser: win32 недоступен")
            return result

        target_procs = {p.lower() for p in preset.programs}
        target_folders = WindowCloser._folder_variants(preset.folders)

        # Карта вкладок нужна только когда есть исключения по папкам.
        tabs_map = FolderScanner.scan_hwnd_map() if IgnoreList.entries() else {}

        for proc, title, hwnd in WindowCloser._collect_live():

            if WindowCloser._is_protected(proc, title, hwnd, exclude_hwnds):
                result["protected"] += 1
                continue

            if proc == "explorer.exe" and WindowCloser._folder_ignored(hwnd, tabs_map):
                result["protected"] += 1
                continue

            should_close = False

            if proc in target_procs:
                should_close = True

            if not should_close and proc == "explorer.exe":
                title_low = (title or "").lower()
                for folder in target_folders:
                    if folder and folder in title_low:
                        should_close = True
                        break

            if not should_close:
                continue

            if WindowCloser._close_window(proc, hwnd):
                result["closed"] += 1
                if proc == "explorer.exe":
                    result["folders_closed"] += 1
                else:
                    result["programs_closed"] += 1

        logger.info("close result: %s", result)
        return result

    # ----------------------------------------------------------

    @staticmethod
    def close_others(preset, exclude_hwnds=None):
        """Закрывает окна, НЕ входящие в пресет. Используется при загрузке
        пресета для полного восстановления рабочего места: сначала закрываются
        лишние окна, потом applier открывает окна пресета."""
        result = {
            "closed": 0,
            "protected": 0,
        }

        if not WindowCloser._is_available():
            logger.error("WindowCloser: win32 недоступен")
            return result

        # Что ОСТАВЛЯЕМ: процессы и папки пресета.
        keep_procs = {p.lower() for p in preset.programs}
        keep_folders = WindowCloser._folder_variants(preset.folders)

        # Карта вкладок нужна только когда есть исключения по папкам.
        tabs_map = FolderScanner.scan_hwnd_map() if IgnoreList.entries() else {}

        for proc, title, hwnd in WindowCloser._collect_live():

            if WindowCloser._is_protected(proc, title, hwnd, exclude_hwnds):
                result["protected"] += 1
                continue

            # 🔴 Исключение по папке — окно не закрываем никогда.
            if proc == "explorer.exe" and WindowCloser._folder_ignored(hwnd, tabs_map):
                result["protected"] += 1
                continue

            keep = False

            if proc in keep_procs:
                keep = True

            if not keep and proc == "explorer.exe":
                title_low = (title or "").lower()
                for folder in keep_folders:
                    if folder and folder in title_low:
                        keep = True
                        break

            if keep:
                continue

            if WindowCloser._close_window(proc, hwnd):
                result["closed"] += 1

        logger.info("close_others result: %s", result)
        return result
