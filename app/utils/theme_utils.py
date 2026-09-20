"""Theme merge helper: applies a per-item DisplaySettings partial over the global ServiceTheme."""
from __future__ import annotations

from app.models.service import DisplaySettings
from app.models.theme import ServiceTheme


def merge_theme(base: ServiceTheme, override: DisplaySettings | None) -> ServiceTheme:
    if override is None:
        return base
    return ServiceTheme(
        background=override.background if override.background is not None else base.background,
        scripture=override.scripture if override.scripture is not None else base.scripture,
        song=override.song if override.song is not None else base.song,
    )
