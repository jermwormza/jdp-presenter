"""Pure slide-rendering widget shared by the Output window and the Control window's preview panel.

Draws onto a fixed virtual canvas (see app.utils.canvas) that is scaled + letterboxed to fit
whatever pixel size this widget actually has. Because Preview and Output both draw the exact same
canvas content through this same class, Preview is always a faithful scaled copy of Output.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, QFile, QIODevice
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from app.models.service import ImageItem, ScriptureItem, SongItem, TextItem
from app.models.theme import ServiceTheme, TextStyle
from app.persistence import bible_repo, song_repo
from app.utils import canvas as canvas_util
from app.utils.media_paths import resolve_media_path
from app.utils.pagination import autofit_font_size, font_for_style, paginate_item
from app.utils.theme_utils import merge_theme

MARGIN = 60


class SlideRenderer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item = None
        self._theme: ServiceTheme | None = None
        self._page_text = ""
        self._version_label = ""
        self._song_author = ""
        self._song_ccli = ""
        self._page_index = 0
        self._total_pages = 1
        self._black = True
        self._canvas_size = canvas_util.size_for_ratio(canvas_util.DEFAULT_CANVAS_RATIO)
        self._font_scale = 1.0

    def set_black(self, black: bool) -> None:
        self._black = black
        self.update()

    def set_canvas_size(self, size: QSize) -> None:
        self._canvas_size = size
        self.update()

    def set_font_scale(self, scale: float) -> None:
        self._font_scale = scale
        self.update()

    def render(
        self,
        item,
        theme: ServiceTheme,
        page_text: str = "",
        version_label: str = "",
        song_author: str = "",
        song_ccli: str = "",
        page_index: int = 0,
        total_pages: int = 1,
    ) -> None:
        self._item = item
        self._theme = theme
        self._page_text = page_text
        self._version_label = version_label
        self._song_author = song_author
        self._song_ccli = song_ccli
        self._page_index = page_index
        self._total_pages = total_pages
        self.update()

    def _qfont(self, style: TextStyle) -> QFont:
        return font_for_style(style, self._font_scale)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))

        if self._black or self._item is None or self._theme is None:
            painter.end()
            return

        scale = min(
            self.width() / self._canvas_size.width(), self.height() / self._canvas_size.height()
        )
        offset_x = (self.width() - self._canvas_size.width() * scale) / 2
        offset_y = (self.height() - self._canvas_size.height() * scale) / 2
        painter.translate(offset_x, offset_y)
        painter.scale(scale, scale)
        canvas_rect = QRect(0, 0, self._canvas_size.width(), self._canvas_size.height())

        bg = self._theme.background
        color = QColor(bg.color)
        color.setAlphaF(max(0.0, min(1.0, bg.opacity)))
        painter.fillRect(canvas_rect, color)

        if isinstance(self._item, ScriptureItem):
            self._paint_scripture(painter, canvas_rect, self._item)
        elif isinstance(self._item, SongItem):
            self._paint_song(painter, canvas_rect, self._item)
        elif isinstance(self._item, TextItem):
            self._paint_text(painter, canvas_rect)
        elif isinstance(self._item, ImageItem):
            self._paint_image(painter, canvas_rect, self._item)
        else:
            self._paint_placeholder(painter, canvas_rect, self._item.type)

        painter.end()

    def _paint_scripture(self, painter: QPainter, canvas_rect: QRect, item: ScriptureItem) -> None:
        theme = self._theme.scripture

        painter.setFont(self._qfont(theme.verse_text))
        painter.setPen(QColor(theme.verse_text.color))
        text_rect = canvas_rect.adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)
        painter.drawText(
            text_rect,
            Qt.TextFlag.TextWordWrap
            | Qt.TextFlag.TextDontClip
            | Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter,
            self._page_text,
        )

        painter.setFont(self._qfont(theme.reference))
        painter.setPen(QColor(theme.reference.color))
        metrics = QFontMetrics(painter.font())
        inner = canvas_rect.adjusted(20, 20, -20, -20)
        line_height = metrics.height()
        is_top = theme.reference.position.startswith("top")
        bar_rect = QRect(
            inner.left(), inner.top() if is_top else inner.bottom() - line_height, inner.width(), line_height
        )
        parts = [item.reference]
        if theme.version.show:
            parts.append(self._version_label or item.bible)
        parts.append(f"{self._page_index + 1}/{self._total_pages}")
        painter.drawText(bar_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, " | ".join(parts))

    def _paint_song(self, painter: QPainter, canvas_rect: QRect, item: SongItem) -> None:
        theme = self._theme.song
        text_rect = canvas_rect.adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)

        # Use the theme's defined lyrics size by default; only shrink (never grow) a verse that
        # wouldn't otherwise fit on one page, and only for that verse — other slides stay unaffected.
        fit_size = autofit_font_size(
            self._page_text, theme.lyrics, canvas_rect.size(), self._font_scale, max_size=theme.lyrics.font_size
        )
        lyrics_font = QFont(theme.lyrics.font_family, fit_size)
        lyrics_font.setBold(theme.lyrics.font_weight == "bold")
        lyrics_font.setItalic(theme.lyrics.font_style == "italic")
        painter.setFont(lyrics_font)
        painter.setPen(QColor(theme.lyrics.color))
        painter.drawText(
            text_rect,
            Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextDontClip | Qt.AlignmentFlag.AlignCenter,
            self._page_text,
        )

        if theme.metadata.show:
            reference_style = self._theme.scripture.reference
            painter.setPen(QColor(reference_style.color))
            inner = canvas_rect.adjusted(20, 20, -20, -20)
            parts = [item.title]
            if self._song_author:
                parts.append(self._song_author)
            if self._song_ccli:
                parts.append(f"CCLI {self._song_ccli}")
            parts.append(f"{self._page_index + 1}/{self._total_pages}")
            footer_text = " | ".join(parts)
            footer_font = self._qfont(reference_style)
            while (
                footer_font.pointSize() > 8
                and QFontMetrics(footer_font).horizontalAdvance(footer_text) > inner.width()
            ):
                footer_font.setPointSize(footer_font.pointSize() - 1)
            painter.setFont(footer_font)
            line_height = QFontMetrics(footer_font).height()
            is_top = theme.metadata.position.startswith("top")
            bar_rect = QRect(
                inner.left(),
                inner.top() if is_top else inner.bottom() - line_height,
                inner.width(),
                line_height,
            )
            painter.drawText(
                bar_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                footer_text,
            )

    def _paint_text(self, painter: QPainter, canvas_rect: QRect) -> None:
        theme = self._theme.scripture.verse_text
        painter.setFont(self._qfont(theme))
        painter.setPen(QColor(theme.color))
        text_rect = canvas_rect.adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)
        painter.drawText(
            text_rect,
            Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextDontClip | Qt.AlignmentFlag.AlignCenter,
            self._page_text,
        )

    def _paint_image(self, painter: QPainter, canvas_rect: QRect, item: ImageItem) -> None:
        # Use QFile to read the image data first — this resolves macOS sandbox bookmarks
        # for files selected via file dialog (which grants temporary access that QPixmap
        # doesn't automatically resolve when loading directly from a path string).
        pixmap = QPixmap()
        file = QFile(resolve_media_path(item.path))
        if file.open(QIODevice.OpenModeFlag.ReadOnly):
            data = file.readAll()
            pixmap.loadFromData(data)
            file.close()
        if pixmap.isNull():
            self._paint_placeholder(painter, canvas_rect, "image (not found)")
            return
        _draw_scaled_media(painter, canvas_rect, pixmap, item.scale_mode)

    def _paint_placeholder(self, painter: QPainter, canvas_rect: QRect, label: str) -> None:
        painter.setFont(QFont("Inter", 28))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(canvas_rect, Qt.AlignmentFlag.AlignCenter, f"{label} rendering not yet implemented")


def _draw_scaled_media(painter: QPainter, canvas_rect: QRect, pixmap: QPixmap, scale_mode: str) -> None:
    """Draw pixmap into canvas_rect, always preserving aspect ratio, centered, per scale_mode:

    - "fit": scale down/up so the whole image is visible (the default; letterboxed if needed).
    - "original": no scaling at all; cropped to the canvas if larger than it.
    - "fill_width"/"fill_height": scale so that dimension exactly fills the canvas, cropping the
      other dimension (centered) if it then overflows.
    """
    size = pixmap.size()
    if size.isEmpty():
        return
    if scale_mode == "original":
        scale = 1.0
    elif scale_mode == "fill_width":
        scale = canvas_rect.width() / size.width()
    elif scale_mode == "fill_height":
        scale = canvas_rect.height() / size.height()
    else:  # "fit"
        scale = min(canvas_rect.width() / size.width(), canvas_rect.height() / size.height())

    draw_width = round(size.width() * scale)
    draw_height = round(size.height() * scale)
    x = canvas_rect.x() + (canvas_rect.width() - draw_width) // 2
    y = canvas_rect.y() + (canvas_rect.height() - draw_height) // 2

    painter.save()
    painter.setClipRect(canvas_rect)
    if scale == 1.0:
        painter.drawPixmap(x, y, pixmap)
    else:
        scaled = pixmap.scaled(
            draw_width, draw_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(x, y, scaled)
    painter.restore()


def sync_renderer_to_output(renderer: SlideRenderer, service_store, output_store) -> None:
    """Push the current OutputStore position into a SlideRenderer (used by Output + Preview)."""
    renderer.set_canvas_size(output_store.canvas_size())
    renderer.set_font_scale(output_store.font_scale)
    renderer.set_black(output_store.is_black)
    if output_store.is_black:
        return
    service = service_store.service
    item = output_store.current_item()
    if service is None or item is None:
        renderer.set_black(True)
        return
    theme = merge_theme(service.theme, item.display_settings)
    version_label = ""
    song_author = ""
    song_ccli = ""
    if isinstance(item, ScriptureItem):
        version_label = bible_repo.resolve_bible_label(item.bible)
    elif isinstance(item, SongItem):
        try:
            song = song_repo.load_song(item.song_id)
            song_author = song.author or ""
            song_ccli = song.ccli or ""
        except (FileNotFoundError, OSError, ValueError):
            pass
    renderer.render(
        item,
        theme,
        output_store.current_page_text(),
        version_label,
        song_author,
        song_ccli,
        output_store.slide_index,
        len(output_store.current_pages()),
    )


def sync_renderer_to_next_item(renderer: SlideRenderer, service_store, output_store) -> None:
    """Render the item after the current one (first page), regardless of live/black state."""
    renderer.set_canvas_size(output_store.canvas_size())
    renderer.set_font_scale(output_store.font_scale)
    service = service_store.service
    next_index = output_store.item_index + 1
    if service is None or next_index >= len(service.items):
        renderer.set_black(True)
        return
    item = service.items[next_index]
    theme = merge_theme(service.theme, item.display_settings)
    pages = paginate_item(item, theme, output_store.canvas_size(), output_store.font_scale) or [""]
    version_label = ""
    song_author = ""
    song_ccli = ""
    if isinstance(item, ScriptureItem):
        version_label = bible_repo.resolve_bible_label(item.bible)
    elif isinstance(item, SongItem):
        try:
            song = song_repo.load_song(item.song_id)
            song_author = song.author or ""
            song_ccli = song.ccli or ""
        except (FileNotFoundError, OSError, ValueError):
            pass
    renderer.set_black(False)
    renderer.render(item, theme, pages[0], version_label, song_author, song_ccli, 0, len(pages))
