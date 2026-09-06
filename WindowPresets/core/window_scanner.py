import logging
import os

try:
    import win32gui
    import win32con
    import win32api
    import win32process
    import psutil
except Exception:
    win32gui = None
    win32con = None
    win32api = None
    win32process = None
    psutil = None

from core.ignore_list import IgnoreList
from core.preset import WindowInfo
from core.window_filters import WindowFilters


logger = logging.getLogger(__name__)

# 🔴 Микро-окна с меньшей стороной меньше этого — служебные помощники
# (AdApplicationButton 41x41, AcIpcMsgWindow 237x39, окна 0x0). Они не
# имеют кнопки на панели задач; сохранение их как отдельных «программ»
# вызывало ДВОЙНОЙ запуск приложений (AutoCAD) при загрузке пресета.
MIN_WINDOW_DIMENSION = 60

# 🔴 Хосты-интерпретаторы: их окно — это запущенный СКРИПТ.
# exe_path такого окна бесполезен для запуска (wscript.exe без
# аргументов ничего не откроет) — сохраняем путь к самому скрипту.
SCRIPT_HOSTS = {
    "wscript.exe",
    "cscript.exe",
    "mshta.exe",
    "powershell.exe",
    "pwsh.exe",
    "autohotkey.exe",
    "autoit3.exe",
}

SCRIPT_EXTENSIONS = (
    ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".hta", ".ps1", ".psm1", ".bat", ".cmd", ".ahk", ".au3",
)


class WindowScanner:
    """Сканирует видимые окна приложений в объекты WindowInfo.

    collect_live() — единый снимок «живых» окон: его используют
    сканер пресетов, применитель (матчинг окон) и закрыватель,
    поэтому все видят одинаковый список окон.
    """

    @staticmethod
    def _monitor_handles():
        # Список handle мониторов в порядке EnumDisplayMonitors.
        # Индекс в этом списке = поле monitor окна.
        try:
            monitors = win32api.EnumDisplayMonitors()
            return [handle for handle, _rect, _info in monitors]
        except Exception:
            return []

    # ----------------------------------------------------------

    @staticmethod
    def monitor_count():
        # 🔴 Число ФИЗИЧЕСКИ подключённых мониторов прямо сейчас
        # (та же нумерация, что у индексов monitor у окон).
        if not WindowFilters.is_available():
            return 0
        return len(WindowScanner._monitor_handles())

    # ----------------------------------------------------------

    @staticmethod
    def _hosted_app(frame_hwnd, frame_pid):
        # 🔴 UWP-приложение за фреймом ApplicationFrameHost:
        # ищем дочернее CoreWindow ЧУЖОГО процесса — это и есть
        # реальное приложение (photos.exe и т.п.).
        # Возвращает (process_name, pid) или None для пустых хостов.
        found = None


        def walk(child, _):
            nonlocal found
            try:
                if win32gui.GetClassName(child) != "Windows.UI.Core.CoreWindow":
                    return
                _, pid = win32process.GetWindowThreadProcessId(child)
                if pid == frame_pid:
                    return
                name = psutil.Process(pid).name().lower()
                if name not in ("applicationframehost.exe", "explorer.exe"):
                    found = (name, pid)
            except Exception:
                pass


        try:
            win32gui.EnumChildWindows(frame_hwnd, walk, None)
        except Exception:
            pass

        return found

    # ----------------------------------------------------------

    @staticmethod
    def _monitor_index(hwnd, normal_rect, monitor_handles):
        # 🔴 Монитор свёрнутого окна нельзя брать через MonitorFromWindow
        # (окно стоит в -32000,-32000) — используем НОРМАЛЬНЫЕ координаты.
        try:
            if win32gui.IsIconic(hwnd):
                handle = win32api.MonitorFromRect(
                    normal_rect, win32con.MONITOR_DEFAULTTONEAREST
                )
            else:
                handle = win32api.MonitorFromWindow(
                    hwnd, win32con.MONITOR_DEFAULTTONEAREST
                )
            if handle in monitor_handles:
                return monitor_handles.index(handle)
        except Exception:
            pass
        return 0

    # ----------------------------------------------------------

    @staticmethod
    def _script_target(pid, process_name, exe_path):
        # 🔴 Для окон-скриптов возвращаем путь к самому файлу скрипта
        # из командной строки хоста (wscript.exe "...\script.vbs").
        # Если скрипт в аргументах не найден — остаётся путь к хосту.
        if process_name not in SCRIPT_HOSTS:
            return exe_path

        try:
            cmdline = psutil.Process(pid).cmdline()
        except Exception:
            return exe_path

        if not cmdline:
            return exe_path

        for arg in cmdline[1:]:
            arg = (arg or "").strip().strip('"')
            if arg.lower().endswith(SCRIPT_EXTENSIONS) and os.path.isfile(arg):
                return arg

        return exe_path

    # ----------------------------------------------------------

    @staticmethod
    def collect_live():
        # Снимок всех «настоящих» окон. Каждый элемент:
        #   {hwnd, title, process, host_process, exe_path, aumid,
        #    host_class, minimized, maximized,
        #    x, y, width, height, monitor}
        #
        # process — реальное приложение: для UWP-хостов
        # (applicationframehost.exe) подставляется процесс
        # приложения за фреймом, чтобы матчинг/запуск работали.
        result = []

        if not WindowFilters.is_available():
            return result

        monitor_handles = WindowScanner._monitor_handles()

        def base_fields(hwnd, process, pid):
            # Общие поля для обычных окон и UWP-фреймов.
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            maximized = bool(style & win32con.WS_MAXIMIZE)
            minimized = bool(win32gui.IsIconic(hwnd))

            # 🔴 GetWindowPlacement даёт НОРМАЛЬНЫЕ координаты
            # (восстановленного состояния), а не maximized с полями -8.
            try:
                placement = win32gui.GetWindowPlacement(hwnd)
                rect = placement[4]
            except Exception:
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                rect = (left, top, right, bottom)

            return {
                "title": win32gui.GetWindowText(hwnd).strip(),
                "process": process,
                "host_process": process,
                "exe_path": WindowScanner._script_target(
                    pid, process,
                    WindowFilters.exe_path_of_pid(pid),
                ),
                "aumid": WindowFilters.aumid_of_pid(pid),
                "host_class": WindowFilters.class_name(hwnd),
                "minimized": minimized,
                "maximized": maximized,
                "x": rect[0],
                "y": rect[1],
                "width": rect[2] - rect[0],
                "height": rect[3] - rect[1],
                "monitor": WindowScanner._monitor_index(hwnd, rect, monitor_handles),
            }

        def enum(hwnd, _):
            if not WindowFilters.is_real_window(hwnd):
                return

            # 🔴 ЖЕЛЕЗНОЕ ПРАВИЛО: сама программа WindowPresets, её
            # консоль и окна терминалов исключены из ЛЮБЫХ операций —
            # уже на уровне общего снимка окон (это видят сканер,
            # список программ, матчинг применителя и оба закрытия).
            if WindowFilters.is_console_class(hwnd):
                return

            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc_obj = psutil.Process(pid)
                process = proc_obj.name().lower()

                if WindowFilters.is_self(process):
                    return

                if WindowFilters.is_terminal_host(process):
                    return

                # 🔴 ЗАМОРОЗКА Store-приложений: при закрытии окна
                # Windows не выгружает UWP-процесс, а замораживает его
                # (status=stopped), оставляя «видимое» окно-призрак —
                # его нет ни на экране, ни в панели задач (например,
                # video.ui.exe «Кино и ТВ»). Замороженный процесс
                # физически не может ничего отображать — не сохраняем.
                try:
                    if proc_obj.status() == psutil.STATUS_STOPPED:
                        return
                except Exception:
                    pass

                fields = base_fields(hwnd, process, pid)
                fields["hwnd"] = hwnd

                # 🔴 Микро-окна-помощники — не приложения.
                if (
                    fields["width"] < MIN_WINDOW_DIMENSION
                    or fields["height"] < MIN_WINDOW_DIMENSION
                ):
                    return

                # 🔴 Исключения из настроек: эти окна никто не видит —
                # не сохраняются, не открываются, не закрываются.
                if IgnoreList.matches(
                    process=fields["process"],
                    exe_path=fields["exe_path"],
                    title=fields["title"],
                ):
                    return

                result.append(fields)
            except Exception as exc:
                logger.warning("collect_live: пропуск окна %s: %s", hwnd, exc)

        def enum_frames(hwnd, _):
            # 🔴 Окна ApplicationFrameHost: процесс в блэклисте, потому
            # что ПУСТЫЕ фреймы-зомби («Параметры» без приложения) — мусор.
            # Но фрейм с живым приложением внутри — окно реального
            # UWP-приложения: сохраняем его под именем приложения.
            try:
                if WindowFilters.class_name(hwnd) != "ApplicationFrameWindow":
                    return
                if not win32gui.IsWindowVisible(hwnd):
                    return
                if WindowFilters.is_cloaked(hwnd):
                    return
                if not win32gui.GetWindowText(hwnd).strip():
                    return

                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if psutil.Process(pid).name().lower() != "applicationframehost.exe":
                    return

                hosted = WindowScanner._hosted_app(hwnd, pid)
                if hosted is None:
                    return  # пустой хост без приложения

                app_process, app_pid = hosted

                # 🔴 Сама программа WindowPresets — вне операций.
                if WindowFilters.is_self(app_process):
                    return

                # 🔴 Замороженное приложение-призрак (см. выше).
                try:
                    if psutil.Process(app_pid).status() == psutil.STATUS_STOPPED:
                        return
                except Exception:
                    pass

                fields = base_fields(hwnd, app_process, app_pid)
                fields["host_process"] = "applicationframehost.exe"
                fields["hwnd"] = hwnd

                # 🔴 Исключения из настроек — и для UWP-приложений.
                if IgnoreList.matches(
                    process=fields["process"],
                    exe_path=fields["exe_path"],
                    title=fields["title"],
                ):
                    return

                result.append(fields)
            except Exception as exc:
                logger.debug("enum_frames skip %s: %s", hwnd, exc)

        try:
            win32gui.EnumWindows(enum, None)
            win32gui.EnumWindows(enum_frames, None)
        except Exception as exc:
            logger.error("collect_live: EnumWindows упал: %s", exc)

        return result

    # ----------------------------------------------------------

    @staticmethod
    def scan(exclude_hwnds=None, folder_map=None):
        # exclude_hwnds — hwnd, которые не нужно сохранять в пресет
        # (окно самой программы WindowPresets + её консоль).
        # folder_map — {hwnd: [путь, ...]} для окон проводника:
        # список вкладок окна, первый элемент — активная вкладка.

        if not WindowFilters.is_available():
            return []

        exclude = set(exclude_hwnds or [])
        folders_by_hwnd = folder_map or {}

        windows = []

        for entry in WindowScanner.collect_live():

            try:
                hwnd = entry["hwnd"]

                # 🔴 Сама программа WindowPresets и её консоль — не сохраняем.
                if entry["process"] in WindowFilters.SELF_PROCESSES:
                    continue
                if entry["host_process"] in WindowFilters.SELF_PROCESSES:
                    continue
                if hwnd in exclude:
                    continue
                if WindowFilters.is_console_class(hwnd):
                    continue

                # 🔴 Адреса вкладок для окон проводника.
                folder_path = ""
                tabs = []
                if entry["host_process"] == "explorer.exe":
                    tabs = list(folders_by_hwnd.get(hwnd, []))
                    folder_path = tabs[0] if tabs else ""

                    # 🔴 Исключение по папке: окно с игнорируемой
                    # вкладкой не сохраняется вовсе (его также
                    # никогда не закроют — см. WindowCloser).
                    if IgnoreList.matches(
                        process=entry["process"],
                        exe_path=entry["exe_path"],
                        title=entry["title"],
                        folders=tabs,
                    ):
                        continue

                windows.append(
                    WindowInfo(
                        title=entry["title"],
                        process=entry["process"],
                        exe_path=entry["exe_path"],
                        folder=folder_path,
                        tabs=tabs,
                        aumid=entry["aumid"],
                        x=entry["x"],
                        y=entry["y"],
                        width=entry["width"],
                        height=entry["height"],
                        monitor=entry["monitor"],
                        maximized=entry["maximized"],
                        minimized=entry["minimized"],
                    )
                )

            except Exception as exc:
                # 🔴 Не глотаем ошибку молча — логируем для диагностики.
                logger.warning(
                    "WindowScanner: пропуск окна %s: %s",
                    entry.get("hwnd"), exc
                )

        return windows
