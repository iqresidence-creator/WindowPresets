from PySide6.QtCore import Qt

from core.settings_manager import SettingsManager

from ui.settings_dialog import SettingsDialog
from ui.preview_expander import PreviewExpander


class MainWindowController:

    @staticmethod
    def open_settings(window):

        dialog = SettingsDialog(window)

        result = dialog.exec()

        if result:

            # ⭐ загружаем новые настройки
            window.settings = SettingsManager.load()

            # ⭐ УДАЛЯЕМ старый expander
            if hasattr(window, "previewExpander"):
                window.previewExpander.deleteLater()

            # ⭐ СОЗДАЁМ НОВЫЙ (с новыми настройками)
            window.previewExpander = PreviewExpander(window)

            # ⭐ обновляем тему
            window.apply_theme(window.settings)

    # --------------------------------------------------

    @staticmethod
    def preset_changed(window):

        row = window.presetList.currentRow()

        if row < 0:
            window.currentPreset = None

            if hasattr(window, "previewManager"):
                window.previewManager.hide()

            return

        # 🔴 Пресет хранится в данных элемента: в списке есть
        # строки-заголовки групп («1 монитор», «Несколько
        # мониторов»), которые пресетами не являются.
        item = window.presetList.currentItem()
        preset = item.data(Qt.UserRole) if item is not None else None

        if preset is None:
            window.currentPreset = None

            if hasattr(window, "previewManager"):
                window.previewManager.hide()

            return

        # 🔴 РАЗДЕЛИТЕЛЬ: выбирается (чтобы его можно было удалить/
        # покрасить/перетащить), но превью у него нет и не будет.
        if getattr(preset, "is_separator", False):
            window.currentPreset = preset

            if hasattr(window, "previewManager"):
                window.previewManager.hide()

            return

        window.currentPreset = preset

        if hasattr(window, "previewManager"):
            rect = window.presetList.visualItemRect(item)
            if rect.isValid():
                # 🔴 Пресет ниже середины списка — текст сверху,
                # скриншот снизу.
                text_on_top = (
                    rect.center().y()
                    > window.presetList.viewport().height() // 2
                )
                window.previewManager.show(window.currentPreset, text_on_top)
            else:
                window.previewManager.show(window.currentPreset)
