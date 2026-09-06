r"""
Автозапуск программы при старте Windows.

Запись в реестре (текущий пользователь, прав админа не нужно):
    HKCU\Software\Microsoft\Windows\CurrentVersion\Run
    "WindowPresets" = "<команда запуска>"

Команда:
  • из .exe-сборки — сам путь к exe;
  • из исходников — pythonw.exe (БЕЗ окна консоли) + main.py;
    запасной вариант — pyw.exe -3.14, затем обычный python.
"""

import logging
import os
import shutil
import sys
import winreg
from pathlib import Path

logger = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "WindowPresets"


def _command():
    # Команда автозапуска для текущей установки программы.
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    main_py = Path(__file__).resolve().parent.parent / "main.py"

    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if os.path.exists(pythonw):
        return f'"{pythonw}" "{main_py}"'

    pyw = shutil.which("pyw")
    if pyw:
        return f'"{pyw}" -3.14 "{main_py}"'

    return f'"{sys.executable}" "{main_py}"'


def set_autostart(enabled):
    # Включить/выключить автозапуск (синхронно с реестром).
    # True/False — успех операции.
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(
                    key, _VALUE_NAME, 0, winreg.REG_SZ, _command()
                )
            else:
                try:
                    winreg.DeleteValue(key, _VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        logger.exception("не удалось изменить автозапуск в реестре")
        return False


def autostart_command():
    # Текущая команда автозапуска из реестра или None.
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
            return value
    except OSError:
        return None
