"""SQLite-backed song persistence with non-destructive JSON migration."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

from app.models.song import Song, Verse
from app.persistence.paths import SONGS_DIR

_DATABASE_NAME = "library.sqlite3"
_SCHEMA_VERSION = 1
_initialize_lock = threading.Lock()
_initialized_paths: set[Path] = set()


def database_path() -> Path:
    return Path(str(SONGS_DIR)) / _DATABASE_NAME


def _connect() -> sqlite3.Connection:
    path = database_path()
    _ensure_database(path)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def _database() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _ensure_database(path: Path, *, migrate_legacy: bool = True) -> None:
    if path in _initialized_paths:
        return
    with _initialize_lock:
        if path in _initialized_paths:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=30)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS songs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT,
                    copyright TEXT,
                    ccli TEXT,
                    song_key TEXT,
                    tempo INTEGER,
                    capo TEXT,
                    verse_order TEXT,
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS song_verses (
                    song_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    text TEXT NOT NULL,
                    PRIMARY KEY (song_id, sequence),
                    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title COLLATE NOCASE);
                CREATE INDEX IF NOT EXISTS idx_songs_author ON songs(author COLLATE NOCASE);
                """
            )
            connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            song_count = connection.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
            if migrate_legacy and song_count == 0:
                _migrate_legacy_json(connection, path.parent)
            connection.commit()
        finally:
            connection.close()
        _initialized_paths.add(path)


def initialize_empty_database() -> None:
    """Create an empty database without importing legacy JSON files."""
    _ensure_database(database_path(), migrate_legacy=False)


def _migrate_legacy_json(connection: sqlite3.Connection, directory: Path) -> None:
    migrated = 0
    for path in sorted(directory.glob("*.json")):
        try:
            song = Song.from_json_dict(json.loads(path.read_text(encoding="utf-8")))
            _write_song(connection, song)
            migrated += 1
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            print(f"[SONGS] Skipping invalid song file {path.name}: {exc}")
    if migrated:
        print(f"[SONGS] Migrated {migrated} legacy JSON songs to {database_path()}")


def _write_song(connection: sqlite3.Connection, song: Song) -> None:
    connection.execute(
        """
        INSERT INTO songs (
            id, title, author, copyright, ccli, song_key, tempo, capo,
            verse_order, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            author = excluded.author,
            copyright = excluded.copyright,
            ccli = excluded.ccli,
            song_key = excluded.song_key,
            tempo = excluded.tempo,
            capo = excluded.capo,
            verse_order = excluded.verse_order,
            created_at = excluded.created_at,
            updated_at = excluded.updated_at
        """,
        (
            song.id,
            song.title,
            song.author,
            song.copyright,
            song.ccli,
            song.key,
            song.tempo,
            song.capo,
            json.dumps(song.verse_order) if song.verse_order is not None else None,
            song.created_at,
            song.updated_at,
        ),
    )
    connection.execute("DELETE FROM song_verses WHERE song_id = ?", (song.id,))
    connection.executemany(
        "INSERT INTO song_verses (song_id, sequence, label, text) VALUES (?, ?, ?, ?)",
        [(song.id, index, verse.label, verse.text) for index, verse in enumerate(song.verses)],
    )


def _song_from_row(row: sqlite3.Row, verses: list[Verse]) -> Song:
    return Song(
        id=row["id"],
        title=row["title"],
        author=row["author"],
        copyright=row["copyright"],
        ccli=row["ccli"],
        key=row["song_key"],
        tempo=row["tempo"],
        capo=row["capo"],
        verses=verses,
        verse_order=json.loads(row["verse_order"]) if row["verse_order"] else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_song_ids() -> list[str]:
    with _database() as connection:
        rows = connection.execute("SELECT id FROM songs ORDER BY title COLLATE NOCASE").fetchall()
    return [row["id"] for row in rows]


def load_song(song_id: str) -> Song:
    with _database() as connection:
        row = connection.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"Song not found: {song_id}")
        verse_rows = connection.execute(
            "SELECT label, text FROM song_verses WHERE song_id = ? ORDER BY sequence",
            (song_id,),
        ).fetchall()
    verses = [Verse(label=verse["label"], text=verse["text"]) for verse in verse_rows]
    return _song_from_row(row, verses)


def load_all_songs() -> list[Song]:
    with _database() as connection:
        song_rows = connection.execute("SELECT * FROM songs ORDER BY title COLLATE NOCASE").fetchall()
        verse_rows = connection.execute(
            "SELECT song_id, label, text FROM song_verses ORDER BY song_id, sequence"
        ).fetchall()
    verses_by_song: dict[str, list[Verse]] = {}
    for row in verse_rows:
        verses_by_song.setdefault(row["song_id"], []).append(Verse(label=row["label"], text=row["text"]))
    return [_song_from_row(row, verses_by_song.get(row["id"], [])) for row in song_rows]


def save_song(song: Song) -> None:
    with _database() as connection:
        _write_song(connection, song)


def delete_song(song_id: str) -> None:
    with _database() as connection:
        connection.execute("DELETE FROM songs WHERE id = ?", (song_id,))
