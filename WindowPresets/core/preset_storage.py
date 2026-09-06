import copy as copy_module
import json
import os
import re
import shutil
from datetime import datetime

from core.app_paths import base_dir
from core.i18n import tr
from core.preset import Preset
from core.screenshot_manager import ScreenshotManager
from core.preset_builder import PresetBuilder
from core.preset_repository import PresetRepository


class PresetStorage:

    # 🔴 Абсолютные пути: у .exe данные лежат рядом с exe.
    FILE_NAME = str(base_dir() / "presets.json")
    PREVIEW_FOLDER = str(base_dir() / "previews")

    # --------------------------------------------------

    @classmethod
    def ensure_preview_folder(cls):

        os.makedirs(
            cls.PREVIEW_FOLDER,
            exist_ok=True
        )

    # --------------------------------------------------

    @classmethod
    def preview_path(cls, preset_name):

        cls.ensure_preview_folder()

        safe = re.sub(
            r'[\\/:*?"<>|]',
            "_",
            preset_name
        )

        return os.path.join(
            cls.PREVIEW_FOLDER,
            safe + ".png"
        )

    # --------------------------------------------------

    @classmethod
    def load(cls):

        cls.ensure_preview_folder()

        if not os.path.exists(cls.FILE_NAME):
            cls.save([])
            return []

        return PresetRepository.load(cls.FILE_NAME)

    # --------------------------------------------------

    @classmethod
    def save(cls, presets):

        cls.ensure_preview_folder()

        PresetRepository.save(
            cls.FILE_NAME,
            presets
        )

    # --------------------------------------------------

    @classmethod
    def new(cls, name=None, exclude_hwnds=None):

        # 🔴 Имя по умолчанию — на языке интерфейса на момент
        # создания; дальше это данные пользователя и не переводятся.
        if not name:
            name = tr("Новый пресет")

        presets = cls.load()

        original = name
        number = 1

        names = {
            p.name.lower()
            for p in presets
        }

        while name.lower() in names:
            number += 1
            name = f"{original} {number}"

        # ⭐ СОЗДАЁМ ПОЛНЫЙ ПРЕСЕТ
        preset = PresetBuilder.build(name, exclude_hwnds=exclude_hwnds)

        presets.append(preset)

        cls.save(presets)

        # ⭐ СКРИНШОТ
        path = cls.preview_path(preset.name)

        ScreenshotManager.save(path)

        preset.screenshot = path

        cls.save(presets)

        return preset

    # --------------------------------------------------

    @classmethod
    def duplicate(cls, name):
        # 🔴 Полная копия пресета: окна, папки, программы, теги,
        # скриншот — с новым уникальным именем «X (копия)».
        presets = cls.load()

        original = next(
            (p for p in presets if p.name == name), None
        )

        if original is None:
            return None

        new_preset = copy_module.deepcopy(original)

        base = original.name
        number = 1
        names = {p.name.lower() for p in presets}
        new_name = tr("{} (копия)").format(base)

        while new_name.lower() in names:
            number += 1
            new_name = tr("{} (копия {})").format(base, number)

        new_preset.name = new_name

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_preset.created = now
        new_preset.updated = now

        # 🔴 Копия встаёт СРАЗУ ЗА оригиналом (не в конец списка):
        # дублированное ищется глазами рядом с исходником.
        original_index = next(
            (i for i, p in enumerate(presets) if p.name == name), 0
        )
        presets.insert(original_index + 1, new_preset)
        cls.save(presets)

        old_image = cls.preview_path(original.name)
        new_image = cls.preview_path(new_name)

        if os.path.exists(old_image):
            try:
                shutil.copyfile(old_image, new_image)
                new_preset.screenshot = new_image
                cls.save(presets)
            except Exception:
                pass

        return new_preset

    # --------------------------------------------------

    @classmethod
    def add_separator(cls, after_name=None, name=None):
        # 🔴 Новый РАЗДЕЛИТЕЛЬ (пустой пресет-заголовок): вставляется
        # СРАЗУ ПОД пресетом after_name (или в конец списка), имя
        # уникализируется «Разделитель 2», «Разделитель 3»...
        if not name:
            name = tr("Разделитель")

        presets = cls.load()

        names = {p.name.lower() for p in presets}
        original = name
        number = 1

        while name.lower() in names:
            number += 1
            name = f"{original} {number}"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sep = Preset(
            name=name,
            created=now,
            updated=now,
            is_separator=True,
        )

        index = len(presets)

        if after_name is not None:
            for i, p in enumerate(presets):
                if p.name == after_name:
                    index = i + 1
                    break

        presets.insert(index, sep)
        cls.save(presets)

        return sep

    # --------------------------------------------------

    @classmethod
    def delete(cls, name):

        image = cls.preview_path(name)

        if os.path.exists(image):
            try:
                os.remove(image)
            except Exception:
                pass

        presets = [
            p for p in cls.load()
            if p.name != name
        ]

        cls.save(presets)

    # --------------------------------------------------

    @classmethod
    def rename(cls, old_name, new_name):

        presets = cls.load()

        names = {
            p.name.lower()
            for p in presets
        }

        if (
            new_name.lower() in names
            and old_name.lower() != new_name.lower()
        ):
            return False

        old_image = cls.preview_path(old_name)
        new_image = cls.preview_path(new_name)

        if os.path.exists(old_image):
            try:
                os.rename(old_image, new_image)
            except Exception:
                pass

        for preset in presets:

            if preset.name == old_name:

                preset.name = new_name

                preset.updated = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                break

        cls.save(presets)

        return True

    # --------------------------------------------------

    @classmethod
    def update_fields(cls, name, programs, folders, windows):
        # 🔴 Ручное редактирование состава («Настроить»): заменить
        # программы/папки/окна БЕЗ пересканирования живых окон.
        presets = cls.load()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for p in presets:
            if p.name == name:
                p.programs = list(programs)
                p.folders = list(folders)
                p.windows = list(windows)
                p.updated = now
                break

        cls.save(presets)

    # --------------------------------------------------

    @classmethod
    def get(cls, name):

        for preset in cls.load():
            if preset.name == name:
                return preset

        return None

    # --------------------------------------------------

    @classmethod
    def update(cls, preset, exclude_hwnds=None):

        presets = cls.load()

        for index, item in enumerate(presets):

            if item.name == preset.name:

                # ⭐ ПЕРЕСОЗДАЁМ ПРЕСЕТ
                new_preset = PresetBuilder.build(
                    preset.name, exclude_hwnds=exclude_hwnds
                )

                # 🔴 Пересоздание затирает поля, не относящиеся к окнам:
                # теги-вкладки и собственный цвет подложки переносим из
                # старого пресета (иначе «Обновить из текущих окон»
                # молча терял их).
                new_preset.tags = list(item.tags or [])
                new_preset.color = item.color or ""
                new_preset.is_separator = item.is_separator

                presets[index] = new_preset

                cls.save(presets)

                path = cls.preview_path(preset.name)

                ScreenshotManager.save(path)

                new_preset.screenshot = path

                cls.save(presets)

                return

        presets.append(preset)
        cls.save(presets)