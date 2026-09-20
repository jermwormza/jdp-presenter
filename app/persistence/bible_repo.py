"""SQLite-backed Bible persistence with non-destructive JSON migration."""
from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.models.bible import BibleBook, BibleChapter, BibleIndexEntry, BibleTranslation, BibleVerse
from app.persistence.paths import BIBLES_DIR

_DATABASE_NAME = "library.sqlite3"
_SCHEMA_VERSION = 1
_initialize_lock = threading.Lock()
_initialized_paths: set[Path] = set()


def database_path() -> Path:
    return Path(str(BIBLES_DIR)) / _DATABASE_NAME


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
                CREATE TABLE IF NOT EXISTS bible_translations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    abbreviation TEXT NOT NULL,
                    language TEXT NOT NULL,
                    source_file TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS bible_books (
                    translation_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    number INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    PRIMARY KEY (translation_id, sequence),
                    FOREIGN KEY (translation_id) REFERENCES bible_translations(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS bible_chapters (
                    translation_id TEXT NOT NULL,
                    book_sequence INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    number INTEGER NOT NULL,
                    PRIMARY KEY (translation_id, book_sequence, sequence),
                    FOREIGN KEY (translation_id, book_sequence)
                        REFERENCES bible_books(translation_id, sequence) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS bible_verses (
                    translation_id TEXT NOT NULL,
                    book_sequence INTEGER NOT NULL,
                    chapter_sequence INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    number INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    PRIMARY KEY (translation_id, book_sequence, chapter_sequence, sequence),
                    FOREIGN KEY (translation_id, book_sequence, chapter_sequence)
                        REFERENCES bible_chapters(translation_id, book_sequence, sequence) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_bible_abbreviation
                    ON bible_translations(abbreviation COLLATE NOCASE);
                """
            )
            connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            translation_count = connection.execute(
                "SELECT COUNT(*) FROM bible_translations"
            ).fetchone()[0]
            if migrate_legacy and translation_count == 0:
                _migrate_legacy_json(connection, path.parent)
            connection.commit()
        finally:
            connection.close()
        _initialized_paths.add(path)


def initialize_empty_database() -> None:
    """Create an empty database without importing legacy JSON files."""
    _ensure_database(database_path(), migrate_legacy=False)


def _migrate_legacy_json(connection: sqlite3.Connection, directory: Path) -> None:
    index_path = directory / "index.json"
    if not index_path.exists():
        return
    try:
        entries = [
            BibleIndexEntry.from_json_dict(value)
            for value in json.loads(index_path.read_text(encoding="utf-8"))
        ]
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"[BIBLES] Could not migrate legacy index: {exc}")
        return
    migrated = 0
    for entry in entries:
        try:
            translation = BibleTranslation.from_json_dict(
                json.loads((directory / entry.file_name).read_text(encoding="utf-8"))
            )
            _write_translation(connection, translation, entry.file_name)
            migrated += 1
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            print(f"[BIBLES] Skipping invalid Bible file {entry.file_name}: {exc}")
    if migrated:
        print(f"[BIBLES] Migrated {migrated} legacy Bibles to {database_path()}")


def _write_translation(
    connection: sqlite3.Connection,
    translation: BibleTranslation,
    source_file: str,
) -> None:
    connection.execute(
        """
        INSERT INTO bible_translations (id, name, abbreviation, language, source_file)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            abbreviation = excluded.abbreviation,
            language = excluded.language,
            source_file = excluded.source_file
        """,
        (translation.id, translation.name, translation.abbreviation, translation.language, source_file),
    )
    connection.execute("DELETE FROM bible_books WHERE translation_id = ?", (translation.id,))
    for book_sequence, book in enumerate(translation.books):
        connection.execute(
            """INSERT INTO bible_books (translation_id, sequence, number, name)
            VALUES (?, ?, ?, ?)""",
            (translation.id, book_sequence, book.number, book.name),
        )
        for chapter_sequence, chapter in enumerate(book.chapters):
            connection.execute(
                """INSERT INTO bible_chapters
                (translation_id, book_sequence, sequence, number) VALUES (?, ?, ?, ?)""",
                (translation.id, book_sequence, chapter_sequence, chapter.number),
            )
            connection.executemany(
                """INSERT INTO bible_verses
                (translation_id, book_sequence, chapter_sequence, sequence, number, text)
                VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        translation.id,
                        book_sequence,
                        chapter_sequence,
                        verse_sequence,
                        verse.number,
                        verse.text,
                    )
                    for verse_sequence, verse in enumerate(chapter.verses)
                ],
            )


def list_bible_index() -> list[BibleIndexEntry]:
    with _database() as connection:
        rows = connection.execute(
            """SELECT id, name, abbreviation, language, source_file
            FROM bible_translations ORDER BY name COLLATE NOCASE"""
        ).fetchall()
    return [
        BibleIndexEntry(
            id=row["id"],
            name=row["name"],
            abbreviation=row["abbreviation"],
            language=row["language"],
            file_name=row["source_file"],
        )
        for row in rows
    ]


def load_bible(file_name: str) -> BibleTranslation:
    with _database() as connection:
        row = connection.execute(
            "SELECT * FROM bible_translations WHERE source_file = ? OR id = ?",
            (file_name, file_name),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(f"Bible not found: {file_name}")
        return _load_translation(connection, row)


def load_bible_by_id(bible_id: str) -> BibleTranslation:
    return load_bible(bible_id)


def resolve_bible_label(bible_id: str) -> str:
    """Map a stored translation id to its display abbreviation (e.g. "ESV"), falling back to the id."""
    with _database() as connection:
        row = connection.execute(
            "SELECT abbreviation FROM bible_translations WHERE id = ?", (bible_id,)
        ).fetchone()
    return row["abbreviation"] if row is not None else bible_id


def _load_translation(connection: sqlite3.Connection, row: sqlite3.Row) -> BibleTranslation:
    translation = BibleTranslation(
        id=row["id"],
        name=row["name"],
        abbreviation=row["abbreviation"],
        language=row["language"],
    )
    book_rows = connection.execute(
        """SELECT sequence, number, name FROM bible_books
        WHERE translation_id = ? ORDER BY sequence""",
        (translation.id,),
    ).fetchall()
    for book_row in book_rows:
        book = BibleBook(number=book_row["number"], name=book_row["name"])
        chapter_rows = connection.execute(
            """SELECT sequence, number FROM bible_chapters
            WHERE translation_id = ? AND book_sequence = ? ORDER BY sequence""",
            (translation.id, book_row["sequence"]),
        ).fetchall()
        for chapter_row in chapter_rows:
            verse_rows = connection.execute(
                """SELECT number, text FROM bible_verses
                WHERE translation_id = ? AND book_sequence = ? AND chapter_sequence = ?
                ORDER BY sequence""",
                (translation.id, book_row["sequence"], chapter_row["sequence"]),
            ).fetchall()
            book.chapters.append(
                BibleChapter(
                    number=chapter_row["number"],
                    verses=[BibleVerse(number=verse["number"], text=verse["text"]) for verse in verse_rows],
                )
            )
        translation.books.append(book)
    return translation


def save_bible(translation: BibleTranslation) -> str:
    """Store a translation and return its stable legacy-compatible file name."""
    file_name = f"{translation.abbreviation.lower()}_{translation.id.split('-')[0]}.json"
    with _database() as connection:
        _write_translation(connection, translation, file_name)
    return file_name


def delete_bible(bible_id: str) -> None:
    with _database() as connection:
        connection.execute("DELETE FROM bible_translations WHERE id = ?", (bible_id,))

