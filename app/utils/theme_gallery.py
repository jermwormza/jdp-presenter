"""Prebuilt themes for the JDP Presenter theme gallery."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.theme import (
    BackgroundTheme,
    MetadataStyle,
    ReferenceStyle,
    ScriptureTheme,
    ServiceTheme,
    SongTheme,
    TextStyle,
    VersionStyle,
)


def _theme(
    bg_color: str,
    font_family: str,
    verse_size: int,
    verse_color: str,
    ref_size: int,
    ref_color: str,
    ref_style: str,
    version_size: int,
    version_color: str,
    version_style: str,
    version_show: bool,
    lyrics_size: int,
    lyrics_color: str,
    lyrics_weight: str,
    metadata_size: int,
    metadata_color: str,
    metadata_style: str,
    metadata_show: bool,
) -> ServiceTheme:
    return ServiceTheme(
        background=BackgroundTheme(type="color", color=bg_color, opacity=1.0),
        scripture=ScriptureTheme(
            verse_text=TextStyle(font_family, verse_size, "normal", "normal", verse_color, "center"),
            reference=ReferenceStyle(
                font_family, ref_size, "bold", ref_style, ref_color, "center", position="bottom-right"
            ),
            version=VersionStyle(
                font_family,
                version_size,
                "normal",
                version_style,
                version_color,
                "right",
                show=version_show,
                position="bottom-left",
            ),
            verse_line_breaks=True,
        ),
        song=SongTheme(
            lyrics=TextStyle(font_family, lyrics_size, lyrics_weight, "normal", lyrics_color, "center"),
            metadata=MetadataStyle(
                font_family,
                metadata_size,
                "normal",
                metadata_style,
                metadata_color,
                "left",
                show=metadata_show,
                position="bottom-left",
            ),
        ),
    )


PREBUILT_THEMES: dict[str, ServiceTheme] = {
    "classic_dark": _theme(
        "#1a1a1a", "Georgia, serif", 48, "#ffffff", 24, "#00d4ff", "normal", 14, "#999999", "normal",
        True, 44, "#ffffff", "normal", 16, "#999999", "normal", True,
    ),
    "modern_bright": _theme(
        "#f5f5f5", "Segoe UI, sans-serif", 52, "#222222", 24, "#0066cc", "normal", 14, "#666666", "normal",
        True, 48, "#222222", "normal", 16, "#666666", "normal", True,
    ),
    "elegant_gold": _theme(
        "#1a1410", "Garamond, serif", 50, "#f0e6d2", 26, "#d4af37", "normal", 14, "#8b7355", "italic",
        True, 46, "#f0e6d2", "normal", 16, "#d4af37", "italic", True,
    ),
    "ocean_blue": _theme(
        "#0a1929", "Trebuchet MS, sans-serif", 48, "#e8f4f8", 24, "#4db8ff", "normal", 14, "#7fb3d5", "normal",
        True, 44, "#e8f4f8", "normal", 16, "#7fb3d5", "normal", True,
    ),
    "sunset_warm": _theme(
        "#2d1810", "Verdana, sans-serif", 50, "#ffe6cc", 26, "#ff9933", "normal", 14, "#cc6633", "normal",
        True, 46, "#ffe6cc", "normal", 16, "#ff9933", "normal", True,
    ),
    "forest_green": _theme(
        "#0d2818", "Georgia, serif", 48, "#d4f1e4", 24, "#7dd3c0", "normal", 14, "#5fa693", "normal",
        True, 44, "#d4f1e4", "normal", 16, "#7dd3c0", "normal", True,
    ),
    "lavender_dream": _theme(
        "#2d1b4e", "Georgia, serif", 48, "#e6d9f0", 24, "#c7b3e5", "normal", 14, "#9d7fc0", "normal",
        True, 44, "#e6d9f0", "normal", 16, "#c7b3e5", "normal", True,
    ),
    "high_contrast": _theme(
        "#000000", "Arial, sans-serif", 56, "#ffff00", 28, "#ffffff", "normal", 16, "#ffffff", "normal",
        True, 52, "#ffff00", "bold", 18, "#ffffff", "normal", True,
    ),
    "minimalist_white": _theme(
        "#ffffff", "Helvetica, Arial, sans-serif", 54, "#000000", 22, "#333333", "normal", 12, "#666666", "normal",
        False, 50, "#000000", "normal", 14, "#666666", "normal", False,
    ),
}


@dataclass
class ThemeMetadata:
    key: str
    label: str
    description: str
    category: str  # 'dark' | 'light' | 'colorful' | 'accessible'


THEME_METADATA: list[ThemeMetadata] = [
    ThemeMetadata("classic_dark", "Classic Dark", "Professional minimalist with elegant serif fonts", "dark"),
    ThemeMetadata("modern_bright", "Modern Bright", "Clean and contemporary with sans-serif styling", "light"),
    ThemeMetadata("elegant_gold", "Elegant Gold", "Premium look with warm gold accents", "colorful"),
    ThemeMetadata("ocean_blue", "Ocean Blue", "Calming blue tones for peaceful worship", "colorful"),
    ThemeMetadata("sunset_warm", "Sunset Warm", "Energetic and vibrant with warm orange tones", "colorful"),
    ThemeMetadata("forest_green", "Forest Green", "Peaceful nature-inspired green palette", "colorful"),
    ThemeMetadata("lavender_dream", "Lavender Dream", "Soft and spiritual with purple tones", "colorful"),
    ThemeMetadata("high_contrast", "High Contrast", "Accessibility-focused with maximum contrast", "accessible"),
    ThemeMetadata(
        "minimalist_white", "Minimalist White", "Ultra-clean white background, pure content focus", "light"
    ),
]


def get_prebuilt_theme(key: str) -> ServiceTheme | None:
    return PREBUILT_THEMES.get(key)


def get_all_prebuilt_theme_keys() -> list[str]:
    return list(PREBUILT_THEMES.keys())
