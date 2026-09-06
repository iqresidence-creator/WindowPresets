"""
WindowPresets
Version 0.1.0

🔴 Защита от запуска второго экземпляра программы.

Первый запуск становится «владельцем» локального сервера
(QLocalServer) с фиксированным именем. Повторный запуск подключается
к нему клиентом (QLocalSocket), отправляет "raise" и тихо выходит —
владелец по этому сообщению показывает и поднимает главное окно
(в том числе из трея).
"""

import logging

from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "WindowPresetsSingleInstance"

_RAISE_MESSAGE = b"raise\n"

_CONNECT_TIMEOUT_MS = 500
_WRITE_TIMEOUT_MS = 1000

logger = logging.getLogger(__name__)


class SingleInstance:
    """Не даёт запустить программу дважды.

    Использование:

        single = SingleInstance()
        if not single.acquire():
            sys.exit(0)          # мы второй экземпляр — выходим

        application = App()
        single.set_raise_callback(...)   # колбэк можно задать позже
    """

    def __init__(self):

        self._server = None
        self._raise_callback = None

        # 🔅 Запрос "raise" может прийти ДО того, как main.py создаст
        # окно и передаст колбэк — тогда запоминаем его и выполняем
        # при подключении колбэка.
        self._pending_raise = False

        # 🔅 Держим ссылки на клиентские сокеты: пока сокет жив,
        # Qt не порвёт соединение раньше, чем мы прочитаем "raise".
        self._clients = []


    def acquire(self) -> bool:
        """Пытаемся стать единственным экземпляром.

        True  — мы первый экземпляр, сервер слушает, продолжаем запуск.
        False — экземпляр уже жив (или имя занято), надо выйти.
        """

        probe = QLocalSocket()
        probe.connectToServer(SERVER_NAME)

        if probe.waitForConnected(_CONNECT_TIMEOUT_MS):
            probe.write(_RAISE_MESSAGE)
            probe.waitForBytesWritten(_WRITE_TIMEOUT_MS)
            probe.disconnectFromServer()
            logger.info(
                "второй экземпляр — активируем существующий и выходим"
            )
            return False

        # Подключения нет: либо программа не запущена, либо от прошлого
        # падения остался мусор. removeServer() лечит мусор (на Windows
        # почти no-op, на Unix удаляет файл сокета), затем слушаем сами.
        QLocalServer.removeServer(SERVER_NAME)

        self._server = QLocalServer()
        if not self._server.listen(SERVER_NAME):
            # 🔴 Имя занято, но подключиться не вышло (например, два
            # запуска одновременно гонятся за именем). Гарантия «ровно
            # один экземпляр» важнее запуска — выходим.
            logger.error(
                "не удалось занять имя единственного экземпляра (%s), "
                "выходим",
                self._server.errorString(),
            )
            self._server = None
            return False

        self._server.newConnection.connect(self._on_new_connection)
        return True


    def set_raise_callback(self, callback):
        """Задаёт функцию, поднимающую главное окно.

        Модуль ничего не знает о MainWindow — функцию передаёт main.py.
        Если "raise" уже успел прийти до этого вызова, колбэк
        выполняется немедленно.
        """

        self._raise_callback = callback

        if self._pending_raise:
            self._pending_raise = False
            self._call_raise_callback()


    def _on_new_connection(self):

        while self._server is not None and self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            self._clients.append(client)
            client.readyRead.connect(
                lambda socket=client: self._on_ready_read(socket)
            )
            client.disconnected.connect(
                lambda socket=client: self._on_disconnected(socket)
            )


    def _on_ready_read(self, socket):

        data = bytes(socket.readAll())
        if b"raise" in data:
            self._call_raise_callback()
            socket.disconnectFromServer()


    def _on_disconnected(self, socket):

        if socket in self._clients:
            self._clients.remove(socket)


    def _call_raise_callback(self):

        if self._raise_callback is None:
            # Окна ещё нет (запуск в процессе) — поднять позже.
            self._pending_raise = True
            return

        try:
            self._raise_callback()
        except Exception:
            # 🔴 Ошибка в колбэке не должна ронять владельца сервера.
            logger.exception("не удалось поднять окно по 'raise'")
