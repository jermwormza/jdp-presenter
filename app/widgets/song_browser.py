"""Song library browser: search, pick a song + verse order, add it to the current service."""
from __future__ import annotations

import re
import uuid

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.models.service import Slide, SongItem
from app.models.song import Song
from app.models.theme import default_theme
from app.stores.service_store import ServiceStore
from app.stores.song_store import SongStore
from app.utils.song_utils import resolve_verse_order
from app.widgets.song_editor import SongEditor

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation, so search/sort ignore things like apostrophes."""
    return _PUNCTUATION_RE.sub("", text).lower()


class SongBrowser(QDialog):
    def __init__(self, song_store: SongStore, service_store: ServiceStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Song Library")
        self.resize(900, 550)
        self._song_store = song_store
        self._service_store = service_store
        self._pending_songs: list[Song] = []
        self._pending_song_index = 0
        self._list_build_timer = QTimer(self)
        self._list_build_timer.setInterval(0)
        self._list_build_timer.timeout.connect(self._append_song_batch)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search title or author…")
        self._search_edit.textChanged.connect(self._refresh_list)

        self._list = QListWidget()
        self._loading_label = QLabel()
        self._loading_progress = QProgressBar()
        self._loading_progress.setTextVisible(False)
        self._loading_progress.setMaximumWidth(140)
        self._loading_label.hide()
        self._loading_progress.hide()
        loading_row = QHBoxLayout()
        loading_row.addWidget(self._loading_label)
        loading_row.addStretch(1)
        loading_row.addWidget(self._loading_progress)
        self._verse_order_edit = QLineEdit()
        self._verse_order_edit.setPlaceholderText("Verse order, e.g. v1 c v2 c")
        self._verse_order_edit.textChanged.connect(self._update_preview)

        self._preview_label = QLabel()
        self._preview_label.setWordWrap(True)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setWidget(self._preview_label)

        new_button = QPushButton("New Song")
        new_button.clicked.connect(self._new_song)
        edit_button = QPushButton("Edit Song…")
        edit_button.clicked.connect(self._edit_song)
        delete_button = QPushButton("Delete…")
        delete_button.clicked.connect(self._delete_song)
        add_button = QPushButton("Add to Service")
        add_button.clicked.connect(self._add_to_service)

        button_row = QHBoxLayout()
        button_row.addWidget(new_button)
        button_row.addWidget(edit_button)
        button_row.addWidget(delete_button)
        button_row.addWidget(add_button)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        left_layout.addWidget(self._search_edit)
        left_layout.addLayout(loading_row)
        left_layout.addWidget(self._list, stretch=1)
        left_layout.addWidget(QLabel("Verse order"))
        left_layout.addWidget(self._verse_order_edit)
        left_layout.addLayout(button_row)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        right_layout.addWidget(QLabel("Preview (all verses, in order)"))
        right_layout.addWidget(self._preview_scroll, stretch=1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 580])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        song_store.songs_changed.connect(self._refresh_list)
        song_store.loading_changed.connect(self._on_loading_changed)
        song_store.load_failed.connect(self._on_load_failed)
        self._list.currentItemChanged.connect(self._on_selection_changed)

        song_store.load_songs_async()

    def _refresh_list(self, *_args) -> None:
        self._list_build_timer.stop()
        query = _normalize(self._search_edit.text().strip())
        self._list.clear()
        if self._song_store.is_loading:
            self._show_loading("Loading songs…")
            return
        songs = []
        for song in sorted(self._song_store.songs, key=lambda candidate: _normalize(candidate.title)):
            haystack = _normalize(f"{song.title} {song.author or ''}")
            if query and query not in haystack:
                continue
            songs.append(song)
        self._pending_songs = songs
        self._pending_song_index = 0
        if not songs:
            self._hide_loading()
            return
        self._loading_label.setText("Building song list…")
        self._loading_label.show()
        self._loading_progress.setRange(0, len(songs))
        self._loading_progress.setValue(0)
        self._loading_progress.show()
        self._list.setCursor(Qt.CursorShape.WaitCursor)
        self._list_build_timer.start()

    def _append_song_batch(self) -> None:
        end = min(self._pending_song_index + 150, len(self._pending_songs))
        self._list.setUpdatesEnabled(False)
        try:
            for song in self._pending_songs[self._pending_song_index:end]:
                list_item = QListWidgetItem(song.title)
                list_item.setData(Qt.ItemDataRole.UserRole, song.id)
                self._list.addItem(list_item)
        finally:
            self._list.setUpdatesEnabled(True)
        self._pending_song_index = end
        self._loading_progress.setValue(end)
        if end >= len(self._pending_songs):
            self._list_build_timer.stop()
            self._hide_loading()
            if self._list.currentItem() is None and self._list.count():
                self._list.setCurrentRow(0)

    def _on_loading_changed(self, is_loading: bool) -> None:
        if is_loading:
            self._show_loading("Loading songs…")
        elif not self._list_build_timer.isActive():
            self._hide_loading()

    def _on_load_failed(self, message: str) -> None:
        self._list_build_timer.stop()
        self._loading_label.setText("Could not load the song library")
        self._loading_label.setToolTip(message)
        self._loading_label.show()
        self._loading_progress.hide()
        self._list.unsetCursor()

    def _show_loading(self, message: str) -> None:
        self._loading_label.setText(message)
        self._loading_label.setToolTip("")
        self._loading_label.show()
        self._loading_progress.setRange(0, 0)
        self._loading_progress.show()
        self._list.setCursor(Qt.CursorShape.WaitCursor)

    def _hide_loading(self) -> None:
        self._loading_label.hide()
        self._loading_progress.hide()
        self._list.unsetCursor()

    def _on_selection_changed(self, current: QListWidgetItem | None, _previous) -> None:
        if current is None:
            self._song_store.select_song(None)
            self._update_preview()
            return
        song_id = current.data(Qt.ItemDataRole.UserRole)
        self._song_store.select_song(song_id)
        song = self._song_store.selected_song
        if song is not None:
            order = song.verse_order or [v.label for v in song.verses]
            self._verse_order_edit.setText(" ".join(order))
        self._update_preview()

    def _current_theme(self):
        service = self._service_store.service
        return service.theme if service is not None else default_theme()

    def _update_preview(self, *_args) -> None:
        song = self._song_store.selected_song
        if song is None:
            self._preview_label.setText("")
            return
        order = self._verse_order_edit.text().split() or song.verse_order or [v.label for v in song.verses]
        resolved_verses = resolve_verse_order(song.verses, order)
        if not resolved_verses and song.verses:
            resolved_verses = song.verses
        verse_texts = [verse.text for verse in resolved_verses if verse.text.strip()]
        if not verse_texts:
            self._preview_label.setStyleSheet("")
            self._preview_label.setText("This song has no lyric content. Re-import it from the source library.")
            return

        theme = self._current_theme().song.lyrics
        self._preview_label.setStyleSheet(
            f"background-color: {self._current_theme().background.color}; color: {theme.color}; "
            f"font-family: '{theme.font_family}'; font-size: 20px; padding: 16px;"
        )
        self._preview_scroll.setStyleSheet(f"background-color: {self._current_theme().background.color};")
        self._preview_label.setText("\n\n".join(verse_texts))

    def _new_song(self) -> None:
        editor = SongEditor(parent=self)
        if editor.exec() == QDialog.DialogCode.Accepted:
            self._song_store.save_song(editor.result_song())

    def _edit_song(self) -> None:
        song = self._song_store.selected_song
        if song is None:
            QMessageBox.warning(self, "Edit Song", "Select a song first.")
            return
        editor = SongEditor(song, parent=self)
        if editor.exec() == QDialog.DialogCode.Accepted:
            self._song_store.save_song(editor.result_song())

    def _delete_song(self) -> None:
        song = self._song_store.selected_song
        if song is None:
            QMessageBox.warning(self, "Delete Song", "Select a song first.")
            return
        confirm = QMessageBox.question(
            self, "Delete Song", f'Delete "{song.title}" from the library? This cannot be undone.'
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._song_store.delete_song(song.id)

    def _add_to_service(self) -> None:
        if self._service_store.service is None:
            QMessageBox.warning(self, "Add Song", "No service is open.")
            return
        song = self._song_store.selected_song
        if song is None:
            QMessageBox.warning(self, "Add Song", "Select a song first.")
            return

        order = self._verse_order_edit.text().split() or song.verse_order or [v.label for v in song.verses]
        slides = []
        for verse in resolve_verse_order(song.verses, order):
            slides.append(Slide(id=str(uuid.uuid4()), content=verse.text, label=verse.label))

        if not slides:
            QMessageBox.warning(self, "Add Song", "No matching verses for that verse order.")
            return

        self._service_store.add_item(
            SongItem(id=str(uuid.uuid4()), title=song.title, song_id=song.id, selected_verses=order, slides=slides)
        )
        self.accept()

