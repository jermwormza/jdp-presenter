"""Unified schedule search for quickly adding songs, scripture, and media."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from app.models.service import (
    AudioItem,
    ImageItem,
    ScriptureItem,
    ServiceItem,
    Slide,
    SongItem,
    VideoItem,
)
from app.models.song import Song
from app.persistence import media_library_repo
from app.persistence.paths import MEDIA_AUDIO_DIR, MEDIA_IMAGES_DIR, MEDIA_VIDEOS_DIR
from app.stores.bible_store import BibleStore
from app.stores.service_store import ServiceStore
from app.stores.song_store import SongStore
from app.utils.bible_utils import find_verses, format_reference, parse_reference
from app.utils.icons import media_icon, scripture_icon, song_icon
from app.utils.song_utils import resolve_verse_order

_TRANSLATION_RE = re.compile(r"^(?P<reference>.+?)\s*\((?P<translation>[^()]+)\)\s*$")
_MEDIA_DIRECTORIES = (
    ("image", MEDIA_IMAGES_DIR, {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}),
    ("video", MEDIA_VIDEOS_DIR, {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}),
    ("audio", MEDIA_AUDIO_DIR, {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}),
)
_RESULT_LIMIT = 30
_ScaleMode = Literal["fit", "original", "fill_width", "fill_height"]


@dataclass(frozen=True)
class QuickAddResult:
    kind: str
    label: str
    detail: str
    value: str


class QuickAddSearch(QWidget):
    input_focus_changed = Signal(bool)

    def __init__(
        self,
        service_store: ServiceStore,
        song_store: SongStore,
        bible_store: BibleStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service_store = service_store
        self._song_store = song_store
        self._bible_store = bible_store
        self._results: list[QuickAddResult] = []

        self._search = QLineEdit()
        self._search.setClearButtonEnabled(True)
        self._search.setPlaceholderText("Quick add: song, Scripture reference (Version), or media")
        self._search.setAccessibleName("Quick add to schedule")
        self._search.installEventFilter(self)

        self._popup = QFrame(
            self,
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint,
        )
        self._popup.setObjectName("QuickAddPopup")
        self._popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._list = QListWidget()
        self._list.setMaximumHeight(220)
        self._status = QLabel()
        self._status.setObjectName("QuickAddStatus")
        self._status.hide()

        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(1, 1, 1, 1)
        popup_layout.setSpacing(0)
        popup_layout.addWidget(self._list)
        popup_layout.addWidget(self._status)
        self._popup.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(self._search)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(140)
        self._timer.timeout.connect(self._refresh_results)
        self._search.textChanged.connect(lambda _text: self._timer.start())
        self._list.itemActivated.connect(lambda _item: self._insert_current())
        song_store.songs_changed.connect(lambda _songs: self._refresh_results())
        if not song_store.songs:
            song_store.load_songs_async()
        if not bible_store.index:
            bible_store.load_index()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt override)
        if watched is self._search and event.type() == QEvent.Type.FocusIn:
            self.input_focus_changed.emit(True)
        elif watched is self._search and event.type() == QEvent.Type.FocusOut:
            self.input_focus_changed.emit(False)
        elif watched is self._search and event.type() == QEvent.Type.KeyPress:
            key_event = event if isinstance(event, QKeyEvent) else None
            if key_event is not None and key_event.key() in (
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            ):
                self._insert_first_result()
                return True
            if key_event is not None and self._results:
                if key_event.key() == Qt.Key.Key_Down:
                    next_row = min(self._list.currentRow() + 1, len(self._results) - 1)
                    self._list.setCurrentRow(next_row)
                    return True
                if key_event.key() == Qt.Key.Key_Up:
                    self._list.setCurrentRow(max(self._list.currentRow() - 1, 0))
                    return True
            if key_event is not None and key_event.key() == Qt.Key.Key_Escape:
                self._search.clear()
                return True
        return super().eventFilter(watched, event)

    def _refresh_results(self) -> None:
        query = self._search.text().strip()
        self._results = []
        self._list.clear()
        if len(query) < 2:
            self._popup.hide()
            return

        scripture_result = self._scripture_result(query)
        if scripture_result is not None:
            self._results.append(scripture_result)

        needle = query.casefold()
        for song in self._song_store.songs:
            searchable = f"{song.title} {song.author}".casefold()
            if needle in searchable:
                self._results.append(
                    QuickAddResult("song", song.title, song.author or "Song", song.id)
                )
                if len(self._results) >= _RESULT_LIMIT:
                    break

        if len(self._results) < _RESULT_LIMIT:
            for kind, directory, extensions in _MEDIA_DIRECTORIES:
                if not directory.exists():
                    continue
                for path in directory.rglob("*"):
                    if (
                        path.is_file()
                        and path.suffix.casefold() in extensions
                        and needle in path.stem.casefold()
                    ):
                        self._results.append(
                            QuickAddResult(kind, path.stem, kind.title(), str(path))
                        )
                        if len(self._results) >= _RESULT_LIMIT:
                            break
                if len(self._results) >= _RESULT_LIMIT:
                    break

        for index, result in enumerate(self._results):
            item = QListWidgetItem(f"{result.label}  ·  {result.detail}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            if result.kind == "scripture":
                item.setIcon(scripture_icon())
            elif result.kind == "song":
                item.setIcon(song_icon())
            else:
                item.setIcon(media_icon())
            self._list.addItem(item)

        self._list.setVisible(bool(self._results))
        self._status.setText("No matching songs, scripture, or media" if not self._results else "")
        self._status.setVisible(not self._results)
        if self._results:
            self._list.setCurrentRow(0)
            row_height = max(self._list.sizeHintForRow(0), 24)
            self._list.setFixedHeight(min(220, row_height * min(len(self._results), 8) + 2))
        self._show_popup()

    def _show_popup(self) -> None:
        self._popup.setFixedWidth(self._search.width())
        self._popup.adjustSize()
        position = self._search.mapToGlobal(QPoint(0, self._search.height()))
        self._popup.move(position)
        self._popup.show()
        self._popup.raise_()

    def _scripture_result(self, query: str) -> QuickAddResult | None:
        match = _TRANSLATION_RE.match(query)
        reference = match.group("reference") if match else query
        requested = match.group("translation").casefold() if match else ""
        if not any(character.isdigit() for character in reference):
            return None
        try:
            parse_reference(reference)
        except ValueError:
            return None

        entries = self._bible_store.index
        if requested:
            entry = next(
                (
                    candidate
                    for candidate in entries
                    if requested in (candidate.abbreviation.casefold(), candidate.name.casefold())
                ),
                None,
            )
        else:
            active_translation = self._bible_store.active_translation
            default_id = (
                active_translation.id
                if active_translation is not None
                else self._bible_store.preferred_translation_id
            )
            entry = next((candidate for candidate in entries if candidate.id == default_id), None)
            entry = entry or (entries[0] if entries else None)
        if entry is None:
            return None
        return QuickAddResult(
            "scripture",
            reference.strip(),
            f"Scripture · {entry.abbreviation}",
            entry.id,
        )

    def _insert_current(self) -> None:
        row = self._list.currentRow()
        if self._service_store.service is None or row < 0 or row >= len(self._results):
            return
        result = self._results[row]
        inserted = False
        if result.kind == "scripture":
            inserted = self._insert_scripture(result)
        elif result.kind == "song":
            inserted = self._insert_song(result.value)
        else:
            inserted = self._insert_media(result)
        if inserted:
            self._search.clear()
            self._popup.hide()
            self._search.setFocus()

    def _insert_first_result(self) -> None:
        self._timer.stop()
        self._refresh_results()
        if not self._results:
            return
        self._list.setCurrentRow(0)
        self._insert_current()

    def _insert_scripture(self, result: QuickAddResult) -> bool:
        self._bible_store.set_active_translation(result.value)
        translation = self._bible_store.active_translation
        if translation is None:
            return False
        parsed = parse_reference(result.label)
        verses = find_verses(translation, parsed)
        if not verses:
            return False
        reference = format_reference(parsed, verses[0].book)
        return self._add_and_select(
            ScriptureItem(
                id=str(uuid.uuid4()),
                title=reference,
                bible=translation.id,
                reference=reference,
                verses=verses,
                slides=[
                    Slide(
                        id=str(uuid.uuid4()),
                        content="\n".join(verse.text for verse in verses),
                    )
                ],
            )
        )

    def _insert_song(self, song_id: str) -> bool:
        song: Song | None = next(
            (item for item in self._song_store.songs if item.id == song_id), None
        )
        if song is None:
            return False
        order = song.verse_order or [verse.label for verse in song.verses]
        slides = [
            Slide(id=str(uuid.uuid4()), content=verse.text, label=verse.label)
            for verse in resolve_verse_order(song.verses, order)
        ]
        if not slides:
            return False
        return self._add_and_select(
            SongItem(
                id=str(uuid.uuid4()),
                title=song.title,
                song_id=song.id,
                selected_verses=order,
                slides=slides,
            )
        )

    def _insert_media(self, result: QuickAddResult) -> bool:
        slide = Slide(id=str(uuid.uuid4()), content=Path(result.value).name)
        scale_mode = cast(_ScaleMode, media_library_repo.get_scale_mode(result.value))
        if result.kind == "image":
            item = ImageItem(
                id=str(uuid.uuid4()),
                title=result.label,
                path=result.value,
                slides=[slide],
                scale_mode=scale_mode,
            )
        elif result.kind == "video":
            item = VideoItem(
                id=str(uuid.uuid4()),
                title=result.label,
                path=result.value,
                slides=[slide],
                auto_play=True,
                scale_mode=scale_mode,
            )
        else:
            item = AudioItem(
                id=str(uuid.uuid4()),
                title=result.label,
                path=result.value,
                slides=[slide],
                auto_play=True,
            )
        return self._add_and_select(item)

    def _add_and_select(self, item: ServiceItem) -> bool:
        self._service_store.add_item(item)
        self._service_store.select_item(item.id)
        return True