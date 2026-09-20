"""Parse Quelea song packs and script exports into JDP song models."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from app.models.song import Song, Verse

_INSERT_RE = re.compile(
    r'INSERT\s+INTO\s+(?:(?:"[^"]+"|\w+)\.)?(?:"SONGS"|SONGS)\s+VALUES\s*\((.*)\)', re.IGNORECASE
)
_SECTION_RE = re.compile(r"^(Verse|Chorus|Bridge|Pre-Chorus|Tag|Slide|Other)\s*(\d+)?", re.IGNORECASE)

_LABEL_PREFIX = {
    "verse": "v",
    "chorus": "c",
    "bridge": "b",
    "pre-chorus": "pc",
    "tag": "t",
}


def _xml_lyrics_text(element: ET.Element) -> str:
    parts: list[str] = []

    def append_content(current: ET.Element) -> None:
        parts.append(current.text or "")
        for child in current:
            tag = child.tag.rsplit("}", 1)[-1].lower()
            if tag == "br":
                parts.append("\n")
            elif tag == "line":
                if parts and parts[-1] and not parts[-1].endswith("\n"):
                    parts.append("\n")
                append_content(child)
                parts.append("\n")
            else:
                append_content(child)
            parts.append(child.tail or "")

    append_content(element)
    return "".join(parts).replace("\r\n", "\n").replace("\r", "\n").strip()


def _parse_sql_values(line: str) -> list[str]:
    values: list[str] = []
    current = ""
    in_string = False
    i = 0
    n = len(line)
    while i < n:
        char = line[i]
        nxt = line[i + 1] if i + 1 < n else ""
        if in_string:
            if char == "'" and nxt == "'":
                current += "'"
                i += 2
                continue
            if char == "'":
                in_string = False
                i += 1
                continue
            current += char
        else:
            if char == "'":
                in_string = True
            elif char == ",":
                values.append(current.strip())
                current = ""
            else:
                current += char
        i += 1
    values.append(current.strip())
    return ["" if v.upper() == "NULL" else v for v in values]


def _parse_quelea_lyrics(raw_lyrics: str) -> list[Verse]:
    lyrics = raw_lyrics.replace("\\u000a", "\n")
    lines = lyrics.split("\n")
    verses: list[Verse] = []
    current_label = "v1"
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        match = _SECTION_RE.match(stripped)
        if match:
            if current_lines:
                verses.append(Verse(label=current_label, text="\n".join(current_lines).strip()))
                current_lines = []
            section_type = match.group(1).lower()
            num = (match.group(2) or "").strip()
            prefix = _LABEL_PREFIX.get(section_type, section_type[:1])
            current_label = f"{prefix}{num}"
        else:
            current_lines.append(line)

    if current_lines:
        verses.append(Verse(label=current_label, text="\n".join(current_lines).strip()))
    return verses


def parse_quelea_script(text: str) -> list[Song]:
    """Returns draft Song objects (id/timestamps left blank — caller assigns before saving)."""
    songs: list[Song] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("INSERT"):
            continue
        match = _INSERT_RE.match(stripped)
        if not match:
            continue
        values = _parse_sql_values(match.group(1))
        if len(values) < 11:
            continue

        author = values[1] or None
        capo = values[2] or None
        ccli = values[3] or None
        copyright_ = values[4] or None
        key = values[6] or None
        lyrics_raw = values[7]
        sequence_raw = values[9] or None
        title = values[10]
        if not title:
            continue

        verse_order = sequence_raw.lower().split() if sequence_raw else None

        songs.append(
            Song(
                id="",
                title=title,
                author=author,
                copyright=copyright_,
                ccli=ccli,
                key=key,
                capo=capo,
                verses=_parse_quelea_lyrics(lyrics_raw),
                verse_order=verse_order,
            )
        )
    return songs


def parse_quelea_song_xml(xml_content: str) -> Song:
    """Parse one native Quelea SongDisplayable XML document."""
    root = ET.fromstring(xml_content)
    if root.tag.lower() != "song":
        raise ValueError("Invalid Quelea song XML: missing <song> root")

    title = (root.findtext("title") or "").strip()
    if not title:
        raise ValueError("Invalid Quelea song XML: missing title")

    verses: list[Verse] = []
    lyrics = root.find("lyrics")
    if lyrics is not None:
        for index, section in enumerate(lyrics.findall("section"), start=1):
            section_title = (section.get("title") or f"Verse {index}").strip()
            label_match = _SECTION_RE.match(section_title)
            if label_match:
                section_type = label_match.group(1).lower()
                prefix = _LABEL_PREFIX.get(section_type, section_type[:1])
                label = f"{prefix}{label_match.group(2) or ''}"
            else:
                label = section_title or f"v{index}"
            lyrics_element = section.find("lyrics")
            text = _xml_lyrics_text(lyrics_element) if lyrics_element is not None else ""
            verses.append(Verse(label=label, text=text))

    sequence = (root.findtext("sequence") or "").strip()
    return Song(
        id="",
        title=title,
        author=(root.findtext("author") or "").strip() or None,
        copyright=(root.findtext("copyright") or "").strip() or None,
        ccli=(root.findtext("ccli") or "").strip() or None,
        key=(root.findtext("key") or "").strip() or None,
        capo=(root.findtext("capo") or "").strip() or None,
        verses=verses,
        verse_order=sequence.lower().split() or None,
    )


def parse_quelea_song_pack(path: str | Path) -> tuple[list[Song], int]:
    """Parse XML songs from a Quelea .qsp ZIP, returning songs and failures."""
    songs: list[Song] = []
    failures = 0
    with zipfile.ZipFile(path, "r") as archive:
        for entry in archive.infolist():
            if entry.is_dir() or not entry.filename.lower().endswith(".xml"):
                continue
            try:
                song = parse_quelea_song_xml(archive.read(entry).decode("utf-8-sig"))
                if not any(verse.text.strip() for verse in song.verses):
                    raise ValueError("Quelea song has no lyric content")
                songs.append(song)
            except (ET.ParseError, UnicodeDecodeError, ValueError):
                failures += 1
    if not songs:
        raise ValueError("No valid Quelea songs were found in this .qsp file")
    return songs, failures
