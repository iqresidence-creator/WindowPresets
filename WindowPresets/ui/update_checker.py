from PySide6.QtCore import QThread, Signal


class UpdateCheckWorker(QThread):
    # --------------------------------------
    # Проверка обновлений В ФОНОВОМ потоке:
    # GitHub API бывает отвечает секундами — UI не должен замирать.
    # Общий для стартовой проверки (главное окно) и кнопки
    # «Проверить обновления» (настройки).
    #
    # Сигнал done(dict): {"tag", "url", "newer"} или {"error": str}.
    # --------------------------------------

    done = Signal(object)

    def run(self):

        from core import updater

        try:
            tag, url = updater.fetch_latest_release()
            self.done.emit(
                {
                    "tag": tag,
                    "url": url,
                    "newer": updater.is_newer(tag),
                }
            )
        except Exception as exc:
            self.done.emit({"error": str(exc)})
