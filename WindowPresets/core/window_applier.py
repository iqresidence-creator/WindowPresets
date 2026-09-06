import logging
import os
import re
import subprocess
import time

try:
    import win32gui
    import win32con
    import win32api
except Exception:
    win32gui = None
    win32con = None
    win32api = None

from core.folder_scanner import FolderScanner
from core.ignore_list import IgnoreList
from core.settings_manager import SettingsManager
from core.window_filters import WindowFilters
from core.window_scanner import WindowScanner


logger = logging.getLogger(__name__)

# Сколько ждать появления окна после запуска процесса (сек).
# 🔴 12 сек: тяжёлые приложения (AutoCAD, Photoshop) рисуют главное
# окно дольше пяти — раньше это вызывало повторные запуски.
LAUNCH_TIMEOUT = 12.0
LAUNCH_POLL = 0.25

# Сколько ждать ОКНО у уже запущенного процесса (повторные записи
# пресета того же процесса) — повторный запуск запрещён.
LAUNCH_SECONDARY_WAIT = 6.0

# 🔴 Микро-записи пресета (сохранённые старыми версиями служебные
# окна 41x41 и т.п.) не запускаются — см. WindowScanner.
MIN_WINDOW_DIMENSION = 60

# 🔴 Повторное применение геометрии: запущенная программа успевает
# САМА восстановить свою последнюю позицию и перетереть нашу —
# поэтому через паузу ставим геометрию ещё раз.
GEOMETRY_REAPPLY_DELAY = 1.2


class WindowApplier:
    """Применяет сохранённый пресет к текущему рабочему месту.

    Стратегия — гибрид:
      • найденные окна — двигаем на сохранённую геометрию;
      • ненайденные — запускаем процесс и ждём появления окна;
      • папки — открываем в проводнике (вкладки — через Ctrl+T).
    Лишние окна НЕ закрываются (этим занимается WindowCloser).
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
    def _live_map():
        # Карта: process_name(lower) -> [(title, hwnd), ...]
        # из общего снимка окон (включая UWP-приложения за хостом).
        live = {}
        for entry in WindowScanner.collect_live():
            live.setdefault(entry["process"], []).append(
                (entry["title"], entry["hwnd"])
            )
        return live

    # ----------------------------------------------------------

    @staticmethod
    def _title_similarity(a, b):
        # Чем больше — тем ближе. 0 = нет совпадения.
        a = (a or "").strip().lower()
        b = (b or "").strip().lower()
        if not a or not b:
            return 0
        if a == b:
            return 100
        if a.startswith(b) or b.startswith(a):
            return 60
        # Общие слова длиной > 3.
        aw = {w for w in a.split() if len(w) > 3}
        bw = {w for w in b.split() if len(w) > 3}
        common = aw & bw
        return len(common) * 5

    # ----------------------------------------------------------

    @staticmethod
    def _pick_hwnd(candidates, info, used, explorer_tabs=None):
        # 🔴 Выбираем лучшее окно по title среди НЕиспользованных.
        #
        # Для проводника главное — ПАПКА, а не заголовок: заголовки
        # «X — проводник» похожи у всех окон. Окно с совпавшей
        # папкой/вкладкой получает большой бонус; если у записи
        # пресета есть папка, а ни у одного кандидата такой папки
        # нет — считаем, что окна нет (запустим новое по адресу).
        #
        # Если кандидатов несколько и нет ни папки, ни смыслового
        # прока по заголовку (score 0) — не двигаем чужое окно
        # (раньше геометрия уходила случайному окну процесса).
        best = None
        best_score = -1
        best_folder_hit = False

        saved_paths = {p.lower() for p in ([info.folder] + list(info.tabs)) if p}

        for title, hwnd in candidates:
            if hwnd in used:
                continue

            score = WindowApplier._title_similarity(title, info.title)
            folder_hit = False

            if (info.process or "").lower() == "explorer.exe" and saved_paths:
                live_paths = {
                    p.lower()
                    for p in (explorer_tabs or {}).get(hwnd, [])
                }
                if saved_paths & live_paths:
                    folder_hit = True
                    score += 1000

            if score > best_score:
                best_score = score
                best = hwnd
                best_folder_hit = folder_hit

        if best is None:
            return None

        # У окна проводника в пресете есть адрес, но ни одно живое
        # окно этот адрес не показывает — это ДРУГОЕ окно, не наше.
        if (
            (info.process or "").lower() == "explorer.exe"
            and saved_paths
            and not best_folder_hit
        ):
            return None

        if len(candidates) > 1 and best_score <= 0:
            logger.info(
                "матчинг отклонён: %r не похож ни на одно окно процесса",
                info.title,
            )
            return None

        return best

    # ----------------------------------------------------------

    @staticmethod
    def _monitor_rect(index):
        # Прямоугольник монитора по индексу (как сохранял сканер).
        try:
            monitors = win32api.EnumDisplayMonitors()
            if 0 <= index < len(monitors):
                info = win32api.GetMonitorInfo(monitors[index][0])
                return info["Monitor"]  # (left, top, right, bottom)
        except Exception:
            pass
        return None

    # ----------------------------------------------------------

    @staticmethod
    def _clamp_into(info, rect):
        # Если центр окна не в сохранённом мониторе — переносим окно
        # внутрь него (координаты могли стать невалидными после
        # смены раскладки мониторов).
        left, top, right, bottom = rect
        cx = info.x + info.width // 2
        cy = info.y + info.height // 2
        if left <= cx <= right and top <= cy <= bottom:
            return info.x, info.y
        x = max(left, min(info.x, right - info.width))
        y = max(top, min(info.y, bottom - info.height))
        return x, y

    # ----------------------------------------------------------

    @staticmethod
    def _set_geometry(hwnd, info):
        # 🔴 Порядок важен: сначала восстановить окно и ПОМЕСТИТЬ
        # его на сохранённый монитор, и только потом разворачивать.
        # Иначе maximized раскрывается на текущем мониторе и окна
        # «менялись местами» между левым/правым.
        try:
            # 🔴 Restore нужен ТОЛЬКО для развёрнутых/свёрнутых окон:
            # обычное окно не трогаем лишним ShowWindow — Store-приятия
            # (Блокнот и др.) на событие восстановления возвращают
            # свою запомненную позицию, перетирая нашу.
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            if (style & win32con.WS_MAXIMIZE) or win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            x, y = info.x, info.y
            rect = WindowApplier._monitor_rect(info.monitor)
            if rect:
                x, y = WindowApplier._clamp_into(info, rect)

            win32gui.SetWindowPos(
                hwnd, 0,
                x, y,
                info.width, info.height,
                win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
            )

            if info.maximized:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            elif info.minimized:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

            return True
        except Exception as exc:
            logger.warning("set_geometry %s failed: %s", hwnd, exc)
            return False

    # ----------------------------------------------------------

    # 🔴 Каталог: процесс -> специальный способ запуска для системных
    # приложений, которые нельзя запустить простым startfile(exe).
    SYSTEM_LAUNCHERS = {
        # Панель управления Windows
        "control.exe": ["control.exe"],
        # Современные настройки Windows 10/11 (ms-settings)
        "systemsettings.exe": ["cmd", "/c", "start", "", "ms-settings:"],
        # Громкость / микшер
        "sndvol.exe": ["sndvol.exe"],
    }

    @staticmethod
    def _virtual_folder_arg(folder):
        # «Этот компьютер» и другие виртуальные папки — shell-URI.
        if not folder:
            return ""
        low = folder.lower()
        if low.startswith(("этот компьютер", "this pc")):
            return "shell:MyComputerFolder"
        return folder

    # ----------------------------------------------------------

    # 🔴 Исполнительные файлы Sandboxie-Plus: через них запускают
    # программы «в песочнице» (как ярлыки вида «[DefaultBox] ...»).
    SANDBOXIE_MANAGERS = (
        r"C:\Program Files\Sandboxie-Plus\SandMan.exe",
        r"C:\Program Files\Sandboxie-Plus\Start.exe",
        r"C:\Program Files\Sandboxie\Start.exe",
    )

    @staticmethod
    def _sandbox_command(exe_path):
        # 🔴 Автопесочница: если сохранённый exe лежит в контейнере
        # Sandboxie (C:\Sandbox\<пользователь>\<бокс>\drive\C\...),
        # запускаем его ЧЕРЕЗ ПЕСОЧНИЦУ (SandMan /box:<бокс> <путь>),
        # а не напрямую (прямой запуск вышел бы вне песочницы).
        match = re.match(
            r"(?i)^[a-z]:\\Sandbox\\[^\\]+\\([^\\]+)\\drive\\.",
            exe_path or "",
        )
        if not match:
            return None

        for manager in WindowApplier.SANDBOXIE_MANAGERS:
            if os.path.exists(manager):
                return [manager, f"/box:{match.group(1)}", exe_path]

        return None

    # ----------------------------------------------------------

    @staticmethod
    def _manual_target(info):
        # 🔴 Ручной путь запуска из настроек («Пути запуска программ»).
        # Ключ может быть именем процесса, именем exe-файла или
        # заголовком окна — как удобнее пользователю.
        try:
            overrides = SettingsManager.load().get("launch_paths", {}) or {}
        except Exception:
            return ""

        if not isinstance(overrides, dict) or not overrides:
            return ""

        process = (info.process or "").strip().lower()
        exe_base = os.path.basename(info.exe_path or "").strip().lower()
        title = (info.title or "").strip().lower()

        # Точное совпадение: процесс / имя файла / заголовок.
        for key in (process, exe_base, title):
            if key and str(overrides.get(key, "") or "").strip():
                return str(overrides[key]).strip()

        # Неточное: ключ является частью заголовка или наоборот
        # (пользователь мог вписать заголовок не полностью).
        for raw_key, raw_value in overrides.items():
            key = str(raw_key).strip().lower()
            value = str(raw_value).strip()
            if not key or not value:
                continue
            if title and (key in title or title in key):
                return value

        return ""

    # ----------------------------------------------------------

    @staticmethod
    def _geometry_matches(hwnd, info):
        # Текущая геометрия окна совпадает с сохранённой в пресете?
        try:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)

            if info.maximized:
                return bool(style & win32con.WS_MAXIMIZE)

            if info.minimized:
                return bool(win32gui.IsIconic(hwnd))

            if (style & win32con.WS_MAXIMIZE) or win32gui.IsIconic(hwnd):
                return False

            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            return (
                abs(left - info.x) <= 2
                and abs(top - info.y) <= 2
                and abs((right - left) - info.width) <= 2
                and abs((bottom - top) - info.height) <= 2
            )
        except Exception:
            return False

    # ----------------------------------------------------------

    @staticmethod
    def _run_command(command):
        # 🔴 Запуск значения из настроек: это может быть путь к файлу
        # (exe/vbs/lnk/...) ИЛИ целая команда с аргументами
        # (например: SandMan.exe /box:DefaultBox "...").
        # Для exe — с рабочей папкой самого файла (ресурсы Qt/OBS
        # ищутся относительно неё); при требовании прав администратора
        # — fallback через ShellExecute (UAC).
        command = (command or "").strip()
        if not command:
            return False

        try:
            if os.path.isfile(command):
                if (
                    command.lower().endswith(".exe")
                    and "windowsapps" not in command.lower()
                ):
                    try:
                        subprocess.Popen(
                            [command],
                            cwd=os.path.dirname(command) or None,
                            shell=False,
                        )
                        return True
                    except Exception as exc:
                        logger.warning("run exe %s failed: %s", command, exc)
                    # 740 (UAC) и прочее — с рабочей папкой.
                    return WindowApplier._shellexecute(
                        command, os.path.dirname(command)
                    )
                os.startfile(command)
            else:
                subprocess.Popen(command, shell=True)
            return True
        except Exception as exc:
            logger.warning("run command %r failed: %s", command, exc)
            return False

    # ----------------------------------------------------------

    @staticmethod
    def _shellexecute(path, working_dir=None):
        # 🔴 Запуск через ShellExecute: в отличие от os.startfile
        # позволяет задать РАБОЧУЮ ПАПКУ (Qt-приложения и OBS ищут
        # ресурсы относительно неё) и корректно обрабатывает
        # требование прав администратора (показывает UAC-запрос).
        import win32api

        result = win32api.ShellExecute(
            0, "open", path, None, working_dir or None, 1  # SW_SHOWNORMAL
        )
        return result > 32

    # ----------------------------------------------------------

    @staticmethod
    def _launch(process_name, info):
        # 🔴 Запускает процесс. Приоритет путей запуска:
        #   0. РУЧНОЙ ПУТЬ из настроек («Пути запуска программ») —
        #      если для программы указан файл/команда, открываем
        #      ТОЛЬКО через них (скрипты, песочница, аргументы)
        #   0b. Автопесочница: exe из контейнера Sandboxie
        #      запускается через SandMan /box:...
        #   1. AUMID (UWP/Store) — shell:AppsFolder\<aumid>
        #   2. Сохранённый полный путь exe_path (для скриптов — сам скрипт)
        #   3. Системный каталог (control.exe, ms-settings, звук)
        #   4. Каталог shell:AppsFolder (все программы Пуска,
        #      включая Win32 и UWP; ищем по exe и по имени)
        name_lower = process_name.lower()

        # 🔴 ЖЕЛЕЗНОЕ ПРАВИЛО: саму программу WindowPresets и терминалы
        # не запускаем ни при каких условиях.
        if WindowFilters.is_self(name_lower) or WindowFilters.is_terminal_host(name_lower):
            logger.info("запуск системного окна запрещён: %s", name_lower)
            return False

        # 0. 🔴 Ручной путь запуска из настроек.
        manual = WindowApplier._manual_target(info)
        if manual and WindowApplier._run_command(manual):
            return True

        # 0b. 🔴 Автопесочница Sandboxie.
        sandbox_cmd = WindowApplier._sandbox_command(info.exe_path)
        if sandbox_cmd:
            try:
                subprocess.Popen(sandbox_cmd, shell=False)
                return True
            except Exception as exc:
                logger.warning("sandbox launch failed: %s", exc)

        # 1. 🔴 AUMID — самый надёжный способ для UWP/Store-приложений.
        if info.aumid:
            try:
                subprocess.Popen(
                    ["explorer.exe", f"shell:AppsFolder\\{info.aumid}"],
                    shell=False,
                )
                return True
            except Exception as exc:
                logger.warning("aumid launch %s failed: %s", info.aumid, exc)

        # 2. 🔴 Полный путь к exe из пресета. Сначала пробуем найти
        # ЯРЛЫК Пуска, указывающий на этот exe, и запустить РОВНО так,
        # как задумано ярлыком (аргументы + рабочая папка) — это
        # покрывает «специальные» лаунчеры. Затем — прямой запуск
        # с РАБОЧЕЙ ПАПКОЙ exe (Qt-приложения и OBS ищут ресурсы
        # относительно текущей папки). При WinError 740 (нужны права
        # администратора) — fallback через ShellExecute (UAC-запрос).
        #
        # 🔴 EXE ИЗ WindowsApps (Store-приложения) прямым запуском НЕ
        # стартуем: без package identity процесс-зомби возникает без
        # окна — их запускают AUMID (шаг 1) или каталог Пуска (шаг 4).
        if (
            info.exe_path
            and os.path.exists(info.exe_path)
            and "windowsapps" not in info.exe_path.lower()
        ):
            exe_dir = os.path.dirname(info.exe_path) or None

            # 2a. Разрешённый ярлык Пуска: аргументы + рабочая папка.
            try:
                from core.shortcut_index import resolve_for_exe

                resolved = resolve_for_exe(info.exe_path)
            except Exception as exc:
                resolved = None
                logger.debug("shortcut resolve failed: %s", exc)

            if resolved:
                target, arguments, working_dir, lnk_path = resolved
                command = f'"{target}"'
                if arguments.strip():
                    command += f" {arguments.strip()}"
                try:
                    subprocess.Popen(
                        command,
                        cwd=working_dir.strip() or exe_dir,
                        shell=False,
                    )
                    return True
                except Exception as exc:
                    logger.warning(
                        "shortcut launch %s failed: %s", target, exc
                    )
                    try:
                        # Ярлык сам несёт свою рабочую папку и флаг
                        # «запуск от администратора».
                        return WindowApplier._shellexecute(lnk_path)
                    except Exception as exc2:
                        logger.warning(
                            "lnk shellexecute %s failed: %s", lnk_path, exc2
                        )

            # 2b. Прямой запуск с рабочей папкой exe.
            try:
                subprocess.Popen(
                    [info.exe_path],
                    cwd=exe_dir,
                    shell=False,
                )
                return True
            except Exception as exc:
                logger.warning("exe launch %s failed: %s", info.exe_path, exc)
                try:
                    # 740 (UAC) и прочее: с рабочей папкой и UAC-запросом.
                    return WindowApplier._shellexecute(
                        info.exe_path, exe_dir
                    )
                except Exception as exc2:
                    logger.warning(
                        "shellexecute %s failed: %s", info.exe_path, exc2
                    )

        # 3. Системный каталог — приоритет для настроек/панели управления.
        if name_lower in WindowApplier.SYSTEM_LAUNCHERS:
            cmd = WindowApplier.SYSTEM_LAUNCHERS[name_lower]
            try:
                subprocess.Popen(
                    cmd, shell=False,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
                return True
            except Exception as exc:
                logger.warning("system launch %s failed: %s", cmd, exc)

        # 4. Каталог Пуска (shell:AppsFolder): там есть ВСЕ приложения —
        # и Win32 (путь к exe), и UWP (AUMID). Ищем по имени exe,
        # затем по отображаемому имени (= заголовку окна).
        for launch_target in WindowApplier._apps_folder_targets(
            name_lower, info.title
        ):
            try:
                if launch_target.lower().endswith(".exe") and os.path.exists(launch_target):
                    # 🔴 С рабочей папкой и поддержкой UAC (см. шаг 2b).
                    if not WindowApplier._shellexecute(
                        launch_target,
                        os.path.dirname(launch_target),
                    ):
                        logger.warning(
                            "shellexecute вернул %s для %s",
                            launch_target, launch_target,
                        )
                else:
                    subprocess.Popen(
                        ["explorer.exe", f"shell:AppsFolder\\{launch_target}"],
                        shell=False,
                    )
                return True
            except Exception as exc:
                logger.warning("apps-folder launch %s failed: %s", launch_target, exc)

        # 5. Обычный путь — имя exe через startfile.
        try:
            os.startfile(process_name)
            return True
        except Exception as exc:
            logger.warning("launch %s failed: %s", process_name, exc)
            return False

    # ----------------------------------------------------------

    @staticmethod
    def _apps_folder():
        # Список приложений Пуска: [(name, target), ...].
        try:
            import win32com.client
            shell = win32com.client.Dispatch("Shell.Application")
            namespace = shell.NameSpace("shell:AppsFolder")
            items = []
            for item in namespace.Items():
                try:
                    items.append((str(item.Name), str(item.Path)))
                except Exception:
                    pass
            return items
        except Exception as exc:
            logger.warning("apps folder enumeration failed: %s", exc)
            return []

    # ----------------------------------------------------------

    @staticmethod
    def _apps_folder_targets(process_name, title):
        # Кандидаты запуска из каталога Пуска по имени процесса
        # и по заголовку окна (у UWP имя = заголовок).
        name_low = process_name.lower()
        title_low = (title or "").strip().lower()
        targets = []

        apps = WindowApplier._apps_folder()

        for name, target in apps:
            target_low = target.lower()
            if target_low.endswith("\\" + name_low) or target_low.endswith("/" + name_low):
                targets.append(target)

        if not targets and title_low:
            for name, target in apps:
                if name.lower() == title_low:
                    targets.append(target)

        return targets

    # ----------------------------------------------------------

    @staticmethod
    def _escape_sendkeys(text):
        # Спецсимволы SendKeys: + ^ % ~ ( ) { }
        special = set("+^%~(){}")
        return "".join(
            "{" + ch + "}" if ch in special else ch
            for ch in text
        )

    # ----------------------------------------------------------

    @staticmethod
    def _force_foreground(hwnd, attempts=6):
        # 🔴 Вытаскивает окно на передний план и ДОКАЗЫВАЕТ это.
        # Прямой SetForegroundWindow молча отклоняется системой, если
        # у процесса нет «права на фокус» (давно не было ввода), —
        # типично при загрузке пресета, где перед папками стартуют
        # OBS/редакторы и перехватывают фокус. Приём «Alt-тап» даёт
        # системе пользовательское разрешение на смену переднего плана.
        for _attempt in range(attempts):
            try:
                if win32gui.GetForegroundWindow() == hwnd:
                    return True
            except Exception:
                return False

            try:
                win32api.keybd_event(0x12, 0, 0, 0)  # Alt down
                win32api.keybd_event(
                    0x12, 0, win32con.KEYEVENTF_KEYUP, 0  # Alt up
                )
            except Exception:
                pass

            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass

            time.sleep(0.25)

        try:
            return win32gui.GetForegroundWindow() == hwnd
        except Exception:
            return False

    # ----------------------------------------------------------

    @staticmethod
    def _open_tabs(hwnd, paths):
        # 🔴 Вкладки Win11-проводника: Ctrl+T создаёт вкладку,
        # Ctrl+L + путь + Enter переходит по адресу. Работает только
        # с окном на переднем плане.
        #
        # 🔴 БЕЗ ОХРАНЫ ФОКУСА ВКЛАДКИ ТЕРЯЛИСЬ: клавиши шлются в
        # АКТИВНОЕ окно, и если проводник не удалось выдвинуть вперёд
        # (фокус у стартующих программ), путь печатался в ЧУЖОЕ
        # приложение, а вкладка не открывалась. Теперь перед каждой
        # вкладкой фокус форсируется, а без успеха печать отменяется.
        paths = [p for p in paths if p]
        if not paths:
            return

        try:
            import win32com.client
            wsh = win32com.client.Dispatch("WScript.Shell")
        except Exception as exc:
            logger.warning("_open_tabs: WScript.Shell недоступен: %s", exc)
            return

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception as exc:
            logger.warning("_open_tabs: окно %s недоступно: %s", hwnd, exc)
            return

        if not WindowApplier._force_foreground(hwnd):
            logger.warning(
                "_open_tabs: проводник не удалось выдвинуть на передний "
                "план, вкладки не открывались: %s",
                paths,
            )
            return

        time.sleep(0.4)

        for index, folder in enumerate(paths):
            target = WindowApplier._virtual_folder_arg(folder)
            if not target:
                continue
            if (
                target != "shell:MyComputerFolder"
                and not os.path.isdir(target)
            ):
                logger.warning(
                    "_open_tabs: папки не существует, пропущена: %s", folder
                )
                continue

            # Фокус могли перехватить стартующие приложения —
            # проверяем и возвращаем перед КАЖДОЙ вкладкой.
            if not WindowApplier._force_foreground(hwnd):
                logger.warning(
                    "_open_tabs: фокус потерян, оставшиеся вкладки "
                    "пропущены: %s",
                    paths[index:],
                )
                break

            try:
                wsh.SendKeys("^t")
                time.sleep(0.6)
                wsh.SendKeys("^l")
                time.sleep(0.2)
                wsh.SendKeys(
                    WindowApplier._escape_sendkeys(target) + "{ENTER}"
                )
                time.sleep(0.8)
            except Exception as exc:
                logger.warning("open tab %s failed: %s", folder, exc)

    # ----------------------------------------------------------

    @staticmethod
    def _wait_for_window(process_name, used, timeout=LAUNCH_TIMEOUT):
        # Ждёт, пока у процесса появится окно верхнего уровня
        # (не занятое другими окнами пресета).
        proc_key = (process_name or "").lower()
        deadline = time.time() + timeout

        while time.time() < deadline:
            live = WindowApplier._live_map()
            for _title, hwnd in live.get(proc_key, []):
                if hwnd not in used:
                    return hwnd
            time.sleep(LAUNCH_POLL)

        return None

    # ----------------------------------------------------------

    @staticmethod
    def _wait_for_explorer(before_hwnds, used, folder_hint, timeout=LAUNCH_TIMEOUT):
        # 🔴 Ждём окно проводника после запуска по адресу.
        # Приоритет: окно, показывающее нужную папку → новое окно
        # (появилось после запуска) → любое незанятое. В COM карта
        # вкладок появляется с задержкой, поэтому новому окну даём
        # полторы секунды подтвердить папку.
        deadline = time.time() + timeout
        fallback = None
        started = time.time()

        while time.time() < deadline:
            try:
                tabs_map = FolderScanner.scan_hwnd_map()
            except Exception:
                tabs_map = {}

            live = WindowApplier._live_map()
            for _title, hwnd in live.get("explorer.exe", []):
                if hwnd in used:
                    continue
                hint = (folder_hint or "").lower()
                tabs = [t.lower() for t in tabs_map.get(hwnd, [])]
                if hint and hint in tabs:
                    return hwnd
                if hwnd not in before_hwnds and fallback is None:
                    fallback = hwnd

            if fallback is not None and time.time() - started > 1.5:
                return fallback

            time.sleep(LAUNCH_POLL)

        return fallback

    # ----------------------------------------------------------

    @staticmethod
    def apply(preset):
        """Применяет пресет. Возвращает dict со статистикой."""
        result = {
            "applied": 0,
            "launched": 0,
            "not_found": 0,
            "folders": 0,
            "skipped": 0,
        }

        if not WindowApplier._is_available():
            logger.error("WindowApplier: win32 недоступен")
            return result

        used = set()
        placed = []  # [(hwnd, info)] — им повторно ставим геометрию
        launched_processes = set()  # процессы, уже запущенные этой загрузкой

        # 🔴 Карта вкладок живых окон проводника — для матчинга по адресу
        # (заголовки «X — проводник» неразличимы между окнами).
        explorer_tabs = {}
        if any((w.process or "").lower() == "explorer.exe" for w in preset.windows):
            explorer_tabs = FolderScanner.scan_hwnd_map()

        for info in preset.windows:
            proc_key = (info.process or "").lower()

            # 🔴 Микро-записи из старых пресетов (служебные окна
            # 41x41 и т.п.) не запускаются — они и не приложения;
            # их запуск вызывал повторный старт всего приложения.
            if (
                info.width < MIN_WINDOW_DIMENSION
                or info.height < MIN_WINDOW_DIMENSION
            ):
                result["skipped"] += 1
                logger.info("микро-запись пресета, пропущена: %s", info.title or proc_key)
                continue

            # 🔴 ЖЕЛЕЗНОЕ ПРАВИЛО: сама программа WindowPresets и окна
            # терминалов никогда не открываются и не трогаются — даже
            # если попали в старый пресет или указаны вручную.
            if WindowFilters.is_self(proc_key) or WindowFilters.is_terminal_host(proc_key):
                result["skipped"] += 1
                logger.info("системное окно, пропущено: %s", info.title or proc_key)
                continue

            # 🔴 Исключения из настроек: эти окна НЕ открываем
            # и вообще не трогаем (окно, если открыто, остаётся как есть).
            if IgnoreList.matches(
                process=info.process,
                exe_path=info.exe_path,
                title=info.title,
                folders=[info.folder] + list(info.tabs),
            ):
                result["skipped"] += 1
                logger.info("окно в исключениях, пропущено: %s", info.title or info.process)
                continue

            # Сначала ищем среди уже открытых.
            live = WindowApplier._live_map()
            candidates = [
                (title, hwnd)
                for title, hwnd in live.get(proc_key, [])
                if hwnd not in used
            ]
            hwnd = WindowApplier._pick_hwnd(candidates, info, used, explorer_tabs)
            launched_now = False

            # Не найдено — пробуем запустить процесс.
            if hwnd is None and proc_key:

                launch_started = False

                # 🔴 Проводник запускаем сразу по адресу первой вкладки,
                # иначе открывается «Мой компьютер» по умолчанию.
                if proc_key == "explorer.exe":
                    folder_arg = WindowApplier._virtual_folder_arg(info.folder)
                    if folder_arg and (
                        folder_arg == "shell:MyComputerFolder"
                        or os.path.isdir(folder_arg)
                    ):
                        before = {
                            h for _t, h in live.get("explorer.exe", [])
                        }
                        try:
                            subprocess.Popen(
                                ["explorer.exe", folder_arg],
                                shell=False,
                            )
                            launch_started = True
                            hwnd = WindowApplier._wait_for_explorer(
                                before, used, info.folder
                            )
                        except Exception as exc:
                            logger.warning("explorer launch failed: %s", exc)

                # 🔴 КАЖДЫЙ ПРОЦЕСС — НЕ БОЛЕЕ ОДНОГО ЗАПУСКА ЗА ЗАГРУЗКУ.
                # Повторные записи пресета того же процесса (например,
                # проектор OBS или второе окно) ждут появления окна,
                # но приложение заново НЕ запускают — иначе оно
                # открывалось несколько раз (OBS, AutoCAD).
                can_launch = (
                    proc_key not in launched_processes
                    or proc_key == "explorer.exe"
                )

                if hwnd is None and not launch_started and not can_launch:
                    hwnd = WindowApplier._wait_for_window(
                        proc_key, used, timeout=LAUNCH_SECONDARY_WAIT
                    )

                if hwnd is None and not launch_started and can_launch:
                    launch_started = WindowApplier._launch(proc_key, info)

                if launch_started:
                    launched_processes.add(proc_key)

                if hwnd is None and launch_started:
                    hwnd = WindowApplier._wait_for_window(proc_key, used)

                if hwnd is not None:
                    # 🔴 «Запущено» — только за РЕАЛЬНЫЙ запуск: окно,
                    # найденное у уже запущенного процесса (вторичные
                    # записи пресета), запуском не является.
                    if launch_started:
                        result["launched"] += 1
                        launched_now = True

            if hwnd is None:
                result["not_found"] += 1
                logger.info("не найдено окно: %s — %s", info.process, info.title)
                continue

            used.add(hwnd)

            # 🔴 Вкладки — только у свежезапущенных окон проводника:
            # у уже открытых вкладки не трогаем (пользователь мог их изменить).
            if launched_now and proc_key == "explorer.exe" and len(info.tabs) > 1:
                WindowApplier._open_tabs(hwnd, info.tabs[1:])

            if WindowApplier._set_geometry(hwnd, info):
                result["applied"] += 1

            placed.append((hwnd, info))

        # 🔴 Повторное применение геометрии: программы (особенно
        # Store-приложения вроде Блокнота) любят АСИНХРОННО вернуть
        # свою последнюю позицию и перетереть нашу — иногда ПОЗЖЕ
        # нашего повторного прохода. Поэтому проверяем геометрию
        # волнами и переустанавливаем, пока не совпадёт.
        if placed:
            time.sleep(GEOMETRY_REAPPLY_DELAY)

            for _attempt in range(3):

                dirty = False

                for hwnd, info in placed:
                    try:
                        if not win32gui.IsWindow(hwnd):
                            continue
                        if not WindowApplier._geometry_matches(hwnd, info):
                            WindowApplier._set_geometry(hwnd, info)
                            dirty = True
                    except Exception as exc:
                        logger.debug("reapply %s failed: %s", hwnd, exc)

                if not dirty:
                    break

                time.sleep(GEOMETRY_REAPPLY_DELAY)

        # 🔴 Папки — открываем только те, которых НЕТ среди окон пресета.
        # Окна проводника (explorer.exe) уже восстановлены выше как WindowInfo
        # (вместе со вкладками), поэтому не дублируем открытие.
        import os.path as ospath

        # Точные адреса и заголовки, уже покрытые окнами проводника.
        covered_folders = set()
        covered_explorer_titles = set()
        for w in preset.windows:
            if (w.process or "").lower() == "explorer.exe":
                for path in [w.folder] + list(w.tabs):
                    if path:
                        covered_folders.add(path.strip().lower())
                covered_explorer_titles.add((w.title or "").strip().lower())

        for folder in preset.folders:
            folder_norm = (folder or "").strip().lower()

            # 🔴 Исключение по папке — не открываем.
            if IgnoreList.matches(folders=[folder or ""]):
                logger.info("папка в исключениях, пропущена: %s", folder)
                continue

            # 🔴 Точное покрытие по адресу окна/вкладки — не открываем повторно.
            if folder_norm in covered_folders:
                logger.info("папка уже открыта окном пресета: %s", folder)
                continue

            # 🔴 «Этот компьютер» и виртуальные папки — спец.командой,
            # только если такого окна нет в пресете.
            if folder.startswith("Этот компьютер") or folder_norm.startswith("this pc"):
                if "этот компьютер" in str(covered_explorer_titles).lower():
                    continue
                try:
                    subprocess.Popen(["explorer.exe", "shell:MyComputerFolder"],
                                     shell=False)
                    result["folders"] += 1
                except Exception as exc:
                    logger.warning("open This PC failed: %s", exc)
                continue

            # 🔴 Запасная проверка через заголовок окна проводника
            # (для старых пресетов без поля folder).
            already_covered = False
            for title in covered_explorer_titles:
                if folder_norm and (
                    folder_norm in title
                    or ospath.basename(folder_norm) in title
                ):
                    already_covered = True
                    break
            if already_covered:
                continue

            try:
                if os.path.isdir(folder):
                    os.startfile(folder)
                    result["folders"] += 1
                else:
                    logger.warning(
                        "папка не существует, не открыта: %s", folder
                    )
            except Exception as exc:
                logger.warning("open folder %s failed: %s", folder, exc)

        logger.info("apply result: %s", result)
        return result
