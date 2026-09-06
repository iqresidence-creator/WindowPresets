import os

from core.settings_manager import SettingsManager


class IgnoreList:
    """Исключения из настроек: программы и папки, которые WindowPresets
    полностью игнорирует — их окна НЕ сохраняются в пресет, НЕ
    открываются при загрузке и НИКОГДА не закрываются.

    Запись-исключение может быть:
      • именем процесса (zcode.exe);
      • именем exe-файла;
      • полным путём к файлу;
      • путём к папке — игнорируется всё, что внутри неё;
      • частью заголовка окна (не короче 3 символов);
      • путём папки для окон проводника.
    """

    @staticmethod
    def entries():
        try:
            raw = SettingsManager.load().get("ignore_list", []) or []
        except Exception:
            return []

        # На случай кривого формата в config.json.
        if isinstance(raw, dict):
            raw = list(raw.keys())

        result = []

        for item in raw:
            text = str(item).strip().lower()
            if text:
                result.append(text)

        return result

    # ----------------------------------------------------------

    @staticmethod
    def path_matches(entry, path):
        # Путь совпадает с записью ИЛИ лежит ВНУТРИ папки записи.
        path = (path or "").strip().lower()
        if not path:
            return False

        if path == entry:
            return True

        folder = entry.rstrip("\\/")
        return path.startswith(folder + "\\")

    # ----------------------------------------------------------

    @staticmethod
    def matches(process="", exe_path="", title="", folders=None):
        # Совпадает ли окно/папка с каким-нибудь исключением.
        entries = IgnoreList.entries()
        if not entries:
            return False

        process = (process or "").strip().lower()
        exe_path = (exe_path or "").strip().lower()
        title = (title or "").strip().lower()
        folder_list = [
            (f or "").strip().lower()
            for f in (folders or [])
            if f
        ]

        for entry in entries:

            # Имя процесса или exe-файла — точное совпадение.
            if process and entry == process:
                return True

            if exe_path:
                if entry == os.path.basename(exe_path):
                    return True
                # Путь к файлу или папке-префиксу.
                if IgnoreList.path_matches(entry, exe_path):
                    return True

            # Часть заголовка окна (короткий мусор не ищем).
            if title and len(entry) >= 3 and entry in title:
                return True

            # Папка окна проводника.
            for folder in folder_list:
                if IgnoreList.path_matches(entry, folder):
                    return True

        return False
