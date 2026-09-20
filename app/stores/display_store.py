"""DisplayStore: tracks available screens and which one the Output window targets."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QScreen


class DisplayStore(QObject):
    target_screen_changed = Signal(object)  # QScreen | None

    def __init__(self) -> None:
        super().__init__()
        self._target_screen: QScreen | None = None

    @property
    def target_screen(self) -> QScreen | None:
        return self._target_screen

    def set_target_screen(self, screen: QScreen | None) -> None:
        self._target_screen = screen
        self.target_screen_changed.emit(screen)
