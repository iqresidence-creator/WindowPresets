try:
    import win32gui
    import win32com.client
except Exception:
    win32gui = None


class FolderScanner:

    @staticmethod
    def scan():

        if win32gui is None:
            return []

        folders = set()

        try:
            shell = win32com.client.Dispatch("Shell.Application")
            windows = shell.Windows()
        except Exception:
            return []

        for window in windows:

            try:

                # только проводник
                if "explorer.exe" not in window.FullName.lower():
                    continue

                folder = window.Document.Folder

                if folder is None:
                    continue

                path = folder.Self.Path

                if not path:
                    continue

                # 🔴 «Этот компьютер», «Корзина» и виртуальные папки
                # имеют путь в виде GUID ::{...}. Сохраняем как есть —
                # иначе «Этот компьютер» никогда не попадал в список.
                if path.startswith("::{") or path.startswith("::"):
                    # Подменяем GUID на понятное имя для отображения.
                    try:
                        name = folder.Self.Name
                    except Exception:
                        name = path
                    folders.add(name)
                    continue

                folders.add(path)

            except Exception:
                pass

        return sorted(folders, key=str.lower)

    @staticmethod
    def scan_hwnd_map():
        # 🔴 Карта hwnd -> СПИСОК путей папок окна проводника.
        # В Win11 у окна есть вкладки: Shell.Windows() отдаёт ОТДЕЛЬНЫЙ
        # элемент на каждую вкладку (с общим HWND). Раньше путь
        # перезаписывался и все вкладки, кроме последней, терялись.
        # Первый элемент списка = активная вкладка (она же folder).
        result = {}

        if win32gui is None:
            return result

        try:
            shell = win32com.client.Dispatch("Shell.Application")
            windows = shell.Windows()
        except Exception:
            return result

        for window in windows:

            try:

                if "explorer.exe" not in window.FullName.lower():
                    continue

                folder = window.Document.Folder

                if folder is None:
                    continue

                path = folder.Self.Path

                if not path:
                    continue

                # Виртуальные папки («Этот компьютер» и т.п.) — по имени.
                if path.startswith("::"):
                    try:
                        path = folder.Self.Name
                    except Exception:
                        pass

                hwnd = int(window.HWND)
                result.setdefault(hwnd, []).append(path)

            except Exception:
                pass

        return result