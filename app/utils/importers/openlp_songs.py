"""Parse an OpenLP song database (songs.sqlite).

Schema per OpenLP's openlp.plugins.songs.lib.db module: `songs` table (id, title, lyrics,
verse_order, copyright, ccli_number, ...) plus `authors`/`authors_songs` bridge tables for author
display names. The `lyrics` column stores OpenLP's own SongXML format:
  <song version="1.0"><lyrics><verse type="v" label="1">...</verse>...</lyrics></song>
verse `type` is a single letter: v/c/b/p/i/e/o (Verse/Chorus/Bridge/Pre-Chorus/Intro/Ending/Other).
`verse_order` is already a space-separated list of type+label tokens (e.g. "v1 c1 v2 c1"), matching
this app's own verse_order convention directly.
"""
from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET

from app.models.song import Song, Verse


def _parse_openlp_lyrics(lyrics_xml: str) -> list[Verse]:
    if not lyrics_xml:
        return []
    root = ET.fromstring(lyrics_xml)
    verses: list[Verse] = []
    for verse_el in root.iter("verse"):
        verse_type = (verse_el.get("type") or "v").lower()
        label = verse_el.get("label") or "1"
        text = (verse_el.text or "").replace("[---]", "\n\n").strip()
        verses.append(Verse(label=f"{verse_type}{label}", text=text))
    return verses


def parse_openlp_sqlite(path: str) -> list[Song]:
    """Returns draft Song objects (id/timestamps left blank — caller assigns before saving)."""
    conn = sqlite3.connect(str(path))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT s.title, s.lyrics, s.verse_order, s.copyright, s.ccli_number,
                   GROUP_CONCAT(a.display_name, ', ') AS authors
            FROM songs s
            LEFT JOIN authors_songs asg ON asg.song_id = s.id
            LEFT JOIN authors a ON a.id = asg.author_id
            GROUP BY s.id
            """
        ).fetchall()
    finally:
        conn.close()

    songs: list[Song] = []
    for row in rows:
        title = row["title"]
        if not title:
            continue
        verse_order_raw = row["verse_order"]
        songs.append(
            Song(
                id="",
                title=title,
                author=row["authors"] or None,
                copyright=row["copyright"] or None,
                ccli=row["ccli_number"] or None,
                verses=_parse_openlp_lyrics(row["lyrics"] or ""),
                verse_order=verse_order_raw.lower().split() if verse_order_raw else None,
            )
        )
    return songs
