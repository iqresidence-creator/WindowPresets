from datetime import datetime

from core.preset import Preset

from core.program_scanner import ProgramScanner
from core.folder_scanner import FolderScanner
from core.window_scanner import WindowScanner


class PresetBuilder:

    @staticmethod
    def build(name, exclude_hwnds=None):
        # exclude_hwnds — hwnd окна программы WindowPresets + консоли,
        # чтобы не сохранять само приложение в пресет.

        now = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        preset = Preset(

            name=name,

            created=now,

            updated=now,

        )

        preset.programs = ProgramScanner.scan()

        preset.folders = FolderScanner.scan()

        # 🔴 Карта hwnd→путь: каждое окно проводника узнает свой адрес.
        folder_map = FolderScanner.scan_hwnd_map()

        preset.windows = WindowScanner.scan(
            exclude_hwnds, folder_map=folder_map
        )

        # 🔴 Железно фиксируем число ПОДКЛЮЧЁННЫХ мониторов в момент
        # сохранения — независимо от количества окон, программ и того,
        # на каких мониторах они расположены. Та же нумерация, что
        # у индексов monitor у окон.
        preset.monitor_count = WindowScanner.monitor_count()

        return preset