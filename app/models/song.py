"""Song dataclasses with JSON compatibility for legacy JDP Presenter libraries."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Verse:
    label: str
    text: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"label": self.label, "text": self.text}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "Verse":
        return cls(label=d["label"], text=d["text"])


@dataclass
class Song:
    id: str
    title: str
    author: str | None = None
    copyright: str | None = None
    ccli: str | None = None
    key: str | None = None
    tempo: int | None = None
    capo: str | None = None
    verses: list[Verse] = field(default_factory=list)
    verse_order: list[str] | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "verses": [v.to_json_dict() for v in self.verses],
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        if self.author is not None:
            d["author"] = self.author
        if self.copyright is not None:
            d["copyright"] = self.copyright
        if self.ccli is not None:
            d["ccli"] = self.ccli
        if self.key is not None:
            d["key"] = self.key
        if self.tempo is not None:
            d["tempo"] = self.tempo
        if self.capo is not None:
            d["capo"] = self.capo
        if self.verse_order is not None:
            d["verseOrder"] = self.verse_order
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "Song":
        return cls(
            id=d["id"],
            title=d.get("title", ""),
            author=d.get("author"),
            copyright=d.get("copyright"),
            ccli=d.get("ccli"),
            key=d.get("key"),
            tempo=d.get("tempo"),
            capo=d.get("capo"),
            verses=[Verse.from_json_dict(v) for v in d.get("verses", [])],
            verse_order=d.get("verseOrder"),
            created_at=d.get("createdAt", ""),
            updated_at=d.get("updatedAt", ""),
        )
