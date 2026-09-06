import ctypes
import logging
import os

try:
    import win32con
    import win32gui
    import win32process
    import psutil
except Exception:
    win32con = None
    win32gui = None
    win32process = None
    psutil = None


logger = logging.getLogger(__name__)

kernel32 = ctypes.windll.kernel32
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class WindowFilters:

    BLACKLISTED_PROCESSES = {
        "applicationframehost.exe",  # сами по себе — пустые хосты-зомби
        # (реальные UWP-приложения за ними резолвит WindowScanner)
        "runtimebroker.exe",
        "textinputhost.exe",
        "searchhost.exe",
        "startmenuexperiencehost.exe",
        "shellexperiencehost.exe",
        "widgetboard.exe",
        "fontdrvhost.exe",
    }

    BLACKLISTED_CLASSES = {
        "Shell_TrayWnd",
        "Progman",
        "WorkerW",
        "XamlExplorerHostIslandWindow",
        # 🔴 Скрытое «мусорное» окно dwm.exe: vis=0, но IsIconic=True —
        # пролезало в пресет через ветку свёрнутых окон.
        "Dwm",
    }

    # 🔴 Процессы-хосты самой программы WindowPresets.
    # Их окна (главное окно приложения + консоль) не сохраняем в пресет.
    SELF_PROCESSES = {
        "python.exe",
        "py.exe",
        "pythonw.exe",
    }

    @staticmethod
    def is_self(process_name):
        # 🔴 Железное правило: сама программа WindowPresets никогда
        # не участвует в операциях с окнами — не сохраняется,
        # не открывается, не закрывается. Проверяется на всех уровнях.
        return (process_name or "").strip().lower() in WindowFilters.SELF_PROCESSES

    # 🔴 Хосты терминалов: окна, в которых живут консоли (в том числе
    # консоль самой программы WindowPresets, запущенной через run.bat).
    # Windows 11 по умолчанию открывает консоли в Windows Terminal —
    # класс окна уже НЕ ConsoleWindowClass, поэтому защищаем по процессу.
    # Такие окна не сохраняются в пресеты и никогда не закрываются
    # (в одном окне терминала могут жить и другие вкладки пользователя).
    TERMINAL_HOST_PROCESSES = {
        "windowsterminal.exe",
        "wt.exe",
        "conhost.exe",
        "openconsole.exe",
        "cmd.exe",
    }

    @staticmethod
    def is_terminal_host(process_name):
        return (process_name or "").strip().lower() in WindowFilters.TERMINAL_HOST_PROCESSES

    DWMWA_CLOAKED = 13

    @staticmethod
    def is_available():

        return all((
            win32gui is not None,
            win32process is not None,
            psutil is not None,
            win32con is not None,
        ))

    @staticmethod
    def is_console_class(hwnd):
        # Консольное окно (где запущен python).
        try:
            cls = win32gui.GetClassName(hwnd)
            return cls in ("ConsoleWindowClass", "TTY")
        except Exception:
            return False

    @staticmethod
    def is_cloaked(hwnd):
        # 🔴 Cloaked-окно рисуется не на экране ( suspended UWP и т.п.).
        # IsWindowVisible у него True, хотя пользователь его не видит.
        try:
            val = ctypes.c_int(0)
            ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, WindowFilters.DWMWA_CLOAKED,
                ctypes.byref(val), 4,
            )
            return bool(val.value)
        except Exception:
            return False

    @staticmethod
    def has_owner(hwnd):
        # Есть окно-владелец (диалог/всплывашка родительского приложения).
        try:
            return bool(win32gui.GetWindow(hwnd, win32con.GW_OWNER))
        except Exception:
            return False

    @staticmethod
    def is_toolwindow(hwnd):
        try:
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            return bool(ex & win32con.WS_EX_TOOLWINDOW)
        except Exception:
            return False

    @staticmethod
    def process_name(hwnd):

        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        try:
            return psutil.Process(pid).name().lower()
        except Exception:
            # 🔴 psutil падает на процессах в песочнице (Sandboxie) и
            # повышенных — иначе такое окно просто терялось фильтром.
            # Берём имя из полного пути через ctypes-запрос.
            full_path = WindowFilters.exe_path_of_pid(pid)
            if full_path:
                return os.path.basename(full_path).lower()
            raise

    @staticmethod
    def exe_path_of_pid(pid):
        # 🔴 Полный путь к exe. psutil бросает AccessDenied для чужих/
        # повышенных процессов — тогда ctypes-запрос с правами
        # PROCESS_QUERY_LIMITED_INFORMATION (работает почти всегда).
        try:
            return psutil.Process(pid).exe() or ""
        except Exception:
            pass

        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return ""

        try:
            size = ctypes.c_uint32(1024)
            buf = ctypes.create_unicode_buffer(1024)
            ok = kernel32.QueryFullProcessImageNameW(
                handle, 0, buf, ctypes.byref(size)
            )
            return buf.value if ok else ""
        finally:
            kernel32.CloseHandle(handle)

    @staticmethod
    def aumid_of_pid(pid):
        # 🔴 AUMID приложения (для надёжного запуска UWP через
        # shell:AppsFolder\<aumid>). Пустая строка = не UWP.
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return ""

        try:
            size = ctypes.c_uint32(512)
            buf = ctypes.create_unicode_buffer(512)
            ok = kernel32.GetApplicationUserModelId(
                handle, ctypes.byref(size), buf
            )
            return buf.value if ok == 0 else ""
        finally:
            kernel32.CloseHandle(handle)

    @staticmethod
    def class_name(hwnd):

        try:
            return win32gui.GetClassName(hwnd)
        except Exception:
            return ""

    @staticmethod
    def is_real_window(hwnd):
        # 🔴 Правило ТЗ: сохраняем всё, что визуально отображается
        # на экране ИЛИ свёрнуто в панель задач.
        # Не сохраняем: скрытые процессы, службы, трей, системный мусор.

        if not win32gui.IsWindow(hwnd):
            return False

        visible = win32gui.IsWindowVisible(hwnd)
        iconic = win32gui.IsIconic(hwnd)

        # 🔴 Ключевая проверка: окно видно ИЛИ оно свёрнуто (IsIconic).
        # Скрытые окна (ни видны, ни свёрнуты) — отбрасываем.
        if not visible and not iconic:
            return False

        # 🔴 Cloaked-окна «видимы» по IsWindowVisible, но не отображаются
        # на экране (подвешенные UWP) — не сохраняем.
        if WindowFilters.is_cloaked(hwnd) and not iconic:
            return False

        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return False

        # 🔴 Системный мусор по классу окна — не трогаем.
        class_name = WindowFilters.class_name(hwnd)
        if class_name in WindowFilters.BLACKLISTED_CLASSES:
            return False

        # 🔴 Свёрнутое, но НЕ видимое окно должно иметь кнопку в панели
        # задач: без владельца и не TOOLWINDOW. Иначе это скрытые
        # окна-помощники (DWM Notification Window, трейные утилиты),
        # которые «притворяются» свёрнутыми.
        if not visible and iconic:
            if WindowFilters.has_owner(hwnd):
                return False
            if WindowFilters.is_toolwindow(hwnd):
                return False

        try:
            process_name = WindowFilters.process_name(hwnd)
        except Exception:
            return False

        if process_name in WindowFilters.BLACKLISTED_PROCESSES:
            return False

        return True
