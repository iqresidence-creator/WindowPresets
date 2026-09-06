from PySide6.QtCore import QObject, QEvent, Qt, QTimer, QRect
from PySide6.QtGui import QCursor


class PresetListController(QObject):

    def __init__(self, window):

        super().__init__(window)

        self.window = window
        self.list = window.presetList
        self.preview = window.previewManager.preview

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.check_hide)

        self.list.viewport().installEventFilter(self)
        self.preview.installEventFilter(self)

    # --------------------------------------

    def cursor_on_list(self, cursor):

        top_left = self.list.viewport().mapToGlobal(
            self.list.viewport().rect().topLeft()
        )

        rect = QRect(
            top_left,
            self.list.viewport().rect().size()
        )

        return rect.contains(cursor)

    # --------------------------------------

    def cursor_on_preview(self, cursor):

        if not self.preview.isVisible():
            return False

        return self.preview.frameGeometry().contains(cursor)

    # --------------------------------------

    def check_hide(self):

        cursor = QCursor.pos()

        if self.cursor_on_list(cursor):
            return

        if self.cursor_on_preview(cursor):
            return

        self.window.previewManager.hide()

        if hasattr(self.window, "statusBar"):
            from core.i18n import tr

            # Возврат в режим ожидания (зелёная заметка об
            # обновлении или «Готово»).
            if hasattr(self.window.statusBar, "set_idle"):
                self.window.statusBar.set_idle()
            else:
                self.window.statusBar.setText(tr("Готово", "status"))

    # --------------------------------------

    def show_preset_from_pos(self, pos):

        item = self.list.itemAt(pos)

        if item is None:
            # 🔴 Не скрываем мгновенно — курсор мог пройти
            # через пустой край списка. Даём таймеру шанс.
            self.timer.start(180)
            return

        # 🔴 Пресет хранится в данных элемента: в списке есть
        # строки-заголовки групп — они пресетами не являются.
        preset = item.data(Qt.UserRole)

        if preset is None:
            self.timer.start(180)
            return

        # 🔴 Разделитель — не превьюируется: это заголовок, а не
        # пресет. Реагируем как на пустое место (таймер скрытия).
        if getattr(preset, "is_separator", False):
            self.timer.start(180)
            return

        # 🔴 Останавливаем таймер скрытия — мы снова над валидным элементом.
        self.timer.stop()

        rect = self.list.visualItemRect(item)
        # 🔴 Пресет ниже середины списка — текст сверху, скриншот снизу.
        text_on_top = rect.center().y() > self.list.viewport().height() // 2
        self.window.previewManager.show(preset, text_on_top)

        if hasattr(self.window, "statusBar"):
            from core.i18n import tr

            self.window.statusBar.setText(
                tr("подсказка: наведи курсор на превью или нажми "
                   "выбранную клавишу")
            )

    # --------------------------------------

    def eventFilter(self, obj, event):

        # 🔴 При закрытии приложения C++ объекты Qt уже могут быть
        # удалены — не падаем, просто пропускаем событие.
        try:
            return self._handle_event(obj, event)
        except RuntimeError:
            return False

    # --------------------------------------

    def _handle_event(self, obj, event):

        if obj is self.list.viewport():

            if event.type() == QEvent.MouseMove:

                self.timer.stop()
                self.show_preset_from_pos(event.pos())
                return False

            if event.type() == QEvent.Leave:

                self.timer.start(120)
                return False

        if obj is self.preview:

            if event.type() == QEvent.Enter:

                self.timer.stop()
                return False

            if event.type() == QEvent.MouseMove:

                self.timer.stop()
                return False

            if event.type() == QEvent.Leave:

                self.timer.start(60)
                return False

        return False