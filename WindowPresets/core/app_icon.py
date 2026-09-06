"""
Иконка приложения — автоматически собирается из PNG-картинки,
лежащей в папке ico.

При запуске программы: если PNG новее готового app.ico (или app.ico
ещё не существует), .ico пересобирается. Достаточно положить в ico
новую картинку и перезапустить программу.

ICO-контейнер собирается сам (многосайзовый: 16–256px, ступенчатое
уменьшение для чёткости мелких значков) — зависимость Pillow не
нужна. У .exe-сборки папка ico ищется сначала рядом с exe (живая),
затем в распакованных ресурсах.
"""

import logging
import os
import struct

from PySide6.QtCore import QBuffer, Qt
from PySide6.QtGui import QPixmap

from core.app_paths import base_dir, is_frozen, resource_dir

logger = logging.getLogger(__name__)

ICO_NAME = "app.ico"
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _icon_dirs():
    # Сначала живая папка рядом с программой, затем ресурсы сборки.
    dirs = [base_dir() / "ico"]
    res = resource_dir() / "ico"
    if res not in dirs:
        dirs.append(res)
    return dirs


def _source_png(dirs):
    # Самый свежий PNG из первой папки, где PNG есть.
    for directory in dirs:
        try:
            pngs = list(directory.glob("*.png"))
        except Exception:
            continue
        if pngs:
            return max(pngs, key=lambda p: p.stat().st_mtime)
    return None


def _find_ico(dirs):
    for directory in dirs:
        ico = directory / ICO_NAME
        if ico.exists():
            return ico
    return None


def _render_ico(source_png, target_ico):
    # Ступенчатое уменьшение вдвое даёт более чёткие мелкие значки,
    # чем один проход до целевого размера.
    src = QPixmap(str(source_png))
    if src.isNull():
        raise RuntimeError(f"не читается PNG: {source_png}")

    pngs = []
    for size in ICO_SIZES:
        cur = src
        while cur.width() // 2 >= size:
            cur = cur.scaled(
                cur.width() // 2,
                cur.height() // 2,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        cur = cur.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        buf = QBuffer()
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        cur.save(buf, "PNG")
        pngs.append(buf.data())

    entries = b""
    images = b""
    offset = 6 + 16 * len(ICO_SIZES)
    for size, data in zip(ICO_SIZES, pngs):
        dim = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset
        )
        images += data
        offset += len(data)

    # Запись через временный файл: обрыв не оставит битый app.ico.
    tmp = str(target_ico) + ".tmp"
    with open(tmp, "wb") as file:
        file.write(
            struct.pack("<HHH", 0, 1, len(ICO_SIZES)) + entries + images
        )
    os.replace(tmp, target_ico)


def ensure_app_icon():
    """Собирает app.ico из свежего PNG при необходимости.

    Возвращает путь к актуальному app.ico (или None, если иконки
    нет вовсе).
    """
    if is_frozen():
        # 🔴 .exe-сборка: иконка уже ВШИТА в exe (--icon) —
        # автосборка рядом с exe не нужна (живой папки ico там
        # нет, попытка писала warning). Берём из ресурсов сборки.
        ico = _find_ico([resource_dir() / "ico"])
        return str(ico) if ico else None

    dirs = _icon_dirs()

    target = dirs[0] / ICO_NAME
    png = _source_png(dirs)

    try:
        need = False

        if png is not None:
            if not target.exists():
                need = True
            else:
                need = (
                    png.stat().st_mtime > target.stat().st_mtime
                )

        if need:
            _render_ico(png, target)
            logger.info("иконка собрана из %s", png.name)

    except Exception as exc:
        logger.warning("не удалось собрать иконку: %s", exc)

    if target.exists():
        return str(target)

    fallback = _find_ico(dirs[1:]) if len(dirs) > 1 else None
    return str(fallback) if fallback else None
