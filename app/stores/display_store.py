"""DisplayStore: tracks available screens and which one the Output window targets."""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication, QScreen


def preferred_output_screen(screens: Sequence[QScreen] | None = None) -> QScreen | None:
    """The screen the Output window should project on by default.

    With two or more screens the first non-primary screen is used so the Control window
    keeps the primary display; with a single screen the Output window shares it.
    """
    candidates = list(QGuiApplication.screens() if screens is None else screens)
    if not candidates:
        return None
    primary = QGuiApplication.primaryScreen()
    for screen in candidates:
        if screen is not primary:
            return screen
    return candidates[0]


class DisplayStore(QObject):
    target_screen_changed = Signal(object)  # QScreen | None

    def __init__(self) -> None:
        super().__init__()
        self._target_screen: QScreen | None = None

    @property
    def target_screen(self) -> QScreen | None:
        return self._target_screen

    @property
    def has_secondary_screen(self) -> bool:
        return len(QGuiApplication.screens()) > 1

    def set_target_screen(self, screen: QScreen | None) -> None:
        self._target_screen = screen
        self.target_screen_changed.emit(screen)
