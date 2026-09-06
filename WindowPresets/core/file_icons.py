"""
Надёжное извлечение значков файлов и программ.

QFileIconProvider (бывший единственный способ) возвращает значок
«по умолчанию» для Store-приложений: их exe лежит в
C:\\Program Files\\WindowsApps\\..., куда обычной программе путь
закрыт, и вытащить иконку из файла она не может.

Здесь несколько независимых способов, от простых к хитрым:
  1) SHGetFileInfo — значок через оболочку Windows;
  2) ExtractIconEx — прямое чтение иконки из ресурсов exe;
  3) логотип UWP-пакета: у Store-программ читается
     AppxManifest.xml в папке пакета и берётся PNG-логотип
     (папка пакета читаема, в отличие от самого exe);
  4) QFileIconProvider — прежний способ, для папок и как запаска.

HICON -> QPixmap конвертируется через GDI (GetIconInfo + GetDIBits).
"""

import logging
import os
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPixmap

logger = logging.getLogger(__name__)

_provider = None

# ——— ctypes: GDI-конвертация HICON ———————————————————————————

import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32


class _ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class _BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", wintypes.LONG),
        ("bmWidth", wintypes.LONG),
        ("bmHeight", wintypes.LONG),
        ("bmWidthBytes", wintypes.LONG),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", wintypes.LPVOID),
    ]


class _BMIH(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BMIH), ("bmiColors", wintypes.DWORD * 3)]


def _hicon_to_pixmap(hicon):
    """HICON -> QPixmap (копия пикселей), None при неудаче."""
    if not hicon:
        return None

    info = _ICONINFO()
    if not _user32.GetIconInfo(hicon, ctypes.byref(info)):
        return None

    try:
        if not info.hbmColor:
            return None

        bmp = _BITMAP()
        if not _gdi32.GetObjectW(
            info.hbmColor, ctypes.sizeof(_BITMAP), ctypes.byref(bmp)
        ):
            return None

        width, height = bmp.bmWidth, bmp.bmHeight
        if width <= 0 or height <= 0:
            return None

        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BMIH)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB

        buf = ctypes.create_string_buffer(width * height * 4)
        hdc = _user32.GetDC(None)
        try:
            ok = _gdi32.GetDIBits(
                hdc, info.hbmColor, 0, height, buf, ctypes.byref(bmi), 0
            )
        finally:
            _user32.ReleaseDC(None, hdc)
        if not ok:
            return None

        img = QImage(buf, width, height, width * 4, QImage.Format_ARGB32)
        img = img.copy()  # отцепиться от сырого буфера

        # Старые иконки без альфы: все пиксели прозрачны -> делаем
        # непрозрачными, иначе значок просто невидим.
        has_alpha = any(
            img.pixelColor(x, y).alpha() > 0
            for y in range(0, height, max(1, height // 16))
            for x in range(0, width, max(1, width // 16))
        )
        if not has_alpha:
            img = img.convertToFormat(QImage.Format_RGB32)

        return QPixmap.fromImage(img)
    finally:
        if info.hbmMask:
            _gdi32.DeleteObject(info.hbmMask)
        if info.hbmColor:
            _gdi32.DeleteObject(info.hbmColor)


# ——— Способы добычи HICON ——————————————————————————————————


def _via_shgetfileinfo(path):
    try:
        import win32con
        import win32gui

        res = win32gui.SHGetFileInfo(
            path, 0,
            win32con.SHGFI_ICON | win32con.SHGFI_LARGEICON,
        )
        hicon = res[1] if isinstance(res, tuple) else None
        pixmap = _hicon_to_pixmap(hicon)
        if hicon:
            win32gui.DestroyIcon(hicon)
        return pixmap
    except Exception:
        return None


def _via_extract_icon(path):
    try:
        import win32gui

        large, _small = win32gui.ExtractIconEx(path, 0, 1, 1)
        pixmap = None
        if large:
            pixmap = _hicon_to_pixmap(large[0])
            for hicon in large:
                win32gui.DestroyIcon(hicon)
        for hicon in (_small or []):
            win32gui.DestroyIcon(hicon)
        return pixmap
    except Exception:
        return None


_LOGO_RE = re.compile(
    r'(?:Square44x44Logo|Square150x150Logo|Logo)\s*=\s*"([^"]+)"'
)


def _via_uwp_logo(path):
    # Store-программа: <...>\WindowsApps\<пакет>\...\x.exe —
    # читаем манифест пакета и берём PNG-логотип.
    try:
        norm = str(path).replace("/", "\\")
        low = norm.lower()
        mark = "windowsapps\\"
        idx = low.find(mark)
        if idx < 0:
            return None

        rest = norm[idx + len(mark):]
        parts = rest.split("\\")
        if len(parts) < 2:
            return None

        pkg_dir = norm[: idx + len(mark)] + parts[0]
        manifest = os.path.join(pkg_dir, "AppxManifest.xml")
        if not os.path.isfile(manifest):
            return None

        with open(manifest, encoding="utf-8", errors="ignore") as file:
            text = file.read()

        logos = _LOGO_RE.findall(text)
        #Square44x44 — «настоящий» значок приложения, остальные — баннеры.
        logos.sort(key=lambda s: (not s.startswith("Square44x44"), len(s)))

        for rel in logos:
            base_dir = os.path.join(
                pkg_dir, os.path.dirname(rel.replace("\\", "/"))
            )
            stem = os.path.splitext(os.path.basename(rel))[0]
            try:
                names = os.listdir(base_dir)
            except Exception:
                continue

            def quality(name):
                # 🔴 Приоритет: логотип, ближайший к 48px сверху
                # (targetsize-48 > targetsize-32 > scale-200 (=88px)
                # > прочие). Раньше брался «самый большой», и у
                # Store-программ без targetsize-256 значок мог быть
                # 16-24px — визуально мелкий.
                suffix = name[len(stem):].lower()
                if "targetsize-" in suffix:
                    n = int(re.findall(r"targetsize-(\d+)", suffix)[0])
                    return (1, -abs(n - 48))   # ближе к 48 — лучше
                if "scale-" in suffix:
                    return (0, 0)
                return (0, -999)

            cands = [
                n for n in names
                if n.startswith(stem) and n.lower().endswith(".png")
            ]
            if not cands:
                continue

            best = max(cands, key=quality)
            pixmap = QPixmap(os.path.join(base_dir, best))
            if not pixmap.isNull():
                # Единый размер: растянут/ужат до 48px — все значки
                # программ одинаковые, мелкие логотипы не мельчят.
                pixmap = pixmap.scaled(
                    48, 48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                return pixmap

    except Exception:
        return None

    return None


def _via_qfile_provider(path):
    global _provider
    if not os.path.exists(path):
        return None
    try:
        if _provider is None:
            from PySide6.QtWidgets import QFileIconProvider
            _provider = QFileIconProvider()
        from PySide6.QtCore import QFileInfo
        return _provider.icon(QFileInfo(path))
    except Exception:
        return None


def _trim_transparent(pixmap, min_alpha=8):
    # 🔴 Store-логотипы (блокнот, paint и др.) часто имеют широкие
    # ПРОЗРАЧНЫЕ поля вокруг рисунка: после сжатия до размера строки
    # глиф визуально мельчает в 1.5-2 раза. Обрезаем прозрачные
    # края — рисунок занимает всю площадь значка.
    # min_alpha: порог «прозрачности» поля; 8 — базовый, 60 —
    # агрессивный (срезает и полупрозрачный ореол/тень).
    if pixmap is None or pixmap.isNull():
        return pixmap

    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    if image.format() != QImage.Format_ARGB32:
        return pixmap  # непрозрачный значок — резать не по чему

    w, h = image.width(), image.height()
    left, top, right, bottom = w, h, -1, -1

    for y in range(h):
        for x in range(w):
            if image.pixelColor(x, y).alpha() > min_alpha:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y

    if right < 0 or bottom < 0:
        return pixmap  # полностью прозрачно — не трогаем

    rect_w = right - left + 1
    rect_h = bottom - top + 1
    if rect_w >= w and rect_h >= h:
        return pixmap  # полей нет

    return QPixmap.fromImage(image.copy(left, top, rect_w, rect_h))


def _glyph_size(pixmap, min_alpha=40):
    # Размер видимого рисунка (bbox пикселей с alpha > min_alpha):
    # (ширина, высота) или None, если видимого нет.
    if pixmap is None or pixmap.isNull():
        return None
    image = pixmap.toImage()
    if image.format() != QImage.Format_ARGB32:
        return (image.width(), image.height())
    w, h = image.width(), image.height()
    left, top, right, bottom = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if image.pixelColor(x, y).alpha() > min_alpha:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y
    if right < 0:
        return None
    return (right - left + 1, bottom - top + 1)


def _scale_48(pixmap):
    return pixmap.scaled(
        48, 48,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _normalize(pixmap):
    # 🔴 Единый размер всех значков программ: 48px. Без этого
    # Store-логотипы и shell-значки бывают 16-32px — «мелкие»
    # на фоне остальных. Сначала обрезка прозрачных полей.
    if pixmap is None or pixmap.isNull():
        return pixmap
    source = _trim_transparent(pixmap)
    if source is None or source.isNull():
        return pixmap

    result = _scale_48(source)

    # 🔴 ПРОВЕРКА РАЗМЕРА ЗНАЧКА: видимый глиф обязан занимать
    # ≥70% канвы. Полупрозрачный ореол/тень вокруг мелкого глифа
    # базовая обрезка (alpha>8) считает «содержимым» — глиф
    # остаётся маленьким в центре. Дожимаем строгой обрезкой
    # (alpha>60) и принудительно увеличиваем до полного размера.
    glyph = _glyph_size(result, min_alpha=40)
    if glyph is not None and max(glyph) < 48 * 0.7:
        tighter = _trim_transparent(source, min_alpha=60)
        if tighter is not None and not tighter.isNull():
            tighter_glyph = _glyph_size(tighter, min_alpha=40)
            before = _glyph_size(source, min_alpha=40)
            if (tighter_glyph and before
                    and max(tighter_glyph) < max(before)):
                result = _scale_48(tighter)
                logger.info(
                    "значок увеличен принудительно: глиф %s -> канва 48px",
                    before,
                )

    return result


def robust_icon(path):
    """Значок exe/папки/файла с несколькими способами извлечения.

    Возвращает QIcon (может быть пустой, если ничего не помогло).
    Все значки приводятся к единому размеру 48px.
    """
    if not path:
        return QIcon()

    pixmap = None

    low = str(path).lower()
    if low.endswith((".exe", ".dll", ".scr")):
        pixmap = _normalize(
            _via_shgetfileinfo(path) or _via_extract_icon(path)
        )
        if pixmap is None and "windowsapps" in low:
            # Store-логотип — через ту же нормализацию: обрезка
            # полей + принудительное увеличение мелкого глифа.
            pixmap = _normalize(_via_uwp_logo(path))

    if pixmap is not None:
        return QIcon(pixmap)

    icon = _via_qfile_provider(path)
    if icon is not None and not icon.isNull():
        # Извлекаем самый большой доступный размер и нормализуем.
        sizes = icon.availableSizes()
        if sizes:
            best = max(sizes, key=lambda s: s.width() * s.height())
            pixmap = _normalize(icon.pixmap(best))
        else:
            pixmap = _normalize(icon.pixmap(64, 64))
        if pixmap is not None and not pixmap.isNull():
            return QIcon(pixmap)

    return QIcon()
