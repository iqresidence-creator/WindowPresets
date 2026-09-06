from core.window_filters import WindowFilters
from core.window_scanner import WindowScanner


class ProgramScanner:

    @staticmethod
    def scan():

        # 🔴 Список процессов берём из общего снимка окон (collect_live),
        # чтобы «Программы» пресета и «Окна» видели одно и то же
        # (включая UWP-приложения за ApplicationFrameHost).

        programs = set()

        for entry in WindowScanner.collect_live():

            # 🔴 Сама программа WindowPresets не попадает в список.
            if entry["process"] in WindowFilters.SELF_PROCESSES:
                continue

            if entry["host_process"] in WindowFilters.SELF_PROCESSES:
                continue

            if WindowFilters.is_console_class(entry["hwnd"]):
                continue

            if entry["process"]:
                programs.add(entry["process"])

        return sorted(programs, key=str.lower)
