"""Output window: full-screen projection display. Renders on QGuiApplication screens."""
from __future__ import annotations

from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QMainWindow, QStackedWidget

from app.models.service import VideoItem
from app.stores.media_store import MediaPlayerStore, apply_video_scale_mode
from app.stores.output_store import OutputStore
from app.stores.service_store import ServiceStore
from app.widgets.qr_overlay import QRCodeOverlay
from app.widgets.slide_renderer import SlideRenderer, sync_renderer_to_output


class OutputWindow(QMainWindow):
    def __init__(
        self,
        service_store: ServiceStore,
        output_store: OutputStore,
        media_store: MediaPlayerStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("JDP Presenter — Output")

        self._service_store = service_store
        self._output_store = output_store
        self._media_store = media_store

        self._renderer = SlideRenderer(self)
        self.video_widget = QVideoWidget(self)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._renderer)
        self._stack.addWidget(self.video_widget)
        self.setCentralWidget(self._stack)
        self.qr_overlay = QRCodeOverlay(self._stack)

        service_store.service_changed.connect(self._render)
        output_store.position_changed.connect(self._render)
        output_store.pages_changed.connect(self._render)
        output_store.is_black_changed.connect(self._render)
        output_store.canvas_changed.connect(self._render)
        output_store.font_scale_changed.connect(self._render)
        self._render()

    def _render(self, *_args) -> None:
        item = self._output_store.current_item()
        if not self._output_store.is_black and isinstance(item, VideoItem):
            apply_video_scale_mode(self.video_widget, item.scale_mode)
            self._stack.setCurrentWidget(self.video_widget)
            return
        self._stack.setCurrentWidget(self._renderer)
        sync_renderer_to_output(self._renderer, self._service_store, self._output_store)


