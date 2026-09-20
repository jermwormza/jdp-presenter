"""ServiceStore: shared, signal-based state for the current Service.

See .github/instructions/state-store.instructions.md for the pattern this follows.
"""
from __future__ import annotations

import uuid

from PySide6.QtCore import QObject, Signal

from app.models.service import Service, ServiceItem, Slide, SongItem
from app.models.song import Song
from app.utils.song_utils import resolve_verse_order


class ServiceStore(QObject):
    service_changed = Signal(object)  # Service | None
    selected_item_changed = Signal(object)  # str | None
    dirty_changed = Signal(bool)  # True if service has unsaved changes

    def __init__(self) -> None:
        super().__init__()
        self._service: Service | None = None
        self._selected_item_id: str | None = None
        self._dirty: bool = False

    @property
    def service(self) -> Service | None:
        return self._service

    @property
    def selected_item_id(self) -> str | None:
        return self._selected_item_id

    @property
    def dirty(self) -> bool:
        return self._dirty

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty != dirty:
            self._dirty = dirty
            self.dirty_changed.emit(dirty)

    def set_service(self, service: Service | None) -> None:
        self._service = service
        self._selected_item_id = None
        self._set_dirty(False)  # Loading a service is not a dirty state
        self.service_changed.emit(service)
        self.selected_item_changed.emit(None)

    def touch(self) -> None:
        """Re-emit service_changed for out-of-band mutations (e.g. ThemeStore editing service.theme)."""
        self._set_dirty(True)
        self.service_changed.emit(self._service)

    def select_item(self, item_id: str | None) -> None:
        self._selected_item_id = item_id
        self.selected_item_changed.emit(item_id)

    def add_item(self, item: ServiceItem) -> None:
        if self._service is None:
            return
        selected_index = next(
            (
                index
                for index, existing_item in enumerate(self._service.items)
                if existing_item.id == self._selected_item_id
            ),
            -1,
        )
        if selected_index == -1:
            self._service.items.append(item)
        else:
            self._service.items.insert(selected_index + 1, item)
        self._set_dirty(True)
        self.service_changed.emit(self._service)

    def update_item(self, item_id: str, **updates: object) -> None:
        if self._service is None:
            return
        for item in self._service.items:
            if item.id == item_id:
                for key, value in updates.items():
                    setattr(item, key, value)
                break
        self._set_dirty(True)
        self.service_changed.emit(self._service)

    def remove_item(self, item_id: str) -> None:
        if self._service is None:
            return
        self._service.items = [i for i in self._service.items if i.id != item_id]
        if self._selected_item_id == item_id:
            self.select_item(None)
        self._set_dirty(True)
        self.service_changed.emit(self._service)

    def move_item(self, item_id: str, direction: str) -> None:
        if self._service is None:
            return
        items = self._service.items
        index = next((i for i, it in enumerate(items) if it.id == item_id), -1)
        if index == -1:
            return
        if direction == "up" and index == 0:
            return
        if direction == "down" and index == len(items) - 1:
            return
        new_index = index - 1 if direction == "up" else index + 1
        items[index], items[new_index] = items[new_index], items[index]
        self._set_dirty(True)
        self.service_changed.emit(self._service)

    def refresh_song_items(self, song: Song) -> None:
        """Refresh every scheduled instance after its library song is edited."""
        if self._service is None:
            return
        changed = False
        for item in self._service.items:
            if not isinstance(item, SongItem) or item.song_id != song.id:
                continue
            order = item.selected_verses or song.verse_order or [verse.label for verse in song.verses]
            verses = resolve_verse_order(song.verses, order)
            if not verses:
                order = song.verse_order or [verse.label for verse in song.verses]
                verses = resolve_verse_order(song.verses, order)
            item.title = song.title
            item.selected_verses = order
            item.slides = [
                Slide(id=str(uuid.uuid4()), content=verse.text, label=verse.label)
                for verse in verses
            ]
            changed = True
        if changed:
            self._set_dirty(True)
            self.service_changed.emit(self._service)

    def reorder_items(self, item_ids: list[str]) -> None:
        """Reorder items to match item_ids (e.g. after a drag-and-drop reorder in the UI)."""
        if self._service is None:
            return
        by_id = {item.id: item for item in self._service.items}
        reordered = [by_id[item_id] for item_id in item_ids if item_id in by_id]
        if len(reordered) != len(self._service.items):
            return  # ids didn't line up 1:1 with current items — leave order untouched
        self._service.items = reordered
        self._set_dirty(True)
        self.service_changed.emit(self._service)

    def mark_saved(self) -> None:
        """Call after successfully saving the service to disk."""
        self._set_dirty(False)
