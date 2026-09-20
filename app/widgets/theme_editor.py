"""Global theme editor: background + scripture/song text style basics."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
)

from app.models.theme import default_theme
from app.stores.theme_store import ThemeStore


def _color_button(initial: str) -> QPushButton:
    button = QPushButton(initial)
    button.setProperty("color", initial)

    def pick() -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            button.setText(color.name())
            button.setProperty("color", color.name())

    button.clicked.connect(pick)
    return button


class ThemeEditor(QDialog):
    def __init__(self, theme_store: ThemeStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Theme Editor")
        self._theme_store = theme_store

        theme = theme_store.theme or default_theme()

        self._bg_color = _color_button(theme.background.color)
        self._verse_color = _color_button(theme.scripture.verse_text.color)
        self._verse_size = QSpinBox()
        self._verse_size.setRange(8, 200)
        self._verse_size.setValue(theme.scripture.verse_text.font_size)
        self._reference_color = _color_button(theme.scripture.reference.color)
        self._version_show = QCheckBox("Show version label")
        self._version_show.setChecked(theme.scripture.version.show)
        self._lyrics_color = _color_button(theme.song.lyrics.color)
        self._lyrics_size = QSpinBox()
        self._lyrics_size.setRange(8, 200)
        self._lyrics_size.setValue(theme.song.lyrics.font_size)
        self._metadata_show = QCheckBox("Show song metadata")
        self._metadata_show.setChecked(theme.song.metadata.show)

        form = QFormLayout(self)
        form.addRow("Background color", self._bg_color)
        form.addRow("Verse text color", self._verse_color)
        form.addRow("Verse text size", self._verse_size)
        form.addRow("Reference color", self._reference_color)
        form.addRow(self._version_show)
        form.addRow("Song lyrics color", self._lyrics_color)
        form.addRow("Song lyrics size", self._lyrics_size)
        form.addRow(self._metadata_show)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._apply_and_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _apply_and_accept(self) -> None:
        theme = self._theme_store.theme
        if theme is None:
            self.reject()
            return
        theme.background.color = self._bg_color.property("color")
        theme.scripture.verse_text.color = self._verse_color.property("color")
        theme.scripture.verse_text.font_size = self._verse_size.value()
        theme.scripture.reference.color = self._reference_color.property("color")
        theme.scripture.version.show = self._version_show.isChecked()
        theme.song.lyrics.color = self._lyrics_color.property("color")
        theme.song.lyrics.font_size = self._lyrics_size.value()
        theme.song.metadata.show = self._metadata_show.isChecked()
        self._theme_store.apply_theme(theme)
        self.accept()
