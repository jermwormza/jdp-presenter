"""Create/edit a Song: metadata fields + a smart-paste lyrics textarea."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from app.models.song import Song
from app.utils.song_utils import smart_paste_lyrics


class SongEditor(QDialog):
    def __init__(self, song: Song | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Song" if song else "New Song")
        self.resize(700, 550)
        self._song = song

        self._title_edit = QLineEdit(song.title if song else "")
        self._author_edit = QLineEdit(song.author or "" if song else "")
        self._ccli_edit = QLineEdit(song.ccli or "" if song else "")
        self._copyright_edit = QLineEdit(song.copyright or "" if song else "")
        self._key_edit = QLineEdit(song.key or "" if song else "")
        self._tempo_edit = QLineEdit(str(song.tempo) if song and song.tempo is not None else "")
        self._capo_edit = QLineEdit(song.capo or "" if song else "")
        self._verse_order_edit = QLineEdit(" ".join(song.verse_order) if song and song.verse_order else "")
        self._verse_order_edit.setPlaceholderText("e.g. v1 c1 v2 c1 (blank = verses in the order below)")
        self._lyrics_edit = QPlainTextEdit()
        if song:
            self._lyrics_edit.setPlainText(
                "\n\n".join(f"{v.label}\n{v.text}" for v in song.verses)
            )
        self._lyrics_edit.setPlaceholderText(
            "Paste lyrics here. Separate sections with a blank line.\n"
            "Optional headers: Verse 1 / Chorus / Bridge / Pre-Chorus / Tag"
        )

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Title", self._title_edit)
        form.addRow("Author", self._author_edit)
        form.addRow("CCLI", self._ccli_edit)
        form.addRow("Copyright", self._copyright_edit)
        form.addRow("Key", self._key_edit)
        form.addRow("Tempo", self._tempo_edit)
        form.addRow("Capo", self._capo_edit)
        form.addRow("Play Order", self._verse_order_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._lyrics_edit)
        layout.addWidget(buttons)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Occasionally opened while another dialog (e.g. the Song Browser) still has focus; make
        # sure this one actually ends up on top instead of behind it.
        self.raise_()
        self.activateWindow()

    def result_song(self) -> Song:
        now = datetime.now(timezone.utc).isoformat()
        verses = smart_paste_lyrics(self._lyrics_edit.toPlainText())
        verse_order = self._verse_order_edit.text().split() or None
        tempo_text = self._tempo_edit.text().strip()
        tempo = int(tempo_text) if tempo_text.isdigit() else None
        return Song(
            id=self._song.id if self._song else str(uuid.uuid4()),
            title=self._title_edit.text() or "Untitled",
            author=self._author_edit.text() or None,
            ccli=self._ccli_edit.text() or None,
            copyright=self._copyright_edit.text() or None,
            key=self._key_edit.text() or None,
            tempo=tempo,
            capo=self._capo_edit.text() or None,
            verse_order=verse_order,
            verses=verses,
            created_at=self._song.created_at if self._song else now,
            updated_at=now,
        )
