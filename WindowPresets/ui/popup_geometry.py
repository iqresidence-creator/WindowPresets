from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QApplication

# 🔴 ЖЕЛЕЗНОЕ ПРАВИЛО ГЕОМЕТРИИ: любое окно программы (popup,
# контекстное меню, диалог) открывается ЦЕЛИКОМ в пределах
# монитора — не уезжает за края ни вниз, ни вверх. Если содержимому
# нужно больше места, чем есть на экране, — окно занимает всю
# доступную высоту, а содержимое листается внутренним скроллом
# (списки уже скроллятся, QMenu скроллится сам).

MARGIN = 8


def screen_geometry(pos):
    # Экран под точкой (мультимонитор); если точка вне экранов —
    # основной. availableGeometry учитывает панель задач.
    screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
    return screen.availableGeometry()


def clamp_point_within_screen(pos, size):
    # Точка для окна/меня размером size (QSize), сдвинутая так,
    # чтобы окно целиком осталось на экране. Использовать ПЕРЕД
    # menu.exec() / dialog.move().
    avail = screen_geometry(pos)
    if isinstance(size, QSize):
        w, h = size.width(), size.height()
    else:
        w, h = size

    x = max(
        avail.left() + MARGIN,
        min(pos.x(), avail.right() + 1 - w - MARGIN),
    )
    y = max(
        avail.top() + MARGIN,
        min(pos.y(), avail.bottom() + 1 - h - MARGIN),
    )
    return QPoint(x, y)


def fit_height_within_screen(pos, needed_height, min_height=120):
    # Пара (y, height) для окна, открывающегося ВНИЗ от точки pos:
    # высота — сколько нужно (needed_height), но не больше экрана;
    # если внизу места не хватает — окно РАСТЁТ ВВЕРХ (низ прижат
    # к краю экрана, верх ограничен экраном), дальше — внутренний
    # скролл содержимого.
    avail = screen_geometry(pos)
    max_height = avail.height() - 2 * MARGIN
    height = max(min_height, min(needed_height, max_height))

    y = pos.y()
    if y + height > avail.bottom() + 1 - MARGIN:
        y = max(
            avail.top() + MARGIN,
            avail.bottom() + 1 - MARGIN - height,
        )

    return y, height
