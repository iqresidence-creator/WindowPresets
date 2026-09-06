import logging
import os

logger = logging.getLogger(__name__)

# Кэш индекса ярлыков на всю сессию программы.
_index = None


def _start_menu_folders():
    folders = []

    appdata = os.environ.get("APPDATA")
    if appdata:
        folders.append(
            os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")
        )

    program_data = os.environ.get("ProgramData")
    if program_data:
        folders.append(
            os.path.join(program_data, "Microsoft", "Windows", "Start Menu", "Programs")
        )

    return folders


def _read_shortcut(path, shell=None):
    # (target, arguments, working_dir) ярлыка; пустые строки при ошибке.
    try:
        if shell is None:
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")

        shortcut = shell.CreateShortCut(path)

        target = getattr(shortcut, "Targetpath", "") or ""
        arguments = getattr(shortcut, "Arguments", "") or ""
        working_dir = getattr(shortcut, "WorkingDirectory", "") or ""

        return target, arguments, working_dir

    except Exception:
        return "", "", ""


def _build_index():
    # [(target_lower, arguments, working_dir, lnk_path), ...]
    entries = []

    shell = None
    try:
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception:
        shell = None

    for folder in _start_menu_folders():

        if not os.path.isdir(folder):
            continue

        for root, _dirs, files in os.walk(folder):

            for name in files:

                if not name.lower().endswith(".lnk"):
                    continue

                path = os.path.join(root, name)
                target, arguments, working_dir = _read_shortcut(path, shell)

                if target:
                    entries.append(
                        (target.lower(), arguments, working_dir, path)
                    )

    return entries


def get_index():
    global _index

    if _index is None:
        import time

        started = time.time()
        _index = _build_index()
        logger.info(
            "индекс ярлыков Пуска: %d шт за %.1f сек",
            len(_index), time.time() - started,
        )

    return _index


def resolve_for_exe(exe_path):
    # 🔴 Находит ярлык Пуска, указывающий на этот exe, и возвращает
    # (target, arguments, working_dir, lnk_path). Это позволяет
    # запускать программу ИМЕННО так, как задумано её ярлыком —
    # с аргументами и рабочей папкой (специальные лаунчеры и т.п.).
    if not exe_path:
        return None

    exe = str(exe_path).strip().lower()

    if not exe:
        return None

    index = get_index()

    # Точное совпадение пути.
    matches = [e for e in index if e[0] == exe]

    # Один путь является концом другого (разные регистры/сокращения).
    if not matches:
        matches = [
            e for e in index
            if e[0].endswith(exe) or exe.endswith(e[0])
        ]

    return matches[0] if matches else None
