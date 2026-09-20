"""OutputStore: current position within the active service, live/black state, canvas + font scale.

Owns pagination: whenever the service, current item, theme, canvas ratio, or font scale changes,
pages are recomputed via app.utils.pagination so navigation always agrees with what actually fits.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Signal

from app.stores.service_store import ServiceStore
from app.utils import canvas
from app.utils.pagination import paginate_item
from app.utils.theme_utils import merge_theme

FONT_SCALE_STEP = 0.1
FONT_SCALE_MIN = 0.4
FONT_SCALE_MAX = 3.0


class OutputStore(QObject):
    position_changed = Signal(int, int)  # item_index, page_index
    pages_changed = Signal(list)  # list[str], current item's pages
    is_live_changed = Signal(bool)
    is_black_changed = Signal(bool)
    canvas_changed = Signal(str)
    font_scale_changed = Signal(float)

    def __init__(self, service_store: ServiceStore) -> None:
        super().__init__()
        self._service_store = service_store
        self._item_index = 0
        self._slide_index = 0
        self._is_live = False
        self._is_black = True
        self._canvas_ratio = canvas.DEFAULT_CANVAS_RATIO
        self._font_scale = 1.0
        self._pages: list[str] = [""]
        self._last_service_id: str | None = None
        self._showing_boundary_blank = False
        self._boundary_direction: str | None = None

        service_store.service_changed.connect(self._on_service_changed)
        self._on_service_changed(service_store.service)

    @property
    def is_live(self) -> bool:
        return self._is_live

    @property
    def is_black(self) -> bool:
        return self._is_black

    @property
    def item_index(self) -> int:
        return self._item_index

    @property
    def slide_index(self) -> int:
        return self._slide_index

    @property
    def canvas_ratio(self) -> str:
        return self._canvas_ratio

    @property
    def font_scale(self) -> float:
        return self._font_scale

    def canvas_size(self) -> QSize:
        return canvas.size_for_ratio(self._canvas_ratio)

    def current_item(self):
        if self._showing_boundary_blank:
            return None
        service = self._service_store.service
        if service is None or not service.items:
            return None
        if self._item_index >= len(service.items):
            return None
        return service.items[self._item_index]

    def current_pages(self) -> list[str]:
        return self._pages

    def current_page_text(self) -> str:
        if self._showing_boundary_blank or not self._pages:
            return ""
        return self._pages[min(self._slide_index, len(self._pages) - 1)]

    def _on_service_changed(self, service) -> None:
        new_id = service.id if service is not None else None
        if new_id != self._last_service_id:
            self._item_index = 0
            self._slide_index = 0
            self._last_service_id = new_id
        self._showing_boundary_blank = False
        self._boundary_direction = None
        self._recompute_pages()
        self.position_changed.emit(self._item_index, self._slide_index)

    def _recompute_pages(self) -> None:
        service = self._service_store.service
        if service is not None and service.items:
            self._item_index = max(0, min(self._item_index, len(service.items) - 1))
        item = self.current_item()
        if service is None or item is None:
            self._pages = [""]
        else:
            theme = merge_theme(service.theme, item.display_settings)
            self._pages = paginate_item(item, theme, self.canvas_size(), self._font_scale) or [""]
        self._slide_index = max(0, min(self._slide_index, len(self._pages) - 1))
        self.pages_changed.emit(self._pages)

    def set_live(self, is_live: bool) -> None:
        self._is_live = is_live
        self.is_live_changed.emit(is_live)

    def set_black(self, is_black: bool) -> None:
        self._is_black = is_black
        self.is_black_changed.emit(is_black)

    def set_canvas_ratio(self, ratio: str) -> None:
        if ratio not in canvas.CANVAS_SIZES or ratio == self._canvas_ratio:
            return
        self._canvas_ratio = ratio
        self.canvas_changed.emit(ratio)
        self._recompute_pages()
        self.position_changed.emit(self._item_index, self._slide_index)

    def set_font_scale(self, scale: float) -> None:
        scale = max(FONT_SCALE_MIN, min(FONT_SCALE_MAX, scale))
        if scale == self._font_scale:
            return
        self._font_scale = scale
        self.font_scale_changed.emit(scale)
        self._recompute_pages()
        self.position_changed.emit(self._item_index, self._slide_index)

    def increase_font_scale(self) -> None:
        self.set_font_scale(self._font_scale + FONT_SCALE_STEP)

    def decrease_font_scale(self) -> None:
        self.set_font_scale(self._font_scale - FONT_SCALE_STEP)

    def next_slide(self) -> None:
        """Advance one page (Down). Moving past the last page of an item shows a blank screen
        first; pressing Down again from there commits the move to the next item's first page.
        Pressing Down while a blank triggered by Up (previous_slide) is showing just cancels it.
        """
        service = self._service_store.service
        if service is None or not service.items:
            return
        if self._showing_boundary_blank:
            if self._boundary_direction == "end":
                return
            commit_forward = self._boundary_direction == "next"
            self._showing_boundary_blank = False
            self._boundary_direction = None
            if commit_forward:
                self._item_index += 1
                self._slide_index = 0
                self._recompute_pages()
            self.position_changed.emit(self._item_index, self._slide_index)
            return
        if self._slide_index + 1 < len(self._pages):
            self._slide_index += 1
        elif self._item_index + 1 < len(service.items):
            self._showing_boundary_blank = True
            self._boundary_direction = "next"
        else:
            self._showing_boundary_blank = True
            self._boundary_direction = "end"
        self.position_changed.emit(self._item_index, self._slide_index)

    def previous_slide(self) -> None:
        """Go back one page (Up). Moving before the first page of an item shows a blank screen
        first; pressing Up again from there commits the move to the previous item's last page.
        Pressing Up while a blank triggered by Down (next_slide) is showing just cancels it.
        """
        service = self._service_store.service
        if service is None or not service.items:
            return
        if self._showing_boundary_blank:
            commit_backward = self._boundary_direction == "prev"
            self._showing_boundary_blank = False
            self._boundary_direction = None
            if commit_backward:
                self._item_index -= 1
                self._recompute_pages()
                self._slide_index = len(self._pages) - 1
            self.position_changed.emit(self._item_index, self._slide_index)
            return
        if self._slide_index > 0:
            self._slide_index -= 1
        elif self._item_index > 0:
            self._showing_boundary_blank = True
            self._boundary_direction = "prev"
        else:
            return
        self.position_changed.emit(self._item_index, self._slide_index)

    def next_item(self) -> None:
        """Jump straight to the next item's first page, skipping remaining pages."""
        service = self._service_store.service
        if service is None or not service.items:
            return
        if self._item_index + 1 >= len(service.items):
            self._showing_boundary_blank = True
            self._boundary_direction = "end"
            self.position_changed.emit(self._item_index, self._slide_index)
            return
        self._showing_boundary_blank = False
        self._boundary_direction = None
        self._item_index += 1
        self._slide_index = 0
        self._recompute_pages()
        self.position_changed.emit(self._item_index, self._slide_index)

    def previous_item(self) -> None:
        """Jump straight to the previous item's first page."""
        service = self._service_store.service
        if service is None or not service.items or self._item_index == 0:
            return
        self._showing_boundary_blank = False
        self._boundary_direction = None
        self._item_index -= 1
        self._slide_index = 0
        self._recompute_pages()
        self.position_changed.emit(self._item_index, self._slide_index)

    def set_position(self, item_index: int, slide_index: int = 0) -> None:
        self._showing_boundary_blank = False
        self._boundary_direction = None
        self._item_index = item_index
        self._slide_index = slide_index
        self._recompute_pages()
        self.position_changed.emit(self._item_index, self._slide_index)

    def handle_remote_command(self, command: str) -> None:
        if command == "next":
            self.next_slide()
        elif command == "prev":
            self.previous_slide()
        elif command == "toggle_live":
            new_is_live = not self._is_live
            self.set_live(new_is_live)
            self.set_black(not new_is_live)
        elif command == "toggle_black":
            self.set_black(not self._is_black)

