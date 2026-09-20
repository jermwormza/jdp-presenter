"""Small hand-drawn vector icons for the service list toolbar (no image assets needed)."""
from __future__ import annotations

from functools import wraps
from typing import Protocol

import qtawesome as qta
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap, QPolygonF

_SIZE = 28

# Neutral fallback used only by the hand-drawn compatibility icons.
_DEFAULT_ICON_COLOR = QColor("#3d8fb5")


class IconFactory(Protocol):
    def __call__(self, color: QColor | None = None) -> QIcon: ...


def _prefer_font_awesome(name: str, default_color: str | None = None):
    """Use a Font Awesome glyph while retaining the hand-drawn icon as fallback."""
    def decorate(fallback: IconFactory) -> IconFactory:
        @wraps(fallback)
        def create(color: QColor | None = None) -> QIcon:
            icon_color = color.name() if color is not None else default_color or "#3d8fb5"
            try:
                return qta.icon(
                    name,
                    color=icon_color,
                    color_active=icon_color,
                    color_disabled="#737b86",
                )
            except Exception:
                return fallback(color)

        return create

    return decorate


def _new_painter(color: QColor | None = None) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(_SIZE, _SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pixmap, painter


def _get_pen(color: QColor | None = None):
    """Create a pen with the specified color or default."""
    from PySide6.QtGui import QPen
    pen = QPen(color or _DEFAULT_ICON_COLOR)
    pen.setWidthF(2.0)
    return pen


def _get_brush(color: QColor | None = None):
    """Create a brush with the specified color or default."""
    from PySide6.QtGui import QBrush
    return QBrush(color or _DEFAULT_ICON_COLOR)


@_prefer_font_awesome("fa6s.arrow-up", "#4a9d72")
def move_up_icon(color: QColor | None = None) -> QIcon:
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.drawLine(QPointF(14, 23), QPointF(14, 6))
    painter.drawLine(QPointF(14, 6), QPointF(7, 13))
    painter.drawLine(QPointF(14, 6), QPointF(21, 13))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.arrow-down", "#d79b32")
def move_down_icon(color: QColor | None = None) -> QIcon:
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.drawLine(QPointF(14, 5), QPointF(14, 22))
    painter.drawLine(QPointF(14, 22), QPointF(7, 15))
    painter.drawLine(QPointF(14, 22), QPointF(21, 15))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.music", "#d55e83")
def song_icon(color: QColor | None = None) -> QIcon:
    """A single eighth-note glyph."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(_get_brush(color))

    stem_x = 17.5
    painter.drawLine(QPointF(stem_x, 4), QPointF(stem_x, 20))

    flag = QPainterPath()
    flag.moveTo(stem_x, 4)
    flag.cubicTo(stem_x + 8, 6, stem_x + 7, 12, stem_x, 13)
    flag.closeSubpath()
    painter.drawPath(flag)

    painter.save()
    painter.translate(stem_x - 4, 20)
    painter.rotate(-20)
    painter.drawEllipse(QRectF(-5, -3.5, 10, 7))
    painter.restore()

    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.book-open", "#d79b32")
def scripture_icon(color: QColor | None = None) -> QIcon:
    """An open book."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    left = QPainterPath()
    left.moveTo(14, 8)
    left.cubicTo(10, 6, 6, 6, 4, 7)
    left.lineTo(4, 21)
    left.cubicTo(6, 20, 10, 20, 14, 22)
    left.closeSubpath()
    painter.drawPath(left)

    right = QPainterPath()
    right.moveTo(14, 8)
    right.cubicTo(18, 6, 22, 6, 24, 7)
    right.lineTo(24, 21)
    right.cubicTo(22, 20, 18, 20, 14, 22)
    right.closeSubpath()
    painter.drawPath(right)

    painter.drawLine(QPointF(14, 8), QPointF(14, 22))

    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.font", "#4a9d72")
def text_icon(color: QColor | None = None) -> QIcon:
    """A stylised serif capital T."""
    pixmap, painter = _new_painter(color)
    font = QFont("Georgia")
    font.setBold(True)
    font.setPointSizeF(18)
    painter.setFont(font)
    painter.setPen(_get_pen(color))
    painter.drawText(QRectF(0, 0, _SIZE, _SIZE), Qt.AlignmentFlag.AlignCenter, "T")
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.trash-can", "#d95757")
def delete_icon(color: QColor | None = None) -> QIcon:
    """A trash can."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    painter.drawLine(QPointF(6, 8), QPointF(22, 8))
    painter.drawLine(QPointF(11, 8), QPointF(11, 5))
    painter.drawLine(QPointF(17, 8), QPointF(17, 5))
    painter.drawRect(QRectF(11, 5, 6, 3))

    body = QPainterPath()
    body.moveTo(7.5, 8)
    body.lineTo(9, 23)
    body.lineTo(19, 23)
    body.lineTo(20.5, 8)
    painter.drawPath(body)

    painter.drawLine(QPointF(11.5, 11), QPointF(12, 20))
    painter.drawLine(QPointF(14, 11), QPointF(14, 20))
    painter.drawLine(QPointF(16.5, 11), QPointF(16, 20))

    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.photo-film", "#5b8fd9")
def media_icon(color: QColor | None = None) -> QIcon:
    """A film strip with a play triangle, for image/video/audio media items."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    frame = QRectF(3, 5, 22, 18)
    painter.drawRoundedRect(frame, 2, 2)
    for x in (3, 9, 15, 21):
        painter.drawLine(QPointF(x, 5), QPointF(x, 9))
        painter.drawLine(QPointF(x, 19), QPointF(x, 23))

    play = QPainterPath()
    play.moveTo(11.5, 10.5)
    play.lineTo(18.5, 14)
    play.lineTo(11.5, 17.5)
    play.closeSubpath()
    painter.setBrush(_get_brush(color))
    painter.drawPath(play)

    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.play")
def play_icon(color: QColor | None = None) -> QIcon:
    """A simple play triangle."""
    pixmap, painter = _new_painter(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_get_brush(color))
    play = QPainterPath()
    play.moveTo(9, 6)
    play.lineTo(22, 14)
    play.lineTo(9, 22)
    play.closeSubpath()
    painter.drawPath(play)
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.pause")
def pause_icon(color: QColor | None = None) -> QIcon:
    """Two vertical bars."""
    pixmap, painter = _new_painter(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_get_brush(color))
    painter.drawRect(QRectF(8, 6, 5, 16))
    painter.drawRect(QRectF(16, 6, 5, 16))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.arrows-rotate", "#28a49a")
def refresh_icon(color: QColor | None = None) -> QIcon:
    """A circular rewind arrow (refresh/reload)."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(QRectF(5, 5, 18, 18), 30 * 16, 300 * 16)
    # Arrow head at the top of the arc
    painter.setBrush(_get_brush(color))
    painter.drawPolygon(QPolygonF([QPointF(10, 5), QPointF(7, 9), QPointF(12.5, 9)]))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.qrcode", "#8067c5")
def qr_icon(color: QColor | None = None) -> QIcon:
    """A simplified QR-code glyph: a grid of solid squares with the classic 3 corner markers."""
    pixmap, painter = _new_painter(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_get_brush(color))

    def corner_marker(x: float, y: float) -> None:
        painter.drawRect(QRectF(x, y, 8, 8))
        painter.save()
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawRect(QRectF(x + 2, y + 2, 4, 4))
        painter.restore()
        painter.setBrush(_get_brush(color))
        painter.drawRect(QRectF(x + 3, y + 3, 2, 2))

    corner_marker(3, 3)
    corner_marker(17, 3)
    corner_marker(3, 17)

    for dx, dy in ((18, 18), (21, 21), (18, 23), (23, 18), (24, 24)):
        painter.drawRect(QRectF(dx, dy, 2, 2))

    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.display", "#3d8fb5")
def output_screen_icon(color: QColor | None = None) -> QIcon:
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(3, 4, 22, 16), 2, 2)
    painter.drawLine(QPointF(14, 20), QPointF(14, 24))
    painter.drawLine(QPointF(9, 24), QPointF(19, 24))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.circle", "#ff5b62")
def record_icon(color: QColor | None = None) -> QIcon:
    """A red filled circle."""
    pixmap, painter = _new_painter(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 80, 80))  # Bright red
    painter.drawEllipse(QRectF(5, 5, 18, 18))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.stop", "#ff5b62")
def stop_icon(color: QColor | None = None) -> QIcon:
    """A red filled square."""
    pixmap, painter = _new_painter(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 80, 80))  # Bright red
    painter.drawRect(QRectF(6, 6, 16, 16))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.file", "#4aa27a")
def new_icon(color: QColor | None = None) -> QIcon:
    """A blank page with a folded corner."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(QRectF(4, 4, 20, 20))
    # Folded corner
    painter.drawLine(QPointF(18, 4), QPointF(18, 10))
    painter.drawLine(QPointF(18, 10), QPointF(12, 10))
    painter.drawLine(QPointF(12, 10), QPointF(18, 4))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.folder-open", "#d79b32")
def open_icon(color: QColor | None = None) -> QIcon:
    """A folder opening."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    # Folder tab
    tab = QPainterPath()
    tab.moveTo(4, 10)
    tab.lineTo(6, 10)
    tab.lineTo(8, 6)
    tab.lineTo(22, 6)
    tab.lineTo(22, 22)
    tab.lineTo(4, 22)
    tab.closeSubpath()
    painter.drawPath(tab)
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.floppy-disk", "#398bc6")
def save_icon(color: QColor | None = None) -> QIcon:
    """A floppy disk."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(4, 4, 20, 20), 2, 2)
    # Metal shutter
    painter.drawRect(QRectF(4, 4, 20, 6))
    # Label area
    painter.drawLine(QPointF(8, 14), QPointF(20, 14))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.file-import", "#4a9d72")
def import_icon(color: QColor | None = None) -> QIcon:
    """Down arrow into a box."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(QRectF(6, 4, 16, 18))
    # Arrow
    painter.drawLine(QPointF(14, 10), QPointF(14, 18))
    painter.drawLine(QPointF(10, 14), QPointF(14, 18))
    painter.drawLine(QPointF(18, 14), QPointF(14, 18))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.file-export", "#ba6db0")
def export_icon(color: QColor | None = None) -> QIcon:
    """Up arrow out of a box."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(QRectF(6, 4, 16, 18))
    # Arrow
    painter.drawLine(QPointF(14, 18), QPointF(14, 10))
    painter.drawLine(QPointF(10, 14), QPointF(14, 10))
    painter.drawLine(QPointF(18, 14), QPointF(14, 10))
    painter.end()
    return QIcon(pixmap)


@_prefer_font_awesome("fa6s.print", "#687c91")
def print_icon(color: QColor | None = None) -> QIcon:
    """A printer."""
    pixmap, painter = _new_painter(color)
    painter.setPen(_get_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    # Printer body
    body = QPainterPath()
    body.moveTo(4, 8)
    body.lineTo(24, 8)
    body.lineTo(24, 22)
    body.lineTo(4, 22)
    body.closeSubpath()
    painter.drawPath(body)
    # Paper tray
    painter.drawLine(QPointF(6, 22), QPointF(6, 25))
    painter.drawLine(QPointF(22, 22), QPointF(22, 25))
    # Top detail
    painter.drawLine(QPointF(8, 6), QPointF(20, 6))
    painter.drawLine(QPointF(10, 4), QPointF(18, 4))
    painter.end()
    return QIcon(pixmap)
