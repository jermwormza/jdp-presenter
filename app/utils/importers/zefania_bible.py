"""Parse and serialize Bibles using the Zefania XML interchange format."""
from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET

from app.models.bible import BibleBook, BibleChapter, BibleTranslation, BibleVerse


def _find_all(parent: ET.Element, tag: str) -> list[ET.Element]:
    """Descendant search, tolerant of tag-name casing (Zefania files vary: BIBLEBOOK/BibleBook/...)."""
    matches = parent.findall(f".//{tag}")
    if matches:
        return matches
    for variant in {tag.upper(), tag.lower(), tag.capitalize()}:
        if variant == tag:
            continue
        matches = parent.findall(f".//{variant}")
        if matches:
            return matches
    lower = tag.lower()
    return [el for el in parent.iter() if el.tag.lower() == lower]


def _int_or(value: str | None, fallback: int) -> int:
    if value and value.isdigit() and int(value) != 0:
        return int(value)
    return fallback


def parse_zefania_xml(xml_content: str) -> BibleTranslation:
    root = ET.fromstring(xml_content)
    xml_bible = root if root.tag.upper() == "XMLBIBLE" else next(iter(_find_all(root, "XMLBIBLE")), None)
    if xml_bible is None:
        raise ValueError("Invalid Zefania XML: missing XMLBIBLE root element")

    full_name = xml_bible.get("biblename", "Unknown Bible")
    match = re.search(r"\b([A-Z]{2,5})\b", full_name)
    abbreviation = match.group(1) if match else "".join(w[0].upper() for w in full_name.split() if w)[:4] or "BIB"

    translation = BibleTranslation(id=str(uuid.uuid4()), name=full_name, abbreviation=abbreviation, language="en")

    for i, b in enumerate(_find_all(xml_bible, "BIBLEBOOK")):
        book = BibleBook(number=_int_or(b.get("bnumber"), i + 1), name=b.get("bname", f"Book {i + 1}"))

        for j, c in enumerate(_find_all(b, "CHAPTER")):
            chapter = BibleChapter(number=_int_or(c.get("cnumber"), j + 1))

            for k, v in enumerate(_find_all(c, "VERS")):
                chapter.verses.append(
                    BibleVerse(number=_int_or(v.get("vnumber"), k + 1), text=(v.text or "").strip())
                )
            book.chapters.append(chapter)
        translation.books.append(book)

    if not translation.books:
        raise ValueError("Parsed Zefania XML but found 0 books (expected BIBLEBOOK elements)")

    return translation


def serialize_zefania(translation: BibleTranslation) -> str:
    """Serialize a Bible translation as Zefania XML."""
    root = ET.Element(
        "XMLBIBLE",
        {
            "biblename": translation.name,
            "type": "x-bible",
            "status": "v",
            "version": "2.0.1.18",
        },
    )
    information = ET.SubElement(root, "INFORMATION")
    ET.SubElement(information, "format").text = "Zefania XML Bible Markup Language"
    ET.SubElement(information, "language").text = translation.language
    ET.SubElement(information, "identifier").text = translation.id
    ET.SubElement(information, "subject").text = translation.abbreviation

    for book in translation.books:
        book_element = ET.SubElement(
            root,
            "BIBLEBOOK",
            {"bnumber": str(book.number), "bname": book.name},
        )
        for chapter in book.chapters:
            chapter_element = ET.SubElement(
                book_element,
                "CHAPTER",
                {"cnumber": str(chapter.number)},
            )
            for verse in chapter.verses:
                ET.SubElement(
                    chapter_element,
                    "VERS",
                    {"vnumber": str(verse.number)},
                ).text = verse.text

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
