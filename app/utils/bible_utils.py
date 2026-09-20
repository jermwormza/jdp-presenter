"""Scripture reference parsing: "John 3:16-21", "Matt 2:1-3:5", "Genesis 1:1" etc."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.bible import BibleTranslation
from app.models.service import ScriptureVerse

_REFERENCE_RE = re.compile(
    r"^\s*(?P<book>[1-3]?\s?[A-Za-z][A-Za-z.\s]*?)"  # Book name (e.g., "1 John", "Genesis")
    r"(?:\s+(?P<chapter>\d+))?"                        # Optional chapter (e.g., "3")
    r"(?::(?P<verse>\d+))?"                            # Optional verse (e.g., ":16")
    r"(?:\s*-\s*(?:(?P<chapter2>\d+):)?(?P<verse2>\d+))?"  # Optional range (e.g., "-21" or "-4:5")
    r"\s*$"
)

# Common abbreviations -> canonical book name (must match the names used in data/bibles/*.json).
_BOOK_ABBREVIATIONS: dict[str, str] = {
    "gen": "Genesis", "ge": "Genesis", "gn": "Genesis",
    "ex": "Exodus", "exo": "Exodus", "exod": "Exodus",
    "lev": "Leviticus", "le": "Leviticus", "lv": "Leviticus",
    "num": "Numbers", "nu": "Numbers", "nm": "Numbers", "nb": "Numbers",
    "deut": "Deuteronomy", "deu": "Deuteronomy", "de": "Deuteronomy", "dt": "Deuteronomy",
    "josh": "Joshua", "jos": "Joshua",
    "judg": "Judges", "jdg": "Judges", "jg": "Judges",
    "ruth": "Ruth", "rut": "Ruth", "ru": "Ruth",
    "1 sam": "1 Samuel", "1sam": "1 Samuel", "1sa": "1 Samuel", "1 sa": "1 Samuel", "1 samuel": "1 Samuel",
    "2 sam": "2 Samuel", "2sam": "2 Samuel", "2sa": "2 Samuel", "2 sa": "2 Samuel", "2 samuel": "2 Samuel",
    "1 kgs": "1 Kings", "1kgs": "1 Kings", "1ki": "1 Kings", "1 ki": "1 Kings", "1 kings": "1 Kings",
    "2 kgs": "2 Kings", "2kgs": "2 Kings", "2ki": "2 Kings", "2 ki": "2 Kings", "2 kings": "2 Kings",
    "1 chr": "1 Chronicles", "1chr": "1 Chronicles", "1 ch": "1 Chronicles", "1ch": "1 Chronicles",
    "1 chronicles": "1 Chronicles",
    "2 chr": "2 Chronicles", "2chr": "2 Chronicles", "2 ch": "2 Chronicles", "2ch": "2 Chronicles",
    "2 chronicles": "2 Chronicles",
    "ezr": "Ezra",
    "neh": "Nehemiah", "ne": "Nehemiah",
    "est": "Esther", "esth": "Esther",
    "job": "Job",
    "ps": "Psalms", "psa": "Psalms", "psalm": "Psalms", "pss": "Psalms",
    "prov": "Proverbs", "pro": "Proverbs", "pr": "Proverbs",
    "eccl": "Ecclesiastes", "ecc": "Ecclesiastes", "qoh": "Ecclesiastes",
    "song": "Song of Songs", "sng": "Song of Songs", "son": "Song of Songs", "sos": "Song of Songs",
    "song of solomon": "Song of Songs", "canticles": "Song of Songs",
    "isa": "Isaiah", "is": "Isaiah",
    "jer": "Jeremiah", "je": "Jeremiah",
    "lam": "Lamentations", "la": "Lamentations",
    "ezek": "Ezekiel", "eze": "Ezekiel", "ezk": "Ezekiel",
    "dan": "Daniel", "da": "Daniel", "dn": "Daniel",
    "hos": "Hosea", "ho": "Hosea",
    "joel": "Joel", "joe": "Joel", "jl": "Joel",
    "am": "Amos", "amo": "Amos",
    "obad": "Obadiah", "oba": "Obadiah", "ob": "Obadiah",
    "jonah": "Jonah", "jon": "Jonah",
    "mic": "Micah", "mi": "Micah",
    "nah": "Nahum", "na": "Nahum",
    "hab": "Habakkuk", "hb": "Habakkuk",
    "zeph": "Zephaniah", "zep": "Zephaniah", "zp": "Zephaniah",
    "hag": "Haggai", "hg": "Haggai",
    "zech": "Zechariah", "zec": "Zechariah", "zc": "Zechariah",
    "mal": "Malachi", "ml": "Malachi",
    "matt": "Matthew", "mat": "Matthew", "mt": "Matthew",
    "mark": "Mark", "mar": "Mark", "mrk": "Mark", "mk": "Mark",
    "luke": "Luke", "luk": "Luke", "lk": "Luke",
    "john": "John", "joh": "John", "jn": "John", "jhn": "John",
    "acts": "Acts", "act": "Acts", "ac": "Acts",
    "rom": "Romans", "ro": "Romans", "rm": "Romans",
    "1 cor": "1 Corinthians", "1cor": "1 Corinthians", "1co": "1 Corinthians", "1 co": "1 Corinthians",
    "1 corinthians": "1 Corinthians",
    "2 cor": "2 Corinthians", "2cor": "2 Corinthians", "2co": "2 Corinthians", "2 co": "2 Corinthians",
    "2 corinthians": "2 Corinthians",
    "gal": "Galatians", "ga": "Galatians",
    "eph": "Ephesians",
    "phil": "Philippians", "php": "Philippians", "phi": "Philippians",
    "col": "Colossians",
    "1 thess": "1 Thessalonians", "1thess": "1 Thessalonians", "1th": "1 Thessalonians", "1 th": "1 Thessalonians",
    "1 thessalonians": "1 Thessalonians",
    "2 thess": "2 Thessalonians", "2thess": "2 Thessalonians", "2th": "2 Thessalonians", "2 th": "2 Thessalonians",
    "2 thessalonians": "2 Thessalonians",
    "1 tim": "1 Timothy", "1tim": "1 Timothy", "1ti": "1 Timothy", "1 ti": "1 Timothy", "1 timothy": "1 Timothy",
    "2 tim": "2 Timothy", "2tim": "2 Timothy", "2ti": "2 Timothy", "2 ti": "2 Timothy", "2 timothy": "2 Timothy",
    "titus": "Titus", "tit": "Titus",
    "philem": "Philemon", "phm": "Philemon", "phlm": "Philemon",
    "heb": "Hebrews",
    "jas": "James", "jm": "James",
    "1 pet": "1 Peter", "1pet": "1 Peter", "1pe": "1 Peter", "1 pe": "1 Peter", "1 peter": "1 Peter",
    "2 pet": "2 Peter", "2pet": "2 Peter", "2pe": "2 Peter", "2 pe": "2 Peter", "2 peter": "2 Peter",
    "1 jn": "1 John", "1jn": "1 John", "1john": "1 John", "1 john": "1 John",
    "2 jn": "2 John", "2jn": "2 John", "2john": "2 John", "2 john": "2 John",
    "3 jn": "3 John", "3jn": "3 John", "3john": "3 John", "3 john": "3 John",
    "jude": "Jude", "jud": "Jude",
    "rev": "Revelation", "re": "Revelation", "revelation": "Revelation",
}

_ROMAN_PREFIX_RE = re.compile(r"^(iii|ii|i)\b\s*")
_ROMAN_TO_ARABIC = {"i": "1", "ii": "2", "iii": "3"}


def _normalize_book_input(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.strip().lower().replace(".", ""))
    match = _ROMAN_PREFIX_RE.match(normalized)
    if match:
        normalized = f"{_ROMAN_TO_ARABIC[match.group(1)]} {normalized[match.end():].strip()}"
    return normalized


def resolve_book_name(name: str) -> str | None:
    """Map a common abbreviation (e.g. "Gen", "1 Cor", "Rev") to its canonical book name."""
    return _BOOK_ABBREVIATIONS.get(_normalize_book_input(name))


@dataclass
class ParsedReference:
    book: str
    chapter: int
    verse_start: int
    verse_end: int
    chapter_end: int


def parse_reference(reference: str) -> ParsedReference:
    match = _REFERENCE_RE.match(reference)
    if match is None:
        raise ValueError(f"Could not parse scripture reference: {reference!r}")

    book = match.group("book").strip()
    chapter_str = match.group("chapter")
    verse_str = match.group("verse")
    verse2 = match.group("verse2")
    chapter2 = match.group("chapter2")

    # Handle different reference formats:
    # "John" -> whole book (chapter=1, verse_start=1, verse_end=last, chapter_end=last)
    # "John 3" -> whole chapter (verse_start=1, verse_end=last)
    # "John 3:16" -> single verse
    # "John 3:16-21" -> verse range in same chapter
    # "John 3:16-4:5" -> cross-chapter range

    if chapter_str is None:
        # Just book name: whole book
        return ParsedReference(
            book=book, chapter=1, verse_start=1, verse_end=0, chapter_end=0  # 0 means "all"
        )

    chapter = int(chapter_str)

    if verse_str is None:
        # Book + chapter only: whole chapter
        if verse2 is None and chapter2 is None:
            # Just "John 3" - whole chapter
            return ParsedReference(
                book=book, chapter=chapter, verse_start=1, verse_end=0, chapter_end=chapter  # 0 means "all verses"
            )

    # Has verse or range
    verse_start = int(verse_str) if verse_str is not None else 1

    if verse2 is None and chapter2 is None:
        # Single verse: "John 3:16"
        return ParsedReference(
            book=book, chapter=chapter, verse_start=verse_start, verse_end=verse_start, chapter_end=chapter
        )

    # Range: "John 3:16-21" or "John 3:16-4:5"
    if chapter2 is not None:
        chapter_end = int(chapter2)
        verse_end = int(verse2)
    else:
        chapter_end = chapter
        verse_end = int(verse2)

    return ParsedReference(
        book=book, chapter=chapter, verse_start=verse_start, verse_end=verse_end, chapter_end=chapter_end
    )


def format_reference(parsed: ParsedReference, book_name: str | None = None) -> str:
    """Format a reference using the resolved book name if provided, otherwise use the original."""
    book = book_name if book_name is not None else parsed.book
    # Whole book
    if parsed.chapter_end == 0:
        return book
    # Whole chapter
    if parsed.verse_end == 0 and parsed.chapter_end == parsed.chapter:
        return f"{book} {parsed.chapter}"
    # Cross-chapter range
    if parsed.chapter_end != parsed.chapter:
        return f"{book} {parsed.chapter}:{parsed.verse_start}-{parsed.chapter_end}:{parsed.verse_end}"
    # Verse range in same chapter
    if parsed.verse_end != parsed.verse_start:
        return f"{book} {parsed.chapter}:{parsed.verse_start}-{parsed.verse_end}"
    # Single verse
    return f"{book} {parsed.chapter}:{parsed.verse_start}"


def is_valid_reference(reference: str) -> bool:
    try:
        parse_reference(reference)
        return True
    except ValueError:
        return False


def find_verses(bible: BibleTranslation, parsed: ParsedReference) -> list[ScriptureVerse]:
    book = next((b for b in bible.books if b.name.lower() == parsed.book.lower()), None)
    if book is None:
        resolved_name = resolve_book_name(parsed.book)
        if resolved_name is not None:
            book = next((b for b in bible.books if b.name.lower() == resolved_name.lower()), None)
    if book is None:
        raise ValueError(f"Book not found in {bible.name}: {parsed.book!r}")

    verses: list[ScriptureVerse] = []
    
    # Handle special cases:
    # chapter_end=0 means whole book
    # verse_end=0 with chapter_end=chapter means whole chapter
    # verse_end=0 with chapter_end > chapter means whole chapters range
    
    start_chapter = parsed.chapter
    end_chapter = parsed.chapter_end if parsed.chapter_end != 0 else len(book.chapters)
    start_verse = parsed.verse_start
    end_verse = parsed.verse_end if parsed.verse_end != 0 else None  # None means all verses in chapter

    for chapter in book.chapters:
        if chapter.number < start_chapter or chapter.number > end_chapter:
            continue
        
        # Determine verse range for this chapter
        if chapter.number == start_chapter:
            verse_start = start_verse
        else:
            verse_start = 1
            
        if chapter.number == end_chapter and end_verse is not None:
            verse_end = end_verse
        else:
            verse_end = None  # All verses
            
        for verse in chapter.verses:
            if verse.number < verse_start:
                continue
            if verse_end is not None and verse.number > verse_end:
                continue
            verses.append(
                ScriptureVerse(book=book.name, chapter=chapter.number, verse=verse.number, text=verse.text)
            )
    return verses
