"""Scrollable page thumbnails for multi-page text-based service items."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from app.models.service import BaseServiceItem, ScriptureItem, SongItem, TextItem
from app.models.theme import ServiceTheme
from app.persistence import bible_repo, song_repo
from app.widgets.slide_renderer import SlideRenderer

_THUMBNAIL_ITEM_TYPES = (ScriptureItem, SongItem, TextItem)


class PageThumbnailStrip(QListWidget):
    """A vertically scrollable list of scaled slide renderers."""

    page_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSpacing(6)
        self._canvas_size = QSize(16, 9)
        self._containers: list[QWidget] = []
        self._content_key: tuple[object, ...] | None = None
        self._updating = False
        self.currentRowChanged.connect(self._on_current_row_changed)
        self.hide()

    def set_pages(
        self,
        item: BaseServiceItem | None,
        theme: ServiceTheme | None,
        pages: list[str],
        canvas_size: QSize,
        font_scale: float,
        selected_page: int = 0,
    ) -> None:
        self._updating = True
        self._canvas_size = canvas_size

        if (
            item is None
            or theme is None
            or not isinstance(item, _THUMBNAIL_ITEM_TYPES)
            or len(pages) <= 1
        ):
            self.clear()
            self._containers.clear()
            self._content_key = None
            self.hide()
            self._updating = False
            return

        content_key = (
            id(item),
            item.title,
            getattr(item, "reference", ""),
            getattr(item, "bible", ""),
            getattr(item, "song_id", ""),
            repr(theme),
            tuple(pages),
            canvas_size.width(),
            canvas_size.height(),
            font_scale,
        )
        if content_key == self._content_key:
            self.setCurrentRow(max(0, min(selected_page, len(pages) - 1)))
            self.show()
            self._updating = False
            return

        self.clear()
        self._containers.clear()
        self._content_key = content_key

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

        for page_index, page_text in enumerate(pages):
            container = QWidget(self)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(3, 3, 3, 3)
            layout.setSpacing(2)

            renderer = SlideRenderer(container)
            renderer.set_canvas_size(canvas_size)
            renderer.set_font_scale(font_scale)
            renderer.set_black(False)
            renderer.render(
                item,
                theme,
                page_text,
                version_label,
                song_author,
                song_ccli,
                page_index,
                len(pages),
            )
            label = QLabel(f"Page {page_index + 1}", container)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(label.fontMetrics().height())
            layout.addWidget(renderer)
            layout.addWidget(label)

            list_item = QListWidgetItem()
            self.addItem(list_item)
            self.setItemWidget(list_item, container)
            self._containers.append(container)

        self._resize_thumbnails()
        self.setCurrentRow(max(0, min(selected_page, len(pages) - 1)))
        self.show()
        self._updating = False

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._resize_thumbnails()

    def _resize_thumbnails(self) -> None:
        width = max(80, self.viewport().width() - 10)
        canvas_width = max(1, self._canvas_size.width())
        preview_height = round(width * self._canvas_size.height() / canvas_width)
        caption_height = self.fontMetrics().height()
        item_height = preview_height + caption_height + 8
        for row, container in enumerate(self._containers):
            container.setFixedSize(width, item_height)
            list_item = self.item(row)
            if list_item is not None:
                list_item.setSizeHint(QSize(width, item_height))

    def _on_current_row_changed(self, page_index: int) -> None:
        if not self._updating and page_index >= 0:
            self.page_selected.emit(page_index)