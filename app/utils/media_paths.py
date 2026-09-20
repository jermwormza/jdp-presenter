"""Resolve possibly-stale media paths onto the current machine's actual files.

Services copied from the macOS origin machine mix two path styles that do not work
as-is on Windows (and vice-versa):

  * relative library paths   ->  ``./data/media/videos/Hymn.mp4``
  * absolute macOS paths     ->  ``/Users/jeremy/.../data/media/videos/Hymn.mp4``

``resolve_media_path`` tries, in order:
  1. the path as stored (works for local absolute paths),
  2. the path joined onto the project root (dev mode:  ./data/... from any CWD;
     frozen mode: the PyInstaller ``_MEIPASS`` bundle where ``data`` was added),
  3. the path joined onto the user-data dir (frozen builds copy bundled data there),
  4. a basename lookup in the local media library (recovers a stored macOS absolute
     path whose file exists locally under the same filename, e.g. in ``data/media/videos``).

If nothing resolves, the original path is returned unchanged so the caller decides
how to surface the missing file (placeholder text, QMediaPlayer error, etc.).
"""
from __future__ import annotations

from pathlib import Path

from app.persistence.paths import (
    MEDIA_AUDIO_DIR,
    MEDIA_DIR,
    MEDIA_IMAGES_DIR,
    MEDIA_VIDEOS_DIR,
    PROJECT_ROOT,
    USER_DATA_DIR,
)

_MEDIA_LIBRARY_DIRS = (MEDIA_IMAGES_DIR, MEDIA_VIDEOS_DIR, MEDIA_AUDIO_DIR, MEDIA_DIR)


def resolve_media_path(path: str) -> str:
    """Return the best existing absolute path for a stored media path (unchanged if not found)."""
    if not path:
        return path
    if path.startswith(("http://", "https://", "file://", "qrc:")):
        return path

    p = Path(path)
    try:
        if p.exists():
            return str(p)
    except OSError:
        pass

    candidates: list[Path] = []
    if not p.is_absolute():
        candidates.append(PROJECT_ROOT / p)
        candidates.append(USER_DATA_DIR / p)
    if p.name:
        for base in _MEDIA_LIBRARY_DIRS:
            candidates.append(base / p.name)

    for cand in candidates:
        try:
            if cand.exists():
                return str(cand)
        except OSError:
            pass
    return path