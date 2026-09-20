"""Parse OpenSong XML songs (root <song> with a raw <lyrics> block using [V1]/[C]/[B] markers).

Chord lines (conventionally prefixed with '.') are skipped since this app has no chord display.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from app.models.song import Song, Verse

_MARKER_RE = re.compile(r"^\[([A-Za-z\-]+)\s*(\d*)\]")

_LABEL_PREFIX = {
    "v": "v",
    "verse": "v",
    "c": "c",
    "chorus": "c",
    "b": "b",
    "bridge": "b",
    "p": "pc",
    "pc": "pc",
    "pre-chorus": "pc",
    "prechorus": "pc",
    "t": "t",
    "tag": "t",
    "i": "i",
    "intro": "i",
    "e": "e",
    "ending": "e",
}


def _parse_opensong_lyrics(raw_lyrics: str) -> list[Verse]:
    verses: list[Verse] = []
    current_label = "v1"
    current_lines: list[str] = []
    auto_verse_count = 0

    for raw_line in raw_lyrics.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("."):
            continue  # chord line, not lyrics
        match = _MARKER_RE.match(stripped)
        if match:
            if current_lines:
                verses.append(Verse(label=current_label, text="\n".join(current_lines).strip()))
                current_lines = []
            marker = match.group(1).lower()
            num = match.group(2)
            prefix = _LABEL_PREFIX.get(marker, marker[:1])
            if prefix == "v" and not num:
                auto_verse_count += 1
                current_label = f"v{auto_verse_count}"
            else:
                current_label = f"{prefix}{num}"
        elif stripped:
            current_lines.append(line)

    if current_lines:
        verses.append(Verse(label=current_label, text="\n".join(current_lines).strip()))
    return verses or ([Verse(label="v1", text=raw_lyrics.strip())] if raw_lyrics.strip() else [])


def parse_opensong_xml(xml_content: str) -> Song:
    """Returns a draft Song object (id/timestamps left blank — caller assigns before saving)."""
    root = ET.fromstring(xml_content)
    song_el = root if root.tag.lower() == "song" else root.find(".//song")
    if song_el is None:
        raise ValueError("Invalid OpenSong XML: missing <song> element")

    def _text(tag: str) -> str | None:
        el = song_el.find(tag)
        return el.text.strip() if el is not None and el.text else None

    title = _text("title") or "Untitled Song"
    author = _text("author")
    ccli = _text("ccli")
    copyright_ = _text("copyright")
    key = _text("key")
    capo = _text("capo")
    tempo_raw = _text("tempo")
    tempo = int(tempo_raw) if tempo_raw and tempo_raw.isdigit() else None
    presentation = _text("presentation")
    verse_order = presentation.lower().split() if presentation else None

    lyrics_el = song_el.find("lyrics")
    lyrics_raw = (lyrics_el.text or "") if lyrics_el is not None else ""

    return Song(
        id="",
        title=title,
        author=author,
        copyright=copyright_,
        ccli=ccli,
        key=key,
        capo=capo,
        tempo=tempo,
        verses=_parse_opensong_lyrics(lyrics_raw),
        verse_order=verse_order,
    )
