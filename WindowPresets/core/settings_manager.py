import json
import os

from core.app_paths import base_dir


class SettingsManager:

    # 🔴 Абсолютный путь: у .exe данные лежат рядом с exe,
    # запуск не из папки проекта ничего не ломает.
    FILE_NAME = str(base_dir() / "config.json")

    DEFAULTS = {

        # ---------- Интерфейс ----------

        # Язык интерфейса: "ru" / "en" (выбор в настройках).
        "language": "ru",

        "window_color": 185,
        "list_color": 215,

        # Кнопки вкладок: "icons" (символы) или "text" (подписи).
        "button_style": "icons",

        # Автозапуск при старте Windows (реестр HKCU Run).
        "autostart": False,

        # Главное окно поверх всех окон (иначе обычный z-порядок).
        "window_on_top": True,

        # Цвета программы — под цветовую тему Windows.
        "use_system_color": False,

        # Прозрачность цветовых подложек пресетов/разделителей, %.
        "preset_color_opacity": 100,

        # Репозиторий GitHub для «Проверить обновления».
        "update_repo": "iqresidence-creator/Window-Manager",

        # ---------- Иконки ----------
        # Пак иконок ЕДИНСТВЕННЫЙ (assets/icons/pack_5) — настройки
        # паков/прозрачности/пиксель-режима удалены. Настроек две:
        # яркость и размер; обе действуют сразу на нижние кнопки
        # и кнопки вкладок (верхние — 70% размера нижних).

        "icon_color": 100,

        "icon_scale": 1.00,

        "icon_brightness": 50,

        # ---------- Пресеты ----------

        "last_preset": "",

        "double_click_edit": True,

        "auto_save": True,

        # ---------- Превью ----------

        "preview_size": 320,

        "preview_dim": 15,

        "preview_panel_alpha": 40,

        "preview_text_size": 18,

        "show_preview": True,

        # ---------- Пасхалка ----------

        "cowabunga": False,

        # ---------- Окно ----------

        "start_minimized": False,

        "minimize_to_tray": False,

        # ---------- Пути запуска ----------
        # {имя_процесса.lower(): путь к файлу запуска (.exe/.vbs/.bat/...)}
        # Ручное указание для программ, которые открываются неправильно
        # (например, скрипты в песочнице Sandboxie).

        "launch_paths": {},

        # ---------- Исключения ----------
        # [строка: имя процесса / путь к файлу / папка / часть заголовка]
        # Эти окна полностью игнорируются: не сохраняются в пресет,
        # не открываются и не закрываются.

        "ignore_list": [],

        # ---------- Вкладки-фильтры пресетов ----------
        # [имена вкладок]. Вкладка показывает только пресеты, которым
        # назначен её тег. Вкладка «Все» встроена и не хранится.

        "preset_tabs": [],

        # ---------- Цвета вкладок ----------
        # {имя вкладки: "#rrggbb"}. Без записи в словаре вкладка
        # рисуется в цвете по умолчанию.

        "tab_colors": {},

        # ---------- Окно ----------

        "window_height": 330,

    }

    # ---------------------------------------------------------

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

        except Exception:

            data = {}

        settings = cls.DEFAULTS.copy()

        settings.update(data)

        changed = False

        for key, value in cls.DEFAULTS.items():

            if key not in settings:

                settings[key] = value

                changed = True

        if changed:

            cls.save(settings)

        return settings

    # ---------------------------------------------------------

    @classmethod
    def save(cls, settings):

        data = cls.DEFAULTS.copy()

        data.update(settings)

        with open(
            cls.FILE_NAME,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(

                data,

                file,

                indent=4,

                ensure_ascii=False

            )
