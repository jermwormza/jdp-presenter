from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.models.bible import BibleBook, BibleChapter, BibleIndexEntry, BibleTranslation, BibleVerse
from app.models.service import Service, TextItem
from app.models.song import Song, Verse
from app.models.theme import default_theme
from app.stores.bible_store import BibleStore
from app.stores.output_store import OutputStore
from app.stores.service_store import ServiceStore
from app.stores.song_store import SongStore
from app.widgets.quick_add_search import QuickAddSearch
from app.widgets.service_list import ServiceList


class QuickAddSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.service_store = ServiceStore()
        self.service_store.set_service(
            Service("service", "1.0", "Sunday", "2026-09-06", default_theme())
        )
        self.song_store = SongStore()
        self.song_store._songs = [
            Song(
                id="song-1",
                title="Crown Him with Many Crowns",
                author="Matthew Bridges",
                verses=[Verse("v1", "Crown Him with many crowns")],
                verse_order=["v1"],
            )
        ]
        self.bible_store = BibleStore()
        self.bible_store._index = [
            BibleIndexEntry("csb", "Christian Standard Bible", "CSB", "en", "csb.sqlite3")
        ]
        self.translation = BibleTranslation(
            id="csb",
            name="Christian Standard Bible",
            abbreviation="CSB",
            language="en",
            books=[
                BibleBook(
                    43,
                    "John",
                    [
                        BibleChapter(
                            1,
                            [BibleVerse(number, f"Verse {number}") for number in range(1, 52)],
                        )
                    ],
                )
            ],
        )

    def test_search_finds_song_and_media_without_false_scripture_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            media_path = Path(temporary_directory) / "Crown Him background.jpg"
            media_path.write_bytes(b"")
            media_directories = (("image", media_path.parent, {".jpg"}),)
            with patch("app.widgets.quick_add_search._MEDIA_DIRECTORIES", media_directories):
                widget = QuickAddSearch(self.service_store, self.song_store, self.bible_store)
                widget._search.setText("Crown Him")
                widget._refresh_results()

        self.assertEqual([result.kind for result in widget._results], ["song", "image"])
        widget._list.setCurrentRow(0)
        widget._insert_current()
        assert self.service_store.service is not None
        self.assertEqual(self.service_store.service.items[-1].title, "Crown Him with Many Crowns")

    def test_enter_inserts_only_result_without_waiting_for_debounce(self) -> None:
        widget = QuickAddSearch(self.service_store, self.song_store, self.bible_store)
        widget._search.setText("Crown Him with Many Crowns")

        QTest.keyClick(widget._search, Qt.Key.Key_Return)

        assert self.service_store.service is not None
        self.assertEqual(len(self.service_store.service.items), 1)
        self.assertEqual(self.service_store.service.items[0].title, "Crown Him with Many Crowns")
        self.assertEqual(
            self.service_store.selected_item_id,
            self.service_store.service.items[0].id,
        )

    def test_input_focus_changes_gate_window_shortcuts(self) -> None:
        widget = QuickAddSearch(self.service_store, self.song_store, self.bible_store)
        focus_states: list[bool] = []
        widget.input_focus_changed.connect(focus_states.append)

        QApplication.sendEvent(
            widget._search,
            QFocusEvent(QEvent.Type.FocusIn),
        )
        QApplication.sendEvent(
            widget._search,
            QFocusEvent(QEvent.Type.FocusOut),
        )

        self.assertEqual(focus_states, [True, False])

    def test_quick_add_highlights_new_item_after_existing_selection(self) -> None:
        assert self.service_store.service is not None
        self.service_store.add_item(TextItem(id="existing", title="Existing"))
        self.service_store.select_item("existing")
        output_store = OutputStore(self.service_store)
        service_list = ServiceList(self.service_store, output_store, self.song_store)
        widget = QuickAddSearch(self.service_store, self.song_store, self.bible_store)
        widget._search.setText("Crown Him")

        QTest.keyClick(widget._search, Qt.Key.Key_Return)

        added_item = self.service_store.service.items[1]
        self.assertEqual(self.service_store.selected_item_id, added_item.id)
        self.assertEqual(
            service_list.currentItem().data(Qt.ItemDataRole.UserRole),
            added_item.id,
        )

    def test_results_popup_does_not_change_quick_add_height(self) -> None:
        widget = QuickAddSearch(self.service_store, self.song_store, self.bible_store)
        initial_height = widget.sizeHint().height()

        widget._search.setText("Crown Him")
        widget._refresh_results()

        self.assertEqual(widget.sizeHint().height(), initial_height)
        self.assertFalse(widget._popup.isHidden())

    def test_enter_inserts_first_result_when_multiple_are_listed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            media_path = Path(temporary_directory) / "Crown Him background.jpg"
            media_path.write_bytes(b"")
            media_directories = (("image", media_path.parent, {".jpg"}),)
            with patch("app.widgets.quick_add_search._MEDIA_DIRECTORIES", media_directories):
                widget = QuickAddSearch(self.service_store, self.song_store, self.bible_store)
                widget._search.setText("Crown Him")
                widget._insert_first_result()

        assert self.service_store.service is not None
        self.assertEqual(len(self.service_store.service.items), 1)
        self.assertEqual(self.service_store.service.items[0].title, "Crown Him with Many Crowns")

    def test_explicit_translation_scripture_search_inserts_requested_verses(self) -> None:
        def activate_translation(_bible_id: str) -> None:
            self.bible_store._active = self.translation

        with patch.object(self.bible_store, "set_active_translation", activate_translation):
            widget = QuickAddSearch(self.service_store, self.song_store, self.bible_store)
            widget._search.setText("John 1:1-14 (CSB)")
            widget._refresh_results()
            widget._list.setCurrentRow(0)
            widget._insert_current()

        assert self.service_store.service is not None
        scripture = self.service_store.service.items[-1]
        self.assertEqual(scripture.type, "scripture")
        self.assertEqual(scripture.bible, "csb")
        self.assertEqual(len(scripture.verses), 14)

    def test_abbreviated_whole_chapter_uses_preferred_translation(self) -> None:
        self.bible_store._preferred_translation_id = "csb"

        def activate_translation(_bible_id: str) -> None:
            self.bible_store._active = self.translation

        with patch.object(self.bible_store, "set_active_translation", activate_translation):
            widget = QuickAddSearch(self.service_store, self.song_store, self.bible_store)
            widget._search.setText("Joh 1")
            widget._refresh_results()
            self.assertEqual(widget._results[0].detail, "Scripture · CSB")
            widget._list.setCurrentRow(0)
            widget._insert_current()

        assert self.service_store.service is not None
        scripture = self.service_store.service.items[-1]
        self.assertEqual(scripture.reference, "John 1")
        self.assertEqual(len(scripture.verses), 51)


if __name__ == "__main__":
    unittest.main()