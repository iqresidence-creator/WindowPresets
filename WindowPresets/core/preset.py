from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------
# Окно
# ---------------------------------------------------------

@dataclass
class WindowInfo:

    title: str = ""
    process: str = ""

    # 🔴 Полный путь к exe (для надёжного запуска программ,
    # которые не находятся простым os.startfile имени).
    exe_path: str = ""

    # 🔴 Адрес папки для окон проводника — при загрузке
    # открывается именно этот путь, а не «Мой компьютер».
    folder: str = ""

    # 🔴 Все вкладки окна проводника (Win11). folder = первая вкладка.
    tabs: List[str] = field(default_factory=list)

    # 🔴 AUMID приложения (UWP/Store) — надёжный запуск через
    # shell:AppsFolder\<aumid>. Пусто для обычных программ.
    aumid: str = ""

    x: int = 0
    y: int = 0

    width: int = 0
    height: int = 0

    monitor: int = 0

    maximized: bool = False
    minimized: bool = False

    def to_dict(self):

        return {

            "title": self.title,
            "process": self.process,
            "exe_path": self.exe_path,
            "folder": self.folder,
            "tabs": list(self.tabs),
            "aumid": self.aumid,

            "x": self.x,
            "y": self.y,

            "width": self.width,
            "height": self.height,

            "monitor": self.monitor,

            "maximized": self.maximized,
            "minimized": self.minimized,

        }

    @classmethod
    def from_dict(cls, data):

        return cls(

            title=data.get("title", ""),
            process=data.get("process", ""),
            exe_path=data.get("exe_path", ""),
            folder=data.get("folder", ""),
            tabs=list(data.get("tabs", [])),
            aumid=data.get("aumid", ""),

            x=data.get("x", 0),
            y=data.get("y", 0),

            width=data.get("width", 0),
            height=data.get("height", 0),

            monitor=data.get("monitor", 0),

            maximized=data.get("maximized", False),
            minimized=data.get("minimized", False),

        )


# ---------------------------------------------------------
# Пресет
# ---------------------------------------------------------

@dataclass
class Preset:

    name: str

    windows: List[WindowInfo] = field(default_factory=list)

    programs: List[str] = field(default_factory=list)

    folders: List[str] = field(default_factory=list)

    created: str = ""

    updated: str = ""

    screenshot: str = ""

    # 🔴 Вкладки-теги, к которым привязан пресет (система фильтров:
    # вкладка показывает только пресеты с её тегом).
    tags: List[str] = field(default_factory=list)

    # 🔴 Собственный цвет пресета: подложка под названием в списке.
    # Независим от цветов вкладок, хранится В ПРЕСЕТЕ (hex, "" — нет).
    color: str = ""

    # 🔴 РАЗДЕЛИТЕЛЬ: «пустой пресет»-заголовок для визуальной
    # каталогизации. Ничего не отображает/не загружает, превью и
    # инфы нет; ведёт себя как строка списка (цвет, drag, копия,
    # удаление). Участвует в общем порядке presets.json и виден
    # во ВСЕХ вкладках.
    is_separator: bool = False

    # 🔴 Число мониторов, подключённых В МОМЕНТ СОХРАНЕНИЯ пресета —
    # железно фиксируется при создании/обновлении независимо от того,
    # сколько окон сохранено и на каких мониторах они находились.
    monitor_count: int = 0

    # -----------------------------------------------------

    @property
    def program_count(self):

        return len(self.programs)

    # -----------------------------------------------------

    @property
    def folder_count(self):

        return len(self.folders)

    # -----------------------------------------------------

    def to_dict(self):

        return {

            "name": self.name,

            "created": self.created,
            "updated": self.updated,

            "screenshot": self.screenshot,

            "tags": list(self.tags),

            "color": self.color,

            "is_separator": self.is_separator,

            "monitor_count": self.monitor_count,

            "programs": self.programs,

            "folders": self.folders,

            "windows": [

                window.to_dict()

                for window in self.windows

            ],

        }

    # -----------------------------------------------------

    @classmethod
    def from_dict(cls, data):

        preset = cls(

            name=data.get(

                "name",

                "Preset"

            )

        )

        preset.created = data.get(

            "created",

            ""

        )

        preset.updated = data.get(

            "updated",

            ""

        )

        preset.screenshot = data.get(

            "screenshot",

            ""

        )

        preset.programs = list(

            data.get(

                "programs",

                []

            )

        )

        preset.folders = list(

            data.get(

                "folders",

                []

            )

        )

        preset.windows = [

            WindowInfo.from_dict(item)

            for item in data.get(

                "windows",

                []

            )

        ]

        # 🔴 Вкладки-теги пресета (старые пресеты без поля — без тегов).
        preset.tags = [
            str(t) for t in (data.get("tags") or []) if str(t).strip()
        ]

        # 🔴 Собственный цвет подложки (старые пресеты — без цвета).
        preset.color = str(data.get("color") or "")

        # 🔴 Разделитель (старые пресеты — не разделители).
        preset.is_separator = bool(data.get("is_separator"))

        # 🔴 Число мониторов, зафиксированное при сохранении.
        # Старые пресеты без поля — миграция: считаем по окнам.
        saved_monitors = data.get("monitor_count")

        if saved_monitors is None:
            saved_monitors = len({w.monitor for w in preset.windows})

        preset.monitor_count = int(saved_monitors)

        return preset