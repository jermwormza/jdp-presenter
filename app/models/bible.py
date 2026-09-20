"""Bible dataclasses with JSON compatibility for legacy JDP Presenter libraries."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BibleVerse:
    number: int
    text: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"number": self.number, "text": self.text}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "BibleVerse":
        return cls(number=d["number"], text=d["text"])


@dataclass
class BibleChapter:
    number: int
    verses: list[BibleVerse] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {"number": self.number, "verses": [v.to_json_dict() for v in self.verses]}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "BibleChapter":
        return cls(number=d["number"], verses=[BibleVerse.from_json_dict(v) for v in d.get("verses", [])])


@dataclass
class BibleBook:
    number: int
    name: str
    chapters: list[BibleChapter] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "name": self.name,
            "chapters": [c.to_json_dict() for c in self.chapters],
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "BibleBook":
        return cls(
            number=d["number"],
            name=d["name"],
            chapters=[BibleChapter.from_json_dict(c) for c in d.get("chapters", [])],
        )


@dataclass
class BibleTranslation:
    id: str
    name: str
    abbreviation: str
    language: str
    books: list[BibleBook] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "abbreviation": self.abbreviation,
            "language": self.language,
            "books": [b.to_json_dict() for b in self.books],
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "BibleTranslation":
        return cls(
            id=d["id"],
            name=d["name"],
            abbreviation=d["abbreviation"],
            language=d["language"],
            books=[BibleBook.from_json_dict(b) for b in d.get("books", [])],
        )


@dataclass
class BibleIndexEntry:
    """One entry in data/bibles/index.json (translation metadata without full text)."""

    id: str
    name: str
    abbreviation: str
    language: str
    file_name: str

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "BibleIndexEntry":
        return cls(
            id=d["id"],
            name=d["name"],
            abbreviation=d["abbreviation"],
            language=d["language"],
            file_name=d["fileName"],
        )
