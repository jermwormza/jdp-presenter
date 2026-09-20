"""BibleStore: loaded translation index + the currently active, fully-loaded translation."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.models.bible import BibleIndexEntry, BibleTranslation
from app.persistence import bible_repo
from app.stores.settings_store import SettingsStore


class BibleStore(QObject):
    index_changed = Signal(list)  # list[BibleIndexEntry]
    active_translation_changed = Signal(object)  # BibleTranslation | None

    def __init__(self, settings_store: SettingsStore | None = None) -> None:
        super().__init__()
        self._settings_store = settings_store
        self._index: list[BibleIndexEntry] = []
        self._active: BibleTranslation | None = None
        stored_id = settings_store.get("lastBibleTranslationId", "") if settings_store else ""
        self._preferred_translation_id = stored_id if isinstance(stored_id, str) else ""

    @property
    def index(self) -> list[BibleIndexEntry]:
        return self._index

    @property
    def active_translation(self) -> BibleTranslation | None:
        return self._active

    @property
    def preferred_translation_id(self) -> str:
        return self._preferred_translation_id

    def load_index(self) -> None:
        self._index = bible_repo.list_bible_index()
        self.index_changed.emit(self._index)

    def set_active_translation(self, bible_id: str) -> None:
        entry = next((e for e in self._index if e.id == bible_id), None)
        if entry is None:
            return
        self._active = bible_repo.load_bible(entry.file_name)
        self._preferred_translation_id = bible_id
        if self._settings_store is not None:
            self._settings_store.set("lastBibleTranslationId", bible_id)
        self.active_translation_changed.emit(self._active)
