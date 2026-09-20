"""Virtual output canvas sizes for aspect-ratio emulation (4:3 / 16:9 / 16:10 displays).

Height is held constant across ratios so theme font sizes (specified in pixels) read the same
relative size regardless of which aspect ratio is being emulated — only available width changes.
"""
from __future__ import annotations

from PySide6.QtCore import QSize

DEFAULT_CANVAS_RATIO = "16:9"

CANVAS_SIZES: dict[str, QSize] = {
    "4:3": QSize(1440, 1080),
    "16:9": QSize(1920, 1080),
    "16:10": QSize(1728, 1080),
}


def size_for_ratio(ratio: str) -> QSize:
    return CANVAS_SIZES.get(ratio, CANVAS_SIZES[DEFAULT_CANVAS_RATIO])
