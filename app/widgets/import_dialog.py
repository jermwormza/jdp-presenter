"""Import Bibles/songs from other church presentation software (Quelea, OpenLP, OpenLyrics, OpenSong, Zefania)."""
from __future__ import annotations

import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.models.song import Song
from app.persistence import bible_repo, song_repo
from app.persistence.library_package import export_library, import_library
from app.stores.bible_store import BibleStore
from app.stores.song_store import SongStore
from app.utils.importers.openlp_songs import parse_openlp_sqlite
from app.utils.importers.openlyrics_songs import parse_openlyrics_archive, parse_openlyrics_xml
from app.utils.importers.opensong_songs import parse_opensong_xml
from app.utils.importers.quelea_songs import parse_quelea_script, parse_quelea_song_pack
from app.utils.importers.zefania_bible import parse_zefania_xml

_FORMATS = {
    "JDP Library package (.jdplibrary)": "jdp-library",
    "Bible — Zefania XML (single file)": "zefania",
    "Songs — Quelea song pack (.qsp)": "quelea-pack",
    "Songs — Quelea .script (single file)": "quelea",
    "Songs — OpenLP database (.sqlite)": "openlp",
    "Songs — OpenLyrics library (.zip)": "openlyrics-archive",
    "Songs — OpenLyrics XML (single file)": "openlyrics",
    "Songs — OpenSong XML (folder)": "opensong",
}


class ImportDialog(QDialog):
    def __init__(self, bible_store: BibleStore, song_store: SongStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import")
        self._bible_store = bible_store
        self._song_store = song_store

        self._format_combo = QComboBox()
        self._format_combo.addItems(list(_FORMATS.keys()))

        self._clear_existing_checkbox = QCheckBox("Replace existing library contents when importing")

        choose_button = QPushButton("Choose && Import…")
        choose_button.clicked.connect(self._choose_and_import)

        backup_button = QPushButton("Backup Libraries…")
        backup_button.clicked.connect(self._backup_library)
        restore_button = QPushButton("Restore Libraries…")
        restore_button.clicked.connect(self._restore_library)
        backup_row = QHBoxLayout()
        backup_row.addWidget(backup_button)
        backup_row.addWidget(restore_button)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Format"))
        layout.addWidget(self._format_combo)
        layout.addWidget(self._clear_existing_checkbox)
        layout.addWidget(choose_button)
        layout.addLayout(backup_row)
        layout.addWidget(self._status_label)

    def _choose_and_import(self) -> None:
        kind = _FORMATS[self._format_combo.currentText()]
        try:
            if kind == "jdp-library":
                self._import_jdp_library()
            elif kind == "zefania":
                self._import_bible()
            elif kind == "quelea":
                self._import_quelea()
            elif kind == "quelea-pack":
                self._import_quelea_pack()
            elif kind == "openlp":
                self._import_openlp()
            elif kind == "openlyrics":
                self._import_openlyrics()
            elif kind == "openlyrics-archive":
                self._import_openlyrics_archive()
            elif kind == "opensong":
                self._import_opensong_folder()
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))

    def _import_bible(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose Zefania XML", "", "XML Files (*.xml)")
        if not path:
            return
        translation = parse_zefania_xml(Path(path).read_text(encoding="utf-8"))
        bible_repo.save_bible(translation)
        self._bible_store.load_index()
        self._status_label.setText(f"Imported Bible: {translation.name} ({len(translation.books)} books)")

    def _import_jdp_library(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose JDP Library",
            "",
            "JDP Library (*.jdplibrary)",
        )
        if not path:
            return
        summary = import_library(path, replace=self._clear_existing_checkbox.isChecked())
        self._reload_libraries()
        self._status_label.setText(
            f"Imported {summary.songs} song(s) and {summary.bibles} Bible(s)"
        )

    def _clear_song_library(self) -> None:
        for song_id in song_repo.list_song_ids():
            song_repo.delete_song(song_id)

    def _save_songs(self, songs: list[Song]) -> int:
        if self._clear_existing_checkbox.isChecked():
            self._clear_song_library()
        now = datetime.now(timezone.utc).isoformat()
        for song in songs:
            song.id = str(uuid.uuid4())
            song.created_at = now
            song.updated_at = now
            song_repo.save_song(song)
        self._song_store.load_songs_async(force=True)
        return len(songs)

    def _backup_library(self) -> None:
        default_name = f"jdp-library-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jdplibrary"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Backup Libraries",
            default_name,
            "JDP Library (*.jdplibrary)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".jdplibrary"):
            file_path += ".jdplibrary"
        try:
            summary = export_library(file_path)
        except OSError as exc:
            QMessageBox.warning(self, "Backup Libraries", str(exc))
            return
        self._status_label.setText(
            f"Backed up {summary.songs} song(s) and {summary.bibles} Bible(s) to {file_path}"
        )

    def _restore_library(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Restore Libraries",
            "",
            "JDP Library (*.jdplibrary);;Legacy Song Backup (*.zip)",
        )
        if not file_path:
            return
        confirm = QMessageBox.question(
            self,
            "Restore Libraries",
            "This replaces the current library contents with the backup. Continue?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            if file_path.lower().endswith(".zip"):
                summary_text = self._restore_legacy_song_zip(file_path)
            else:
                summary = import_library(file_path, replace=True)
                summary_text = f"{summary.songs} song(s) and {summary.bibles} Bible(s)"
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(self, "Restore Libraries", str(exc))
            return
        self._reload_libraries()
        self._status_label.setText(f"Restored {summary_text} from backup")

    def _restore_legacy_song_zip(self, file_path: str) -> str:
        songs: list[Song] = []
        with zipfile.ZipFile(file_path, "r") as archive:
            for name in archive.namelist():
                if name.lower().endswith(".json"):
                    songs.append(Song.from_json_dict(json.loads(archive.read(name).decode("utf-8"))))
        self._clear_song_library()
        for song in songs:
            song_repo.save_song(song)
        return f"{len(songs)} song(s)"

    def _reload_libraries(self) -> None:
        self._bible_store.load_index()
        self._song_store.load_songs_async(force=True)

    def _import_quelea(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose Quelea .script file", "", "Quelea Script (*.script)")
        if not path:
            return
        songs = parse_quelea_script(Path(path).read_text(encoding="utf-8", errors="replace"))
        count = self._save_songs(songs)
        self._status_label.setText(f"Imported {count} song(s) from Quelea script")

    def _import_quelea_pack(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Quelea song pack", "", "Quelea Song Pack (*.qsp)"
        )
        if not path:
            return
        self._status_label.setText("Reading Quelea song pack…")
        QApplication.processEvents()
        songs, failures = parse_quelea_song_pack(path)
        count = self._save_songs(songs)
        self._set_song_archive_status(count, failures, "Quelea song pack")

    def _import_openlp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose OpenLP database", "", "OpenLP Database (*.sqlite *.db);;All Files (*)"
        )
        if not path:
            return
        songs = parse_openlp_sqlite(path)
        count = self._save_songs(songs)
        self._status_label.setText(f"Imported {count} song(s) from OpenLP database")

    def _import_openlyrics(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose OpenLyrics XML", "", "XML Files (*.xml)")
        if not path:
            return
        song = parse_openlyrics_xml(Path(path).read_text(encoding="utf-8"))
        count = self._save_songs([song])
        self._status_label.setText(f"Imported {count} song from OpenLyrics XML")

    def _import_openlyrics_archive(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose OpenLyrics library", "", "OpenLyrics Library (*.zip)"
        )
        if not path:
            return
        self._status_label.setText("Reading OpenLyrics library…")
        QApplication.processEvents()
        songs, failures = parse_openlyrics_archive(path)
        count = self._save_songs(songs)
        self._set_song_archive_status(count, failures, "OpenLyrics library")

    def _set_song_archive_status(self, count: int, failures: int, source: str) -> None:
        message = f"Imported {count} song(s) from {source}"
        if failures:
            message += f" ({failures} XML file(s) could not be imported)"
        self._status_label.setText(message)

    def _import_opensong_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose OpenSong folder")
        if not folder:
            return
        songs: list[Song] = []
        failures = 0
        for path in sorted(Path(folder).rglob("*")):
            if not path.is_file() or path.suffix.lower() not in ("", ".xml"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                if "<song" not in text:
                    continue
                songs.append(parse_opensong_xml(text))
            except Exception:
                failures += 1
        count = self._save_songs(songs)
        message = f"Imported {count} song(s) from OpenSong folder"
        if failures:
            message += f" ({failures} file(s) failed to parse)"
        self._status_label.setText(message)
