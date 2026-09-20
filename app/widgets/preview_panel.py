"""Live preview panel: a scaled-down mirror of exactly what the Output window is showing."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QSplitter, QStackedWidget, QVBoxLayout, QWidget

from app.models.service import VideoItem
from app.stores.media_store import MediaPlayerStore, apply_video_scale_mode
from app.stores.output_store import OutputStore
from app.stores.service_store import ServiceStore
from app.utils.pagination import paginate_item
from app.utils.theme_utils import merge_theme
from app.widgets.page_thumbnail_strip import PageThumbnailStrip
from app.widgets.qr_overlay import QRCodeOverlay
from app.widgets.slide_renderer import (
    SlideRenderer,
    sync_renderer_to_next_item,
    sync_renderer_to_output,
)


class PreviewPanel(QWidget):
    """Mirrors the Output window: shows live video when the current item itself is media."""

    def __init__(
        self,
        service_store: ServiceStore,
        output_store: OutputStore,
        media_store: MediaPlayerStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service_store = service_store
        self._output_store = output_store
        self._media_store = media_store

        self._renderer = SlideRenderer(self)
        self._renderer.setMinimumSize(320, 180)
        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumSize(320, 180)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._renderer)
        self._stack.addWidget(self.video_widget)
        self.qr_overlay = QRCodeOverlay(self._stack)

        self._thumbnails = PageThumbnailStrip(self)
        self._thumbnails.page_selected.connect(self._select_page)
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.addWidget(self._thumbnails)
        self._splitter.addWidget(self._stack)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setCollapsible(1, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._splitter)

        service_store.service_changed.connect(self._render)
        output_store.position_changed.connect(self._render)
        output_store.pages_changed.connect(self._render)
        output_store.is_black_changed.connect(self._render)
        output_store.canvas_changed.connect(self._render)
        output_store.font_scale_changed.connect(self._render)
        media_store.active_changed.connect(self._render)
        self._render()

    def _render(self, *_args) -> None:
        item = self._output_store.current_item()
        service = self._service_store.service
        was_hidden = self._thumbnails.isHidden()
        if service is None or item is None:
            self._thumbnails.set_pages(
                None,
                None,
                [],
                self._output_store.canvas_size(),
                self._output_store.font_scale,
            )
        else:
            theme = merge_theme(service.theme, item.display_settings)
            self._thumbnails.set_pages(
                item,
                theme,
                self._output_store.current_pages(),
                self._output_store.canvas_size(),
                self._output_store.font_scale,
                self._output_store.slide_index,
            )
        if was_hidden and not self._thumbnails.isHidden():
            self._set_initial_splitter_sizes()

        if not self._output_store.is_black and isinstance(item, VideoItem):
            apply_video_scale_mode(self.video_widget, item.scale_mode)
            self._stack.setCurrentWidget(self.video_widget)
            return
        self._stack.setCurrentWidget(self._renderer)
        sync_renderer_to_output(self._renderer, self._service_store, self._output_store)

    def _select_page(self, page_index: int) -> None:
        self._output_store.set_position(self._output_store.item_index, page_index)

    def _set_initial_splitter_sizes(self) -> None:
        width = max(500, self.width())
        self._splitter.setSizes([width // 5, width * 4 // 5])


class NextPreviewPanel(QWidget):
    """Preview the next item, including video when it is playing in the background."""

    def __init__(
        self,
        service_store: ServiceStore,
        output_store: OutputStore,
        media_store: MediaPlayerStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service_store = service_store
        self._output_store = output_store
        self._media_store = media_store

        self._renderer = SlideRenderer(self)
        self._renderer.setMinimumSize(320, 180)
        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumSize(320, 180)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._renderer)
        self._stack.addWidget(self.video_widget)

        self._thumbnails = PageThumbnailStrip(self)
        self._thumbnails.page_selected.connect(self._select_page)
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.addWidget(self._thumbnails)
        self._splitter.addWidget(self._stack)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setCollapsible(1, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._splitter)

        service_store.service_changed.connect(self._render)
        output_store.position_changed.connect(self._render)
        output_store.canvas_changed.connect(self._render)
        output_store.font_scale_changed.connect(self._render)
        media_store.active_changed.connect(self._render)
        self._render()

    def _render(self, *_args) -> None:
        service = self._service_store.service
        next_index = self._output_store.item_index + 1
        next_item = (
            service.items[next_index]
            if service is not None and next_index < len(service.items)
            else None
        )
        was_hidden = self._thumbnails.isHidden()
        if service is None or next_item is None:
            self._thumbnails.set_pages(
                None,
                None,
                [],
                self._output_store.canvas_size(),
                self._output_store.font_scale,
            )
        else:
            theme = merge_theme(service.theme, next_item.display_settings)
            pages = paginate_item(
                next_item,
                theme,
                self._output_store.canvas_size(),
                self._output_store.font_scale,
            ) or [""]
            self._thumbnails.set_pages(
                next_item,
                theme,
                pages,
                self._output_store.canvas_size(),
                self._output_store.font_scale,
            )
        if was_hidden and not self._thumbnails.isHidden():
            self._set_initial_splitter_sizes()

        if self._media_store.active_target == "next" and isinstance(
            self._media_store.active_item, VideoItem
        ):
            apply_video_scale_mode(self.video_widget, self._media_store.active_item.scale_mode)
            self._stack.setCurrentWidget(self.video_widget)
            return
        self._stack.setCurrentWidget(self._renderer)
        sync_renderer_to_next_item(self._renderer, self._service_store, self._output_store)

    def _select_page(self, page_index: int) -> None:
        self._output_store.set_position(self._output_store.item_index + 1, page_index)

    def _set_initial_splitter_sizes(self) -> None:
        width = max(500, self.width())
        self._splitter.setSizes([width // 5, width * 4 // 5])
