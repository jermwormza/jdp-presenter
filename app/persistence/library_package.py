"""Portable JDP library packages using OpenLyrics and Zefania XML."""
from __future__ import annotations

import json
import re
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.models.bible import BibleTranslation
from app.models.song import Song
from app.persistence import bible_repo, song_repo
from app.persistence.paths import DEFAULT_DATA_DIR
from app.utils.importers.openlyrics_songs import parse_openlyrics_xml, serialize_openlyrics
from app.utils.importers.zefania_bible import parse_zefania_xml, serialize_zefania

PACKAGE_FORMAT = "jdp-library"
PACKAGE_VERSION = 1
STARTER_PACKAGE_NAME = "starter-library.jdplibrary"
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class LibraryPackageSummary:
    songs: int
    bibles: int


@dataclass(frozen=True)
class LegacyLibraryState:
    songs: int
    bibles: int

    @property
    def requires_decision(self) -> bool:
        return self.songs > 0 or self.bibles > 0


class LibraryPackageError(ValueError):
    pass


def detect_legacy_library() -> LegacyLibraryState:
    """Find legacy JSON libraries that have not yet been migrated to SQLite."""
    songs_directory = song_repo.database_path().parent
    bibles_directory = bible_repo.database_path().parent
    legacy_songs = (
        len(list(songs_directory.glob("*.json")))
        if not song_repo.database_path().exists()
        else 0
    )
    legacy_bibles = 0
    if not bible_repo.database_path().exists():
        index_path = bibles_directory / "index.json"
        if index_path.exists():
            try:
                payload = json.loads(index_path.read_text(encoding="utf-8"))
                legacy_bibles = len(payload) if isinstance(payload, list) else 1
            except (OSError, json.JSONDecodeError):
                legacy_bibles = 1
    return LegacyLibraryState(songs=legacy_songs, bibles=legacy_bibles)


def convert_legacy_library() -> LibraryPackageSummary:
    """Convert legacy JSON in place, retaining the original files as rollback data."""
    state = detect_legacy_library()
    if state.songs:
        song_repo.list_song_ids()
    if state.bibles:
        bible_repo.list_bible_index()
    bootstrap_starter_library()
    return LibraryPackageSummary(
        songs=len(song_repo.list_song_ids()),
        bibles=len(bible_repo.list_bible_index()),
    )


def replace_with_starter_library(source: str | Path | None = None) -> LibraryPackageSummary:
    """Use the packaged library while retaining legacy JSON files on disk."""
    source_path = Path(source) if source is not None else DEFAULT_DATA_DIR / STARTER_PACKAGE_NAME
    if not source_path.exists():
        raise LibraryPackageError(f"Starter library was not found: {source_path}")
    song_repo.initialize_empty_database()
    bible_repo.initialize_empty_database()
    return import_library(source_path, replace=True)


def bootstrap_starter_library(source: str | Path | None = None) -> LibraryPackageSummary:
    """Import missing runtime libraries from the installed starter package."""
    source_path = Path(source) if source is not None else DEFAULT_DATA_DIR / STARTER_PACKAGE_NAME
    if not source_path.exists():
        return LibraryPackageSummary(songs=0, bibles=0)
    needs_songs = not song_repo.list_song_ids()
    needs_bibles = not bible_repo.list_bible_index()
    if not needs_songs and not needs_bibles:
        return LibraryPackageSummary(songs=0, bibles=0)
    return import_library(
        source_path,
        include_songs=needs_songs,
        include_bibles=needs_bibles,
    )


def _safe_name(value: str, fallback: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", value).strip("._")
    return cleaned or fallback


def export_library(
    destination: str | Path,
    *,
    include_songs: bool = True,
    include_bibles: bool = True,
) -> LibraryPackageSummary:
    """Write the current libraries to an atomic, compressed package."""
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    songs = song_repo.load_all_songs() if include_songs else []
    bible_entries = bible_repo.list_bible_index() if include_bibles else []
    manifest: dict[str, object] = {
        "format": PACKAGE_FORMAT,
        "version": PACKAGE_VERSION,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "songs": [],
        "bibles": [],
    }
    song_manifest: list[dict[str, object]] = []
    bible_manifest: list[dict[str, object]] = []

    temporary = tempfile.NamedTemporaryFile(
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
        dir=destination_path.parent,
        delete=False,
    )
    temporary_path = Path(temporary.name)
    temporary.close()
    try:
        with zipfile.ZipFile(
            temporary_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for index, song in enumerate(songs):
                file_name = f"songs/{_safe_name(song.id, f'song-{index + 1}')}.xml"
                archive.writestr(file_name, serialize_openlyrics(song).encode("utf-8"))
                song_manifest.append(
                    {
                        "id": song.id,
                        "file": file_name,
                        "title": song.title,
                        "createdAt": song.created_at,
                        "updatedAt": song.updated_at,
                        "capo": song.capo,
                    }
                )

            for index, entry in enumerate(bible_entries):
                bible = bible_repo.load_bible_by_id(entry.id)
                stem = _safe_name(f"{bible.abbreviation}-{bible.id}", f"bible-{index + 1}")
                file_name = f"bibles/{stem}.xml"
                archive.writestr(file_name, serialize_zefania(bible).encode("utf-8"))
                bible_manifest.append(
                    {
                        "id": bible.id,
                        "file": file_name,
                        "name": bible.name,
                        "abbreviation": bible.abbreviation,
                        "language": bible.language,
                    }
                )

            manifest["songs"] = song_manifest
            manifest["bibles"] = bible_manifest
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
            )
        temporary_path.replace(destination_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return LibraryPackageSummary(songs=len(songs), bibles=len(bible_entries))


def import_library(
    source: str | Path,
    *,
    replace: bool = False,
    include_songs: bool = True,
    include_bibles: bool = True,
) -> LibraryPackageSummary:
    """Validate and import a JDP library package into the runtime databases."""
    source_path = Path(source)
    try:
        with zipfile.ZipFile(source_path, "r") as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            _validate_manifest(manifest)
            songs = _read_songs(archive, manifest) if include_songs else []
            bibles = _read_bibles(archive, manifest) if include_bibles else []
    except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise LibraryPackageError(f"Invalid JDP library package: {exc}") from exc

    if replace:
        if include_songs:
            for song_id in song_repo.list_song_ids():
                song_repo.delete_song(song_id)
        if include_bibles:
            for entry in bible_repo.list_bible_index():
                bible_repo.delete_bible(entry.id)

    for song in songs:
        song_repo.save_song(song)
    for bible in bibles:
        bible_repo.save_bible(bible)
    return LibraryPackageSummary(songs=len(songs), bibles=len(bibles))


def _validate_manifest(manifest: object) -> None:
    if not isinstance(manifest, dict):
        raise LibraryPackageError("Manifest must be a JSON object")
    if manifest.get("format") != PACKAGE_FORMAT:
        raise LibraryPackageError("Unsupported library package format")
    if manifest.get("version") != PACKAGE_VERSION:
        raise LibraryPackageError(f"Unsupported library package version: {manifest.get('version')}")
    if not isinstance(manifest.get("songs"), list) or not isinstance(manifest.get("bibles"), list):
        raise LibraryPackageError("Manifest must contain song and Bible lists")


def _read_songs(archive: zipfile.ZipFile, manifest: dict[str, object]) -> list[Song]:
    songs: list[Song] = []
    for raw_entry in manifest["songs"]:
        if not isinstance(raw_entry, dict) or not isinstance(raw_entry.get("file"), str):
            raise LibraryPackageError("Invalid song manifest entry")
        song = parse_openlyrics_xml(archive.read(raw_entry["file"]).decode("utf-8"))
        song.id = str(raw_entry.get("id") or uuid.uuid4())
        song.created_at = str(raw_entry.get("createdAt") or "")
        song.updated_at = str(raw_entry.get("updatedAt") or "")
        capo = raw_entry.get("capo")
        song.capo = str(capo) if capo is not None else None
        songs.append(song)
    return songs


def _read_bibles(archive: zipfile.ZipFile, manifest: dict[str, object]) -> list[BibleTranslation]:
    bibles: list[BibleTranslation] = []
    for raw_entry in manifest["bibles"]:
        if not isinstance(raw_entry, dict) or not isinstance(raw_entry.get("file"), str):
            raise LibraryPackageError("Invalid Bible manifest entry")
        bible = parse_zefania_xml(archive.read(raw_entry["file"]).decode("utf-8"))
        bible.id = str(raw_entry.get("id") or bible.id)
        bible.name = str(raw_entry.get("name") or bible.name)
        bible.abbreviation = str(raw_entry.get("abbreviation") or bible.abbreviation)
        bible.language = str(raw_entry.get("language") or bible.language)
        bibles.append(bible)
    return bibles
