import json
import os
import subprocess
import sys
import tempfile
import zipfile

from urllib.request import Request, urlopen

from core.app_paths import base_dir
from core.settings_manager import SettingsManager

# 🔴 Текущая версия программы. НА ДОБАВЛЕНИЕ ФИЧ ПОДНИМАТЬ ВРУЧНУЮ
# — с ней сравниваются релизы GitHub.
APP_VERSION = "0.6.0"

# 🔴 Репозиторий обновлений по умолчанию (config «update_repo»
# перекрывает). Релизы GitHub крепятся к репозиторию ЦЕЛИКОМ
# (подпапка WindowPresets не важна).
DEFAULT_REPO = "iqresidence-creator/Window-Manager"


class UpdateError(Exception):
    pass


def get_repo():

    return SettingsManager.load().get(
        "update_repo", DEFAULT_REPO
    ) or DEFAULT_REPO


# --------------------------------------------------

def version_tuple(tag):

    # "v0.4.10" -> (0, 4, 10): цифры из тега, иначе сравнение
    # строк поставит "0.4.10" ниже "0.4.9".
    digits = []

    for part in tag.lstrip("vV").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        digits.append(int(num) if num else 0)

    return tuple(digits)


# --------------------------------------------------

def fetch_latest_release(repo=None):

    # Возвращает (tag, download_url) последнего релиза с zip-ассетом.
    # БЕЗ сторонних зависимостей: urllib + GitHub Releases API.
    repo = repo or get_repo()

    url = f"https://api.github.com/repos/{repo}/releases/latest"

    try:
        with urlopen(Request(url, headers={"User-Agent": "WindowPresets"}), timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise UpdateError(f"Нет связи с GitHub: {exc}") from exc

    if "tag_name" not in data:
        raise UpdateError("Релизы в репозитории не найдены")

    download_url = None

    for asset in data.get("assets") or []:
        name = (asset.get("name") or "").lower()
        if name.endswith(".zip"):
            download_url = asset.get("browser_download_url")
            break

    if not download_url:
        raise UpdateError("В релизе нет zip-архива")

    return data["tag_name"], download_url


# --------------------------------------------------

def is_newer(tag):

    try:
        return version_tuple(tag) > version_tuple(APP_VERSION)
    except Exception:
        return False


# --------------------------------------------------

def download(url, dest_path, progress=None):

    # Скачивание с колбэком прогресса progress(доля 0..1).
    try:
        with urlopen(
            Request(url, headers={"User-Agent": "WindowPresets"}),
            timeout=30,
        ) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0

            with open(dest_path, "wb") as file:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    file.write(chunk)
                    done += len(chunk)
                    if progress and total:
                        progress(min(1.0, done / total))

    except Exception as exc:
        raise UpdateError(f"Ошибка скачивания: {exc}") from exc

    return dest_path


# --------------------------------------------------

def find_exe_in_zip(zip_path):

    # Самый крупный .exe в архиве — это и есть программа
    # (в портативном zip рядом с exe лежат README и данные).
    best = None
    best_size = -1

    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.filename.lower().endswith(".exe"):
                if info.file_size > best_size:
                    best = info.filename
                    best_size = info.file_size

    return best


# --------------------------------------------------

def prepare_exe_update(zip_path):

    # 🔴 Работающий exe НЕ МОЖЕТ заменить сам себя. Схема:
    # распаковать новый exe во временную папку и создать .bat,
    # который (после закрытия программы) подменяет exe и запускает
    # программу заново. Возвращает путь к .bat (уже запущен НЕ будет).
    current_exe = sys.executable if getattr(sys, "frozen", False) else None

    if not current_exe:
        raise UpdateError("Обновление exe доступно только в сборке exe")

    inner = find_exe_in_zip(zip_path)

    if not inner:
        raise UpdateError("В архиве не найден exe")

    staging = os.path.join(
        tempfile.gettempdir(), "WindowPresets_update"
    )
    os.makedirs(staging, exist_ok=True)

    new_exe = os.path.join(staging, "WindowPresets_new.exe")

    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(inner) as src, open(new_exe, "wb") as dst:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                dst.write(chunk)

    pid = os.getpid()

    bat = os.path.join(staging, "apply_update.bat")

    with open(bat, "w", encoding="cp866", errors="replace") as file:
        file.write(
            "@echo off\r\n"
            ":wait\r\n"
            f'tasklist /FI "PID eq {pid}" | find "{pid}" >nul\r\n'
            "if not errorlevel 1 (\r\n"
            "  timeout /t 1 /nobreak >nul\r\n"
            "  goto wait\r\n"
            ")\r\n"
            f'copy /y "{new_exe}" "{current_exe}"\r\n'
            f'if exist "{new_exe}" del "{new_exe}"\r\n'
            f'if exist "{zip_path}" del "{zip_path}"\r\n'
            f'start "" "{current_exe}"\r\n'
            'del "%~f0"\r\n'
        )

    return bat


# --------------------------------------------------

def launch_apply_script(bat_path):

    # 🔴 Запуск bat ОТДЕЛЬНОЙ командой, DetachedProcess: батч живёт
    # после закрытия программы (фоновый запуск — отдельной командой,
    # не внутри цепочки).
    flags = 0x00000008  # DETACHED_PROCESS

    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=flags,
        close_fds=True,
    )
