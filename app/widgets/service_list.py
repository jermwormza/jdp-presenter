"""Drag-and-drop ordered list of the current service's items."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QDialog, QListWidget, QListWidgetItem, QMenu

from app.models.service import AudioItem, ImageItem, ScriptureItem, Slide, SongItem, VideoItem
from app.persistence import bible_repo, media_library_repo, song_repo
from app.stores.output_store import OutputStore
from app.stores.service_store import ServiceStore
from app.stores.song_store import SongStore
from app.utils.icons import media_icon, scripture_icon, song_icon, text_icon
from app.widgets.song_editor import SongEditor

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
_ScaleMode = Literal["fit", "original", "fill_width", "fill_height"]

_ITEM_ICONS = {
    "scripture": scripture_icon,
    "song": song_icon,
    "text": text_icon,
    "image": media_icon,
    "video": media_icon,
    "audio": media_icon,
}


class ServiceList(QListWidget):
    def __init__(
        self,
        service_store: ServiceStore,
        output_store: OutputStore,
        song_store: SongStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._store = service_store
        self._output_store = output_store
        self._song_store = song_store
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        service_store.service_changed.connect(self._on_service_changed)
        service_store.selected_item_changed.connect(self._on_selected_item_changed)
        output_store.position_changed.connect(self._on_position_changed)
        self.currentRowChanged.connect(self._on_row_selected)
        self.itemDoubleClicked.connect(self._on_row_double_clicked)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._on_service_changed(service_store.service)

    def _on_service_changed(self, service) -> None:
        self.blockSignals(True)
        self.clear()
        selected_item_id = self._store.selected_item_id
        selected_row = -1
        if service is not None:
            for row, item in enumerate(service.items):
                icon_factory = _ITEM_ICONS.get(item.type)
                label = item.title
                if isinstance(item, ScriptureItem):
                    version = bible_repo.resolve_bible_label(item.bible)
                    if version:
                        label = f"{item.reference or item.title} ({version})"
                list_item = QListWidgetItem(label)
                list_item.setData(Qt.ItemDataRole.UserRole, item.id)
                if icon_factory is not None:
                    list_item.setIcon(icon_factory())
                else:
                    list_item.setText(f"[{item.type}] {item.title}")
                self.addItem(list_item)
                if item.id == selected_item_id:
                    selected_row = row
            # Restore the highlighted row to match the actual current item — otherwise Qt can
            # silently default the selection to row 0 after a rebuild (e.g. on any edit/add/remove),
            # and a later focus change fires currentRowChanged(0), resetting playback position.
            if selected_row < 0 and 0 <= self._output_store.item_index < len(service.items):
                selected_row = self._output_store.item_index
            if selected_row < 0 and service.items:
                selected_row = 0
            if selected_row >= 0:
                self.setCurrentRow(selected_row)
        self.blockSignals(False)
        if service is not None and selected_row >= 0:
            self._store.select_item(service.items[selected_row].id)

    def _on_position_changed(self, item_index: int, _slide_index: int) -> None:
        if 0 <= item_index < self.count() and self.currentRow() != item_index:
            self.blockSignals(True)
            self.setCurrentRow(item_index)
            self.blockSignals(False)

    def _on_selected_item_changed(self, item_id: str | None) -> None:
        for row in range(self.count()):
            if self.item(row).data(Qt.ItemDataRole.UserRole) == item_id:
                if self.currentRow() != row:
                    self.blockSignals(True)
                    self.setCurrentRow(row)
                    self.blockSignals(False)
                return
        if item_id is None:
            self.clearSelection()

    def _on_row_selected(self, row: int) -> None:
        service = self._store.service
        if service is None or row < 0 or row >= len(service.items):
            return
        self._store.select_item(service.items[row].id)
        self._output_store.set_position(row, 0)

    def _on_row_double_clicked(self, item: QListWidgetItem) -> None:
        row = self.row(item)
        service = self._store.service
        if service is None or row < 0 or row >= len(service.items):
            return
        self._store.select_item(service.items[row].id)
        self._output_store.set_position(row, 0)
        if self._output_store.is_black:
            self._output_store.set_live(True)
            self._output_store.set_black(False)

    def move_selected(self, direction: str) -> None:
        item_id = self._store.selected_item_id
        service = self._store.service
        if item_id is None or service is None:
            return
        self._store.move_item(item_id, direction)
        new_index = next(
            (index for index, item in enumerate(service.items) if item.id == item_id), -1
        )
        if new_index >= 0:
            self._output_store.set_position(new_index, 0)

    def _show_context_menu(self, position) -> None:
        list_item = self.itemAt(position)
        service = self._store.service
        if list_item is None or service is None:
            return
        item_id = list_item.data(Qt.ItemDataRole.UserRole)
        item = next((candidate for candidate in service.items if candidate.id == item_id), None)
        if not isinstance(item, SongItem):
            return
        menu = QMenu(self)
        edit_action = menu.addAction("Edit Song…")
        if menu.exec(self.viewport().mapToGlobal(position)) == edit_action:
            self._edit_song(item)

    def _edit_song(self, item: SongItem) -> None:
        try:
            song = song_repo.load_song(item.song_id)
        except (FileNotFoundError, OSError, ValueError):
            return
        editor = SongEditor(song, parent=self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        edited_song = editor.result_song()
        self._song_store.save_song(edited_song)
        self._store.refresh_song_items(edited_song)

    @staticmethod
    def _supported_file(path: Path) -> bool:
        suffix = path.suffix.casefold()
        return suffix in _IMAGE_EXTENSIONS | _VIDEO_EXTENSIONS | _AUDIO_EXTENSIONS

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 (Qt override)
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() and self._supported_file(Path(url.toLocalFile()))
            for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 (Qt override)
        if event.mimeData().hasUrls():
            paths = [
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.isLocalFile() and self._supported_file(Path(url.toLocalFile()))
            ]
            if paths:
                target = self.itemAt(event.position().toPoint())
                if target is not None:
                    self._store.select_item(target.data(Qt.ItemDataRole.UserRole))
                for path in paths:
                    item = self._media_item(path)
                    self._store.add_item(item)
                    self._store.select_item(item.id)
                event.acceptProposedAction()
                return
        current_item = self.currentItem()
        current_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item is not None else None
        super().dropEvent(event)
        new_order = [self.item(row).data(Qt.ItemDataRole.UserRole) for row in range(self.count())]
        self._store.reorder_items(new_order)
        if current_id is not None and current_id in new_order:
            self._output_store.set_position(new_order.index(current_id), 0)

    @staticmethod
    def _media_item(path: Path):
        slide = Slide(id=str(uuid.uuid4()), content=path.name)
        common = {"id": str(uuid.uuid4()), "title": path.name, "path": str(path), "slides": [slide]}
        suffix = path.suffix.casefold()
        scale_mode = cast(_ScaleMode, media_library_repo.get_scale_mode(str(path)))
        if suffix in _IMAGE_EXTENSIONS:
            return ImageItem(**common, scale_mode=scale_mode)
        if suffix in _VIDEO_EXTENSIONS:
            return VideoItem(**common, auto_play=True, scale_mode=scale_mode)
        return AudioItem(**common, auto_play=True)
