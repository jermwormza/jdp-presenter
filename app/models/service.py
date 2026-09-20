"""Service models with explicit compatibility for legacy camelCase JSON files."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Union

from app.models.theme import BackgroundTheme, ScriptureTheme, ServiceTheme, SongTheme, default_theme


@dataclass
class DisplaySettings:
    """Shallow, per-item partial override of ServiceTheme (None fields inherit the global theme)."""

    background: BackgroundTheme | None = None
    scripture: ScriptureTheme | None = None
    song: SongTheme | None = None
    custom_qss: str | None = None
    verse_range: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.background is not None:
            d["background"] = self.background.to_json_dict()
        if self.scripture is not None:
            d["scripture"] = self.scripture.to_json_dict()
        if self.song is not None:
            d["song"] = self.song.to_json_dict()
        if self.custom_qss is not None:
            d["customCSS"] = self.custom_qss
        if self.verse_range is not None:
            d["verseRange"] = self.verse_range
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "DisplaySettings":
        return cls(
            background=BackgroundTheme.from_json_dict(d["background"]) if "background" in d else None,
            scripture=ScriptureTheme.from_json_dict(d["scripture"]) if "scripture" in d else None,
            song=SongTheme.from_json_dict(d["song"]) if "song" in d else None,
            custom_qss=d.get("customCSS"),
            verse_range=d.get("verseRange"),
        )


@dataclass
class Slide:
    id: str
    content: str = ""
    label: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "content": self.content}
        if self.label is not None:
            d["label"] = self.label
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "Slide":
        return cls(id=d["id"], content=d.get("content", ""), label=d.get("label"))


@dataclass
class ScriptureVerse:
    book: str
    chapter: int
    verse: int
    text: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"book": self.book, "chapter": self.chapter, "verse": self.verse, "text": self.text}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "ScriptureVerse":
        return cls(book=d["book"], chapter=d["chapter"], verse=d["verse"], text=d["text"])


@dataclass
class BaseServiceItem:
    id: str
    type: str
    title: str = ""
    display_settings: DisplaySettings | None = None
    slides: list[Slide] = field(default_factory=list)

    def _base_json_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "slides": [s.to_json_dict() for s in self.slides],
        }
        if self.display_settings is not None:
            d["displaySettings"] = self.display_settings.to_json_dict()
        return d

    @staticmethod
    def _base_kwargs(d: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": d["id"],
            "type": d["type"],
            "title": d.get("title", ""),
            "display_settings": (
                DisplaySettings.from_json_dict(d["displaySettings"]) if "displaySettings" in d else None
            ),
            "slides": [Slide.from_json_dict(s) for s in d.get("slides", [])],
        }


@dataclass
class ScriptureItem(BaseServiceItem):
    type: str = "scripture"
    bible: str = ""
    reference: str = ""
    verses: list[ScriptureVerse] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        d = self._base_json_dict()
        d["bible"] = self.bible
        d["reference"] = self.reference
        d["verses"] = [v.to_json_dict() for v in self.verses]
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "ScriptureItem":
        return cls(
            **cls._base_kwargs(d),
            bible=d.get("bible", ""),
            reference=d.get("reference", ""),
            verses=[ScriptureVerse.from_json_dict(v) for v in d.get("verses", [])],
        )


@dataclass
class SongItem(BaseServiceItem):
    type: str = "song"
    song_id: str = ""
    selected_verses: list[str] = field(default_factory=list)
    linked_video: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        d = self._base_json_dict()
        d["songId"] = self.song_id
        d["selectedVerses"] = self.selected_verses
        if self.linked_video is not None:
            d["linkedVideo"] = self.linked_video
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "SongItem":
        return cls(
            **cls._base_kwargs(d),
            song_id=d.get("songId", ""),
            selected_verses=list(d.get("selectedVerses", [])),
            linked_video=d.get("linkedVideo"),
        )


@dataclass
class ImageItem(BaseServiceItem):
    type: str = "image"
    path: str = ""
    fit: Literal["contain", "cover", "fill"] | None = None
    scale_mode: Literal["fit", "original", "fill_width", "fill_height"] = "fit"

    def to_json_dict(self) -> dict[str, Any]:
        d = self._base_json_dict()
        d["path"] = self.path
        if self.fit is not None:
            d["fit"] = self.fit
        d["scaleMode"] = self.scale_mode
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "ImageItem":
        return cls(
            **cls._base_kwargs(d),
            path=d.get("path", ""),
            fit=d.get("fit"),
            scale_mode=d.get("scaleMode", "fit"),
        )


@dataclass
class VideoItem(BaseServiceItem):
    type: str = "video"
    path: str = ""
    auto_play: bool = False
    loop: bool = False
    scale_mode: Literal["fit", "original", "fill_width", "fill_height"] = "fit"

    def to_json_dict(self) -> dict[str, Any]:
        d = self._base_json_dict()
        d["path"] = self.path
        d["autoPlay"] = self.auto_play
        d["loop"] = self.loop
        d["scaleMode"] = self.scale_mode
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "VideoItem":
        return cls(
            **cls._base_kwargs(d),
            path=d.get("path", ""),
            auto_play=d.get("autoPlay", False),
            loop=d.get("loop", False),
            scale_mode=d.get("scaleMode", "fit"),
        )


@dataclass
class AudioItem(BaseServiceItem):
    """Background audio (e.g. hymn tracks) with no visible slide, played behind other content."""

    type: str = "audio"
    path: str = ""
    auto_play: bool = False
    loop: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        d = self._base_json_dict()
        d["path"] = self.path
        d["autoPlay"] = self.auto_play
        d["loop"] = self.loop
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "AudioItem":
        return cls(
            **cls._base_kwargs(d),
            path=d.get("path", ""),
            auto_play=d.get("autoPlay", False),
            loop=d.get("loop", False),
        )


@dataclass
class PdfItem(BaseServiceItem):
    type: str = "pdf"
    path: str = ""
    page_count: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        d = self._base_json_dict()
        d["path"] = self.path
        if self.page_count is not None:
            d["pageCount"] = self.page_count
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "PdfItem":
        return cls(**cls._base_kwargs(d), path=d.get("path", ""), page_count=d.get("pageCount"))


@dataclass
class PptxItem(BaseServiceItem):
    """Type defined for forward-compat; rendering deferred (see TODO.md #12)."""

    type: str = "pptx"
    path: str = ""
    slide_count: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        d = self._base_json_dict()
        d["path"] = self.path
        if self.slide_count is not None:
            d["slideCount"] = self.slide_count
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "PptxItem":
        return cls(**cls._base_kwargs(d), path=d.get("path", ""), slide_count=d.get("slideCount"))


@dataclass
class TextItem(BaseServiceItem):
    type: str = "text"
    content: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        d = self._base_json_dict()
        d["content"] = self.content
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "TextItem":
        return cls(**cls._base_kwargs(d), content=d.get("content", ""))


ServiceItem = Union[ScriptureItem, SongItem, ImageItem, VideoItem, AudioItem, PdfItem, PptxItem, TextItem]

_ITEM_TYPES: dict[str, type[BaseServiceItem]] = {
    "scripture": ScriptureItem,
    "song": SongItem,
    "image": ImageItem,
    "video": VideoItem,
    "audio": AudioItem,
    "pdf": PdfItem,
    "pptx": PptxItem,
    "text": TextItem,
}


def service_item_from_json_dict(d: dict[str, Any]) -> ServiceItem:
    item_cls = _ITEM_TYPES.get(d["type"])
    if item_cls is None:
        raise ValueError(f"Unknown service item type: {d['type']!r}")
    return item_cls.from_json_dict(d)  # type: ignore[return-value]


@dataclass
class Service:
    id: str
    version: str
    name: str
    date: str
    theme: ServiceTheme
    items: list[ServiceItem] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "name": self.name,
            "date": self.date,
            "theme": self.theme.to_json_dict(),
            "items": [item.to_json_dict() for item in self.items],
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "Service":
        return cls(
            id=d["id"],
            version=d.get("version", "1.0"),
            name=d.get("name", "New Service"),
            date=d.get("date", ""),
            theme=ServiceTheme.from_json_dict(d["theme"]) if "theme" in d else default_theme(),
            items=[service_item_from_json_dict(i) for i in d.get("items", [])],
            created_at=d.get("createdAt", ""),
            updated_at=d.get("updatedAt", ""),
        )
