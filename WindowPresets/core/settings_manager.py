import json
import os


class SettingsManager:

    FILE_NAME = "config.json"

    DEFAULTS = {

        # Цвет окна
        "window_color": 185,

        # Цвет списка пресетов
        "list_color": 215,

        # Цвет иконок
        "icon_color": 100,

        # Масштаб иконок
        "icon_scale": 1.00,

        # Набор иконок
        "icon_pack": 1,

        # Pixel Art режим
        "pixel_mode": False

    }

    # -------------------------------------------------------------

    @classmethod
    def load(cls):

        if not os.path.exists(cls.FILE_NAME):

            cls.save(cls.DEFAULTS.copy())

            return cls.DEFAULTS.copy()

        try:

            with open(
                cls.FILE_NAME,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            settings = cls.DEFAULTS.copy()

            settings.update(data)

            return settings

        except Exception:

            cls.save(cls.DEFAULTS.copy())

            return cls.DEFAULTS.copy()

    # -------------------------------------------------------------

    @classmethod
    def save(cls, settings):

        with open(
            cls.FILE_NAME,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                settings,
                file,
                indent=4,
                ensure_ascii=False
            )