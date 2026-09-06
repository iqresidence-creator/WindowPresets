"""
Пути программы: работают и из исходников, и из .exe (PyInstaller).

ЖИВЫЕ ДАННЫЕ (config.json, presets.json, previews/, logs/) всегда
лежат рядом с точкой запуска: в исходниках — корень проекта, у .exe —
папка самого exe-файла. Поэтому exe можно копировать в любое место
вместе с данными.

РЕСУРСЫ (assets/, ico/) — read-only: в onefile-сборке PyInstaller
распаковывает их во временную папку _MEIPASS.
"""

import sys
from pathlib import Path


def is_frozen():
    # True, если работает замороженная сборка (.exe).
    return bool(getattr(sys, "frozen", False))


def base_dir():
    # Папка живых данных.
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # app_paths.py лежит в core/ → корень проекта на уровень выше.
    return Path(__file__).resolve().parent.parent


def resource_dir():
    # Папка ресурсов (assets/, ico/).
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return base_dir()
