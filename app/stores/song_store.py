"""SongStore: library of songs loaded from disk, plus the currently selected song."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.models.song import Song
from app.persistence import song_repo


class _SongLoader(QObject):
    loaded = Signal(list)
    failed = Signal(str)
    finished = Signal()

    @Slot()
    def run(self) -> None:
        try:
            self.loaded.emit(song_repo.load_all_songs())
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class SongStore(QObject):
    songs_changed = Signal(list)  # list[Song]
    selected_song_changed = Signal(object)  # Song | None
    loading_changed = Signal(bool)
    load_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._songs: list[Song] = []
        self._selected_song: Song | None = None
        self._is_loading = False
        self._load_thread: QThread | None = None
        self._load_worker: _SongLoader | None = None

    @property
    def songs(self) -> list[Song]:
        return self._songs

    @property
    def selected_song(self) -> Song | None:
        return self._selected_song

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    def load_songs(self) -> None:
        self._songs = song_repo.load_all_songs()
        self.songs_changed.emit(self._songs)

    def load_songs_async(self, force: bool = False) -> None:
        if self._is_loading:
            return
        if self._songs and not force:
            self.songs_changed.emit(self._songs)
            return

        self._is_loading = True
        self.loading_changed.emit(True)
        thread = QThread(self)
        worker = _SongLoader()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.loaded.connect(self._on_songs_loaded)
        worker.failed.connect(self._on_songs_load_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_load_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._load_thread = thread
        self._load_worker = worker
        thread.start()

    @Slot(list)
    def _on_songs_loaded(self, songs: list[Song]) -> None:
        self._songs = songs
        self._is_loading = False
        self.loading_changed.emit(False)
        self.songs_changed.emit(self._songs)

    @Slot(str)
    def _on_songs_load_failed(self, message: str) -> None:
        self._is_loading = False
        self.loading_changed.emit(False)
        self.load_failed.emit(message)

    @Slot()
    def _on_load_thread_finished(self) -> None:
        self._load_thread = None
        self._load_worker = None

    def select_song(self, song_id: str | None) -> None:
        self._selected_song = next((s for s in self._songs if s.id == song_id), None)
        self.selected_song_changed.emit(self._selected_song)

    def save_song(self, song: Song) -> None:
        song_repo.save_song(song)
        self.load_songs_async(force=True)

    def delete_song(self, song_id: str) -> None:
        song_repo.delete_song(song_id)
        if self._selected_song is not None and self._selected_song.id == song_id:
            self.select_song(None)
        self.load_songs_async(force=True)
