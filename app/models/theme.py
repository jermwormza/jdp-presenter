"""Theme dataclasses with JSON compatibility for legacy JDP Presenter services."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Position = Literal["bottom-right", "bottom-left", "top-left", "top-right"]


@dataclass
class TextStyle:
    font_family: str
    font_size: int
    font_weight: str
    font_style: str
    color: str
    text_align: Literal["left", "center", "right"] | None = None

    def to_json_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "fontFamily": self.font_family,
            "fontSize": self.font_size,
            "fontWeight": self.font_weight,
            "fontStyle": self.font_style,
            "color": self.color,
        }
        if self.text_align is not None:
            d["textAlign"] = self.text_align
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "TextStyle":
        return cls(
            font_family=d["fontFamily"],
            font_size=d["fontSize"],
            font_weight=d["fontWeight"],
            font_style=d["fontStyle"],
            color=d["color"],
            text_align=d.get("textAlign"),
        )


@dataclass
class ReferenceStyle(TextStyle):
    position: Position = "bottom-right"

    def to_json_dict(self) -> dict[str, Any]:
        d = super().to_json_dict()
        d["position"] = self.position
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "ReferenceStyle":
        base = TextStyle.from_json_dict(d)
        return cls(**vars(base), position=d.get("position", "bottom-right"))


@dataclass
class VersionStyle(TextStyle):
    show: bool = True
    position: Position = "bottom-left"

    def to_json_dict(self) -> dict[str, Any]:
        d = super().to_json_dict()
        d["show"] = self.show
        d["position"] = self.position
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "VersionStyle":
        base = TextStyle.from_json_dict(d)
        return cls(**vars(base), show=d.get("show", True), position=d.get("position", "bottom-left"))


@dataclass
class MetadataStyle(TextStyle):
    show: bool = True
    position: Literal["bottom-left", "bottom-right"] = "bottom-left"

    def to_json_dict(self) -> dict[str, Any]:
        d = super().to_json_dict()
        d["show"] = self.show
        d["position"] = self.position
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "MetadataStyle":
        base = TextStyle.from_json_dict(d)
        return cls(**vars(base), show=d.get("show", True), position=d.get("position", "bottom-left"))


@dataclass
class BackgroundTheme:
    type: Literal["color", "image", "video"] = "color"
    color: str = "#000000"
    image_path: str | None = None
    video_path: str | None = None
    opacity: float = 1.0

    def to_json_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type, "color": self.color, "opacity": self.opacity}
        if self.image_path is not None:
            d["imagePath"] = self.image_path
        if self.video_path is not None:
            d["videoPath"] = self.video_path
        return d

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "BackgroundTheme":
        return cls(
            type=d.get("type", "color"),
            color=d.get("color", "#000000"),
            image_path=d.get("imagePath"),
            video_path=d.get("videoPath"),
            opacity=d.get("opacity", 1.0),
        )


@dataclass
class ScriptureTheme:
    verse_text: TextStyle
    reference: ReferenceStyle
    version: VersionStyle
    verse_line_breaks: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "verseText": self.verse_text.to_json_dict(),
            "reference": self.reference.to_json_dict(),
            "version": self.version.to_json_dict(),
            "verseLineBreaks": self.verse_line_breaks,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "ScriptureTheme":
        return cls(
            verse_text=TextStyle.from_json_dict(d["verseText"]),
            reference=ReferenceStyle.from_json_dict(d["reference"]),
            version=VersionStyle.from_json_dict(d["version"]),
            verse_line_breaks=d.get("verseLineBreaks", False),
        )


@dataclass
class SongTheme:
    lyrics: TextStyle
    metadata: MetadataStyle

    def to_json_dict(self) -> dict[str, Any]:
        return {"lyrics": self.lyrics.to_json_dict(), "metadata": self.metadata.to_json_dict()}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "SongTheme":
        return cls(
            lyrics=TextStyle.from_json_dict(d["lyrics"]),
            metadata=MetadataStyle.from_json_dict(d["metadata"]),
        )


@dataclass
class ServiceTheme:
    background: BackgroundTheme
    scripture: ScriptureTheme
    song: SongTheme

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "background": self.background.to_json_dict(),
            "scripture": self.scripture.to_json_dict(),
            "song": self.song.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> "ServiceTheme":
        return cls(
            background=BackgroundTheme.from_json_dict(d["background"]),
            scripture=ScriptureTheme.from_json_dict(d["scripture"]),
            song=SongTheme.from_json_dict(d["song"]),
        )


def default_theme() -> ServiceTheme:
    return ServiceTheme(
        background=BackgroundTheme(type="color", color="#000000", opacity=1.0),
        scripture=ScriptureTheme(
            verse_text=TextStyle("Inter", 48, "normal", "normal", "#ffffff", "left"),
            reference=ReferenceStyle("Inter", 32, "bold", "normal", "#22d3ee", position="bottom-right"),
            version=VersionStyle(
                "Inter", 24, "normal", "italic", "#94a3b8", show=True, position="bottom-left"
            ),
            verse_line_breaks=False,
        ),
        song=SongTheme(
            lyrics=TextStyle("Inter", 56, "bold", "normal", "#ffffff"),
            metadata=MetadataStyle(
                "Inter", 24, "normal", "normal", "#94a3b8", show=True, position="bottom-left"
            ),
        ),
    )


DEFAULT_THEME = default_theme()
