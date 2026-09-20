"""Per-file library metadata for media (currently just each file's preferred scale mode),
backed by a small JSON file alongside the media library — distinct from per-service-item
scale_mode, which is set once an item is actually inserted into a service and can then be
overridden per-slide without affecting this stored library default.
"""
from __future__ import annotations

import json

from app.persistence.paths import MEDIA_DIR

METADATA_FILE = MEDIA_DIR / "library_metadata.json"

DEFAULT_SCALE_MODE = "fit"


def _load() -> dict[str, dict]:
    if not METADATA_FILE.exists():
        return {}
    return json.loads(METADATA_FILE.read_text(encoding="utf-8"))


def _save(metadata: dict[str, dict]) -> None:
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def get_scale_mode(path: str) -> str:
    return _load().get(path, {}).get("scaleMode", DEFAULT_SCALE_MODE)


def set_scale_mode(path: str, scale_mode: str) -> None:
    metadata = _load()
    metadata.setdefault(path, {})["scaleMode"] = scale_mode
    _save(metadata)


def remove_entry(path: str) -> None:
    metadata = _load()
    if metadata.pop(path, None) is not None:
        _save(metadata)
