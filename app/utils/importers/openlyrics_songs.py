"""Parse and serialize songs using the OpenLyrics XML interchange format."""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from app.models.song import Song, Verse


def _strip_namespaces(root: ET.Element) -> None:
    """OpenLyrics files declare an xmlns; strip it so plain-tag .find()/.findall() calls work."""
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def _element_text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    text = "".join(element.itertext()).strip()
    return text or None


def _lines_text(element: ET.Element) -> str:
    parts: list[str] = []

    def append_content(current: ET.Element) -> None:
        parts.append(current.text or "")
        for child in current:
            tag = child.tag.lower()
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


def _verse_text(verse: ET.Element) -> str:
    line_groups = [element for element in verse.iter() if element.tag.lower() == "lines"]
    if line_groups:
        return "\n".join(filter(None, (_lines_text(element) for element in line_groups))).strip()
    return _lines_text(verse)


def parse_openlyrics_xml(xml_content: str) -> Song:
    """Returns a draft Song object (id/timestamps left blank — caller assigns before saving)."""
    root = ET.fromstring(xml_content)
    _strip_namespaces(root)
    song_el = root if root.tag.lower() == "song" else root.find(".//song")
    if song_el is None:
        raise ValueError("Invalid OpenLyrics XML: missing <song> element")

    title = "Untitled Song"
    author = None
    copyright_ = None
    ccli = None

    properties = song_el.find("properties")
    if properties is not None:
        title = _element_text(properties.find("titles/title")) or title
        authors = [text for element in properties.findall("authors/author") if (text := _element_text(element))]
        author = "; ".join(authors) or None
        copyright_ = _element_text(properties.find("copyright"))
        ccli = _element_text(properties.find("ccliNo"))
        key = _element_text(properties.find("key"))
        tempo_text = _element_text(properties.find("tempo"))
        tempo = int(tempo_text) if tempo_text and tempo_text.isdigit() else None
        verse_order_text = _element_text(properties.find("verseOrder"))
        verse_order = verse_order_text.split() if verse_order_text else None
    else:
        key = None
        tempo = None
        verse_order = None

    verses: list[Verse] = []
    lyrics_el = song_el.find("lyrics")
    if lyrics_el is not None:
        for verse_el in lyrics_el.findall("verse"):
            label = verse_el.get("name", "v")
            verses.append(Verse(label=label, text=_verse_text(verse_el)))

    return Song(
        id="",
        title=title,
        author=author,
        copyright=copyright_,
        ccli=ccli,
        key=key,
        tempo=tempo,
        verses=verses,
        verse_order=verse_order,
    )


def parse_openlyrics_archive(path: str | Path) -> tuple[list[Song], int]:
    """Parse all OpenLyrics XML documents in a ZIP archive."""
    songs: list[Song] = []
    failures = 0
    with zipfile.ZipFile(path, "r") as archive:
        for entry in archive.infolist():
            if entry.is_dir() or not entry.filename.lower().endswith(".xml"):
                continue
            try:
                song = parse_openlyrics_xml(archive.read(entry).decode("utf-8-sig"))
                if not any(verse.text.strip() for verse in song.verses):
                    raise ValueError("OpenLyrics song has no lyric content")
                songs.append(song)
            except (ET.ParseError, UnicodeDecodeError, ValueError):
                failures += 1
    if not songs:
        raise ValueError("No valid OpenLyrics songs were found in this ZIP file")
    return songs, failures


def serialize_openlyrics(song: Song) -> str:
    """Serialize a song as interoperable OpenLyrics 0.9 XML."""
    namespace = "http://openlyrics.info/namespace/2009/song"
    ET.register_namespace("", namespace)
    root = ET.Element(
        f"{{{namespace}}}song",
        {"version": "0.9", "createdIn": "JDP Presenter", "modifiedIn": "JDP Presenter"},
    )
    properties = ET.SubElement(root, f"{{{namespace}}}properties")
    titles = ET.SubElement(properties, f"{{{namespace}}}titles")
    ET.SubElement(titles, f"{{{namespace}}}title").text = song.title
    if song.author:
        authors = ET.SubElement(properties, f"{{{namespace}}}authors")
        for author in (part.strip() for part in song.author.split(";")):
            if author:
                ET.SubElement(authors, f"{{{namespace}}}author").text = author
    if song.copyright:
        ET.SubElement(properties, f"{{{namespace}}}copyright").text = song.copyright
    if song.ccli:
        ET.SubElement(properties, f"{{{namespace}}}ccliNo").text = song.ccli
    if song.verse_order:
        ET.SubElement(properties, f"{{{namespace}}}verseOrder").text = " ".join(song.verse_order)
    if song.key:
        ET.SubElement(properties, f"{{{namespace}}}key").text = song.key
    if song.tempo is not None:
        ET.SubElement(properties, f"{{{namespace}}}tempo", {"type": "bpm"}).text = str(song.tempo)

    lyrics = ET.SubElement(root, f"{{{namespace}}}lyrics")
    for verse in song.verses:
        verse_element = ET.SubElement(lyrics, f"{{{namespace}}}verse", {"name": verse.label})
        lines = ET.SubElement(verse_element, f"{{{namespace}}}lines")
        text_lines = verse.text.splitlines() or [""]
        lines.text = text_lines[0]
        for text_line in text_lines[1:]:
            line_break = ET.SubElement(lines, f"{{{namespace}}}br")
            line_break.tail = text_line

    return ET.tostring(root, encoding="unicode", xml_declaration=True)
