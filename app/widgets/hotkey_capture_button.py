"""Push button that captures the next keyboard shortcut pressed."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QPushButton, QWidget

from app.utils.hotkeys import normalize_hotkey


class HotkeyCaptureButton(QPushButton):
    sequence_captured = Signal(str)

    def __init__(self, sequence: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sequence = normalize_hotkey(sequence)
        self._capturing = False
        self.setMinimumWidth(150)
        self.clicked.connect(self._begin_capture)
        self._update_text()

    @property
    def sequence(self) -> str:
        return self._sequence

    def set_sequence(self, sequence: str) -> None:
        self._sequence = normalize_hotkey(sequence)
        self._capturing = False
        self._update_text()

    def _begin_capture(self) -> None:
        self._capturing = True
        self.setText("Press shortcut...")
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        if not self._capturing:
            super().keyPressEvent(event)
            return
        if event.isAutoRepeat() or event.key() in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
            event.accept()
            return
        sequence = QKeySequence(event.keyCombination()).toString(
            QKeySequence.SequenceFormat.PortableText
        )
        if sequence:
            self._sequence = sequence
            self._capturing = False
            self._update_text()
            self.sequence_captured.emit(sequence)
        event.accept()

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802 (Qt override)
        self._capturing = False
        self._update_text()
        super().focusOutEvent(event)

    def _update_text(self) -> None:
        display = QKeySequence(self._sequence).toString(
            QKeySequence.SequenceFormat.NativeText
        )
        self.setText(display)
