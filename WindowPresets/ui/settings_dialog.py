from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QScrollArea,
    QWidget,
)

from core.settings_manager import SettingsManager
from core.i18n import tr

from ui.settings.language_group import SettingsLanguageGroup
from ui.settings.window_group import SettingsWindowGroup
from ui.settings.icons_group import SettingsIconsGroup
from ui.settings.preview_group import SettingsPreviewGroup
from ui.settings.behavior_group import SettingsBehaviorGroup
from ui.settings.launch_group import SettingsLaunchGroup
from ui.settings.ignore_group import SettingsIgnoreGroup
from ui.settings.easter_group import SettingsEasterGroup

from ui.settings.apply import SettingsApply
from ui.update_checker import UpdateCheckWorker


class SettingsDialog(QDialog):

    def __init__(self, parent):

        super().__init__(parent)

        self.window = parent

        self.settings = SettingsManager.load()

        self.setWindowTitle(tr("Настройки"))

        self.setFixedSize(370, 640)

        self.mainLayout = QVBoxLayout(self)

        self.mainLayout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        self.mainLayout.setSpacing(8)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        # Store scroll position on the parent window so it survives reopen.
        self._scroll_position = getattr(
            self.window,
            "_settings_scroll_position",
            0,
        )

        self.scrollWidget = QWidget()

        self.scrollLayout = QVBoxLayout(self.scrollWidget)
        self.scrollLayout.setSpacing(8)

        # 🔴 Проверка обновлений — САМАЯ ПЕРВАЯ в настройках
        # (просьба владельца), с серой рамкой как у кнопок
        # диалоговых окон — чтобы было видно, что это кнопка.
        from core.updater import APP_VERSION

        self.updateButton = QPushButton(
            tr("Проверить обновления (v{})").format(APP_VERSION)
        )
        self.updateButton.setMinimumHeight(36)
        self.updateButton.clicked.connect(self._check_updates)
        self._apply_update_button_base_style()
        self.scrollLayout.addWidget(self.updateButton)

        # 🔴 Зелёная плашка: обновление уже найдено при старте
        # (автопроверка главного окна).
        startup_tag = getattr(self.window, "update_tag", None)
        if startup_tag:
            self._mark_update_button(startup_tag)

        self.languageGroup = SettingsLanguageGroup(self.settings)
        self.windowGroup = SettingsWindowGroup(self.settings)
        self.iconsGroup = SettingsIconsGroup(self.settings)
        self.previewGroup = SettingsPreviewGroup(self.settings)
        self.behaviorGroup = SettingsBehaviorGroup(self.settings)
        self.launchGroup = SettingsLaunchGroup(self.settings)
        self.ignoreGroup = SettingsIgnoreGroup(self.settings)
        self.easterGroup = SettingsEasterGroup(self.settings)

        self.scrollLayout.addWidget(self.languageGroup)
        self.scrollLayout.addWidget(self.windowGroup)
        self.scrollLayout.addWidget(self.iconsGroup)
        self.scrollLayout.addWidget(self.previewGroup)
        self.scrollLayout.addWidget(self.behaviorGroup)
        self.scrollLayout.addWidget(self.launchGroup)
        self.scrollLayout.addWidget(self.ignoreGroup)
        self.scrollLayout.addWidget(self.easterGroup)
        self.scrollLayout.addStretch()

        # 🔴 Блок автора со ссылками — в самом низу настроек.
        # Ссылки открываются в браузере кликом (openExternalLinks).
        self.creditsLabel = QLabel(
            "Author: NickMoor<br>"
            "<br>"
            "Instagram: "
            "<a href=\"https://www.instagram.com/artmuravich\">"
            "artmuravich</a><br>"
            "Telegram: "
            "<a href=\"https://t.me/MuravichArt\">MuravichArt</a><br>"
            "ArtStation: "
            "<a href=\"https://www.artstation.com/muraga\">muraga</a><br>"
            "YouTube: "
            "<a href=\"https://www.youtube.com/@nikitamuravich4601\">"
            "nikitamuravich4601</a><br>"
            "SoundCloud: "
            "<a href=\"https://soundcloud.com/iqres\">iqres</a><br>"
            "<br>"
            "Email: "
            "<a href=\"mailto:iqresidence@gmail.com\">"
            "iqresidence@gmail.com</a><br>"
            "<br>"
            "Support: "
            "<a href=\"https://boosty.to/artmuravich/donate\">"
            "boosty.to/artmuravich/donate</a><br>"
            "<br>"
            "THANK YOU!<br>"
            "2026"
        )
        self.creditsLabel.setTextFormat(Qt.TextFormat.RichText)
        self.creditsLabel.setOpenExternalLinks(True)
        self.creditsLabel.setWordWrap(True)
        self.creditsLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.creditsLabel.setStyleSheet(
            "color: rgb(150, 150, 150);"
            "font-size: 9pt;"
            "background: transparent;"
            "border: none;"
        )
        self.scrollLayout.addWidget(self.creditsLabel)

        self.scroll.setWidget(self.scrollWidget)
        self.scroll.verticalScrollBar().valueChanged.connect(
            self._save_scroll_position
        )

        self.mainLayout.addWidget(self.scroll)

        # 🔴 Высота как у кнопки обновлений (36) — без этого кнопка
        # выходит неоправданно плоской.
        self.closeButton = QPushButton(tr("Закрыть"))
        self.closeButton.setMinimumHeight(36)
        self.mainLayout.addWidget(self.closeButton)

        self.connect_controls()
        self.apply()

    # ----------------------------------------------------------

    def _apply_update_button_base_style(self):
        # Серая рамка — как у кнопок диалоговых окон: видно,
        # что это кнопка (без стиля она сливается с фоном).
        self.updateButton.setStyleSheet("""
QPushButton {
    background: rgb(75, 75, 75);
    color: rgb(230, 230, 230);
    border: 1px solid rgb(110, 110, 110);
    border-radius: 6px;
    padding: 6px 12px;
}

QPushButton:hover {
    background: rgb(90, 90, 90);
    border: 1px solid rgb(130, 130, 130);
}

QPushButton:pressed {
    background: rgb(100, 100, 100);
}
""")

    # --------------------------------------------------

    def _check_updates(self):

        # 🔴 Сеть — в QThread: UI не замирает (гвоздь программы —
        # GitHub API бывает отвечает секундами). Воркер общий
        # со стартовой автопроверкой (ui/update_checker.py).
        self.updateButton.setText(tr("Проверяю..."))
        self.updateButton.setEnabled(False)
        self._apply_update_button_base_style()

        self._check_worker = UpdateCheckWorker()
        self._check_worker.done.connect(self._on_check_done)
        self._check_worker.start()

    # --------------------------------------------------

    def _mark_update_button(self, tag):
        # 🔴 Зелёная плашка на кнопке: новая версия найдена
        # (просьба владельца).

        self.updateButton.setText(
            tr("Есть новая версия «{}»").format(tag)
        )
        self.updateButton.setStyleSheet("""
QPushButton {
    background: rgb(46, 125, 50);
    color: rgb(255, 255, 255);
    border: 1px solid rgb(67, 160, 71);
    border-radius: 6px;
}

QPushButton:hover {
    background: rgb(56, 142, 60);
}

QPushButton:pressed {
    background: rgb(67, 160, 71);
}
""")

    # --------------------------------------------------

    def _on_check_done(self, result):

        from ui.confirm_dialog import ConfirmDialog

        self.updateButton.setEnabled(True)

        if "error" in result:
            self.updateButton.setText(tr("Обновления: нет связи"))
            QTimer.singleShot(
                4000,
                lambda: self._reset_update_button(),
            )
            return

        if not result["newer"]:
            # 🔴 Обновления нет: гасим и заметку в статусе главного
            # окна (например, найденная при старте устарела).
            if hasattr(self.window, "update_tag"):
                self.window.update_tag = None
            if hasattr(self.window.statusBar, "clear_update_tag"):
                self.window.statusBar.clear_update_tag()
            self.updateButton.setText(
                tr("У вас последняя версия ({})").format(result["tag"])
            )
            QTimer.singleShot(
                4000,
                lambda: self._reset_update_button(),
            )
            return

        # 🔴 Найдено: зелёная плашка и в настройках, и в статусе
        # главного окна (как при стартовой автопроверке).
        self._mark_update_button(result["tag"])
        if hasattr(self.window, "mark_update_available"):
            self.window.mark_update_available(result["tag"])

        answer = ConfirmDialog(
            self,
            tr("Обновление"),
            tr("Доступна версия {}. Скачать и установить?")
            .format(result["tag"]),
            yes_text=tr("Обновить"),
            no_text=tr("Позже"),
        ).exec()

        if answer != QDialog.DialogCode.Accepted:
            # 🔴 «Позже»: плашка ОСТАЁТСЯ зелёной — обновление всё
            # ещё доступно (гаснет только после установки или
            # когда проверка покажет «последняя версия»).
            if not getattr(self.window, "update_tag", None):
                self._reset_update_button()
            return

        self._download_update(result["url"])

    # ----------------------------------------------------------

    def _download_update(self, url):

        from core import updater

        self.updateButton.setText(tr("Скачиваю... 0%"))
        self.updateButton.setEnabled(False)

        self._download_url = url

        class DownloadWorker(QThread):
            progress = Signal(float)
            done = Signal(object)

            def run(self):
                import os
                import tempfile

                dest = os.path.join(
                    tempfile.gettempdir(),
                    "WindowPresets_update.zip",
                )
                try:
                    updater.download(
                        url,
                        dest,
                        progress=self.progress.emit,
                    )
                    self.done.emit({"zip": dest})
                except Exception as exc:
                    self.done.emit({"error": str(exc)})

        self._download_worker = DownloadWorker()
        self._download_worker.progress.connect(
            lambda p: self.updateButton.setText(
                tr("Скачиваю... {}%").format(int(p * 100))
            )
        )
        self._download_worker.done.connect(self._on_download_done)
        self._download_worker.start()

    # ----------------------------------------------------------

    def _on_download_done(self, result):

        from ui.confirm_dialog import ConfirmDialog

        self.updateButton.setEnabled(True)

        if "error" in result:
            self.updateButton.setText(tr("Ошибка скачивания"))
            QTimer.singleShot(4000, self._reset_update_button)
            return

        from core import updater
        import sys

        if not getattr(sys, "frozen", False):
            # 🔴 Запуск из исходников: exe-обновление не применимо.
            self.updateButton.setText(tr("Обновление скачано (исходники)"))
            self._reset_update_button(6000)
            return

        try:
            bat = updater.prepare_exe_update(result["zip"])
        except Exception as exc:
            self.updateButton.setText(tr("Ошибка: {}").format(exc))
            QTimer.singleShot(5000, self._reset_update_button)
            return

        answer = ConfirmDialog(
            self,
            tr("Готово"),
            tr("Обновление готово. Программа закроется, "
               "заменит exe и запустится сама."),
            yes_text=tr("Установить"),
            no_text=tr("Отмена"),
        ).exec()

        if answer != QDialog.DialogCode.Accepted:
            self._reset_update_button()
            return

        updater.launch_apply_script(bat)

        # Программа закроется — апдейтер подхватит подмену exe.
        self.window._force_quit = True
        self.window.close()

    # ----------------------------------------------------------

    def _reset_update_button(self, delay=0):

        def reset():
            from core.updater import APP_VERSION

            # Серая рамка вместо зелёной плашки (заметка в
            # статусе главного окна живёт отдельно).
            self._apply_update_button_base_style()
            self.updateButton.setText(
                tr("Проверить обновления (v{})").format(APP_VERSION)
            )

        if delay:
            QTimer.singleShot(delay, reset)
        else:
            reset()

    # ----------------------------------------------------------

    def connect_controls(self):

        controls = [
            self.windowGroup.windowBrightness.slider,
            self.windowGroup.listBrightness.slider,
            self.iconsGroup.scale.slider,
            self.iconsGroup.brightness.slider,
            self.previewGroup.size.slider,
            self.previewGroup.dim.slider,
        ]

        for control in controls:
            control.valueChanged.connect(self.apply)

        # 🔴 Смена языка: apply() пересоберёт окно настроек заново.
        self.languageGroup.combo.currentIndexChanged.connect(self.apply)
        self.windowGroup.autostart.toggled.connect(self.apply)
        self.behaviorGroup.showPreview.toggled.connect(self.apply)
        self.behaviorGroup.minimizeToTray.toggled.connect(self.apply)
        self.behaviorGroup.rememberPosition.toggled.connect(self.apply)
        self.windowGroup.iconButtons.toggled.connect(self.apply)
        self.launchGroup.changed.connect(self.apply)
        self.ignoreGroup.changed.connect(self.apply)

        self.easterGroup.cowabunga.toggled.connect(self.apply)

        # 🔴 Клавиша просмотра — всегда ПРОБЕЛ (раньше был SHIFT), выбор CTRL/ALT удалён.

        self.closeButton.clicked.connect(self.close_dialog)

    # ----------------------------------------------------------

    def apply(self):

        SettingsApply.apply(self)

    # ----------------------------------------------------------

    def _save_scroll_position(self, value=None):

        if value is None:
            value = self.scroll.verticalScrollBar().value()

        self._scroll_position = value
        self.window._settings_scroll_position = value

    # ----------------------------------------------------------

    def close_dialog(self):

        self._save_scroll_position()
        self.apply()
        self.accept()

    # ----------------------------------------------------------

    def showEvent(self, event):

        super().showEvent(event)

        if self.window is None:
            return

        parentGeometry = self.window.frameGeometry()
        dialogGeometry = self.frameGeometry()

        x = parentGeometry.right() + 6
        y = parentGeometry.top()

        screen = self.screen().availableGeometry()

        if x + dialogGeometry.width() > screen.right():
            x = parentGeometry.left() - dialogGeometry.width() - 6

        if y + dialogGeometry.height() > screen.bottom():
            y = screen.bottom() - dialogGeometry.height()

        self.move(x, y)

        # Restore scroll after the layout is settled.
        QTimer.singleShot(
            0,
            lambda: self.scroll.verticalScrollBar().setValue(
                self._scroll_position
            ),
        )
