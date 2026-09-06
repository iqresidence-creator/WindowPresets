from core.settings_manager import SettingsManager
from core.autostart import set_autostart


class SettingsApply:

    @staticmethod
    def apply(dialog):

        s = SettingsManager.load()

        # 🔴 Язык интерфейса: сравниваем со СТАРЫМ значением —
        # при смене переводим главное окно на лету и окно
        # настроек открываем заново (оно строится из tr()-строк).
        old_language = s.get("language", "ru")
        new_language = (
            "en"
            if dialog.languageGroup.combo.currentIndex() == 1
            else "ru"
        )
        s["language"] = new_language

        # ---------- Главное окно ----------

        # 🔴 Цвета под тему Windows: при включении яркости берутся
        # из системы, бегунки яркости игнорируются.
        s["use_system_color"] = (
            dialog.windowGroup.useSystemColor.isChecked()
        )

        if s["use_system_color"]:
            from core.system_theme import system_colors

            s.update(system_colors())

        # 🔴 Автозапуск: настройка + синхронизация реестра Windows.
        s["autostart"] = (
            dialog.windowGroup.autostart.isChecked()
        )
        set_autostart(s["autostart"])

        s["window_color"] = (
            dialog.windowGroup.windowBrightness.value()
        )

        # 🔴 «Поверх всех окон»: применяется к живому окну сразу.
        s["window_on_top"] = (
            dialog.windowGroup.windowOnTop.isChecked()
        )
        dialog.window.set_always_on_top(s["window_on_top"])

        s["list_color"] = (
            dialog.windowGroup.listBrightness.value()
        )

        # 🔴 Прозрачность подложек пресетов/разделителей, %.
        s["preset_color_opacity"] = (
            dialog.windowGroup.colorOpacity.value()
        )
        delegate = dialog.window.presetList.itemDelegate()
        if delegate is not None:
            delegate.colorOpacity = s["preset_color_opacity"]
        dialog.window.load_presets()

        s["button_style"] = (
            "icons"
            if dialog.windowGroup.iconButtons.isChecked()
            else "text"
        )

        # ---------- Иконки ----------
        # 🔴 Настроек иконок две: яркость и размер. Обе действуют
        # сразу на нижние кнопки и кнопки вкладок (верхние —
        # 70% размера нижних). Пак иконок единственный; ключи
        # эпохи паков/прозрачности/пиксель-режима вычищаем из
        # config.json.
        s["icon_brightness"] = (
            dialog.iconsGroup.brightness.value()
        )

        s["icon_scale"] = (
            dialog.iconsGroup.scale.value() / 100.0
        )

        s.pop("icon_pack", None)
        s.pop("icon_opacity", None)
        s.pop("pixel_mode", None)

        # ---------- Превью ----------

        s["preview_size"] = (
            dialog.previewGroup.size.value()
        )

        s["preview_dim"] = (
            dialog.previewGroup.dim.value()
        )

        s["preview_text_size"] = (
            dialog.previewGroup.textSize.value()
        )

        s["preview_panel_alpha"] = (
            dialog.previewGroup.panelOpacity.value()
        )

        # ⭐ Клавиша просмотра превью — всегда ПРОБЕЛ (зашита в коде).
        # Старый ключ выбора CTRL/SHIFT/ALT вычищаем из config.json.
        s.pop("preview_key", None)

        # ---------- Поведение ----------

        s["show_preview"] = (
            dialog.behaviorGroup.showPreview.isChecked()
        )

        s["minimize_to_tray"] = (
            dialog.behaviorGroup.minimizeToTray.isChecked()
        )

        # Устаревший ключ старой галочки «Увеличивать по CTRL» — вычищаем.
        s.pop("preview_ctrl", None)

        s["remember_window_position"] = (
            dialog.behaviorGroup.rememberPosition.isChecked()
        )

        # ---------- Пути запуска ----------

        if hasattr(dialog, "launchGroup"):
            s["launch_paths"] = dialog.launchGroup.values()

        # ---------- Исключения ----------

        if hasattr(dialog, "ignoreGroup"):
            s["ignore_list"] = dialog.ignoreGroup.values()

        # ---------- Пасхалка ----------

        s["cowabunga"] = (
            dialog.easterGroup.cowabunga.isChecked()
        )

        SettingsManager.save(s)

        dialog.window.settings = s
        dialog.window.apply_theme(s)

        # 🔴 Смена языка: глобальный tr() переключается ДО
        # перевода окна; окно настроек пересоздаётся (его тексты
        # читаются при построении), скролл сохраняется на окне.
        if new_language != old_language:
            from core import i18n

            i18n.set_language(new_language)
            dialog.window._retranslate_ui()

            from PySide6.QtCore import QTimer

            QTimer.singleShot(
                0,
                lambda: (
                    dialog.accept(),
                    dialog.window.open_settings(),
                ),
            )
