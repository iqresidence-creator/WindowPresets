"""
WindowPresets
Version 0.1.0

Точка входа в программу.
"""

import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.app_icon import ensure_app_icon
from core.app_paths import base_dir
from core.app import App
from core.autostart import set_autostart
from core.single_instance import SingleInstance
from core.settings_manager import SettingsManager


def setup_logging():
    # 🔴 Диагностика загрузки пресетов: решения аплаера (пропуски,
    # потеря фокуса, несуществующие папки) раньше терялись — теперь
    # всё пишется в logs/app.log.
    logs_dir = base_dir() / "logs"
    logs_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        filename=str(logs_dir / "app.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )


def main():

    setup_logging()

    app = QApplication(sys.argv)

    # 🔴 Только один экземпляр программы: повторный запуск будит уже
    # запущенный ("raise" через QLocalServer/QLocalSocket) и тихо выходит.
    single_instance = SingleInstance()
    if not single_instance.acquire():
        sys.exit(0)

    # 🔴 Язык интерфейса — до создания окон: все тексты берутся
    # через core.i18n.tr() в момент построения.
    from core import i18n

    startup_cfg = SettingsManager.load()
    i18n.set_language(startup_cfg.get("language", "ru"))

    # 🔴 Автозапуск: если включён в настройках — восстанавливаем
    # запись в реестре (самовосстановление после сбоев/чистки).
    if startup_cfg.get("autostart"):
        set_autostart(True)

    # 🔴 Иконка программы: окно, таскбар, трей (трей берёт windowIcon).
    # Собирается автоматически из PNG в папке ico — достаточно
    # положить новую картинку и перезапустить программу.
    icon_path = ensure_app_icon()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    application = App()

    # 🔴 Подъём окна при повторном запуске: первый экземпляр получает
    # "raise" и показывает/поднимает окно (в том числе из трея).
    def raise_main_window():
        window = application.window
        window.showNormal()
        window.raise_()
        window.activateWindow()

    single_instance.set_raise_callback(raise_main_window)

    application.run()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()