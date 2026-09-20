from __future__ import annotations

import unittest

from app.models.service import Service, SongItem, TextItem
from app.models.song import Song, Verse
from app.models.theme import default_theme
from app.stores.service_store import ServiceStore


class ServiceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ServiceStore()
        self.store.set_service(
            Service(
                id="service-1",
                version="1.0",
                name="Sunday Service",
                date="2026-09-05",
                theme=default_theme(),
                items=[
                    TextItem(id="first", title="First"),
                    TextItem(id="selected", title="Selected"),
                    TextItem(id="last", title="Last"),
                ],
            )
        )

    def test_add_item_inserts_after_selected_item(self) -> None:
        self.store.select_item("selected")

        self.store.add_item(TextItem(id="inserted", title="Inserted"))

        assert self.store.service is not None
        self.assertEqual(
            [item.id for item in self.store.service.items],
            ["first", "selected", "inserted", "last"],
        )

    def test_add_item_appends_without_a_selection(self) -> None:
        self.store.add_item(TextItem(id="appended", title="Appended"))

        assert self.store.service is not None
        self.assertEqual(self.store.service.items[-1].id, "appended")

    def test_move_item_reorders_selected_schedule_item(self) -> None:
        self.store.select_item("selected")

        self.store.move_item("selected", "up")

        assert self.store.service is not None
        self.assertEqual(
            [item.id for item in self.store.service.items],
            ["selected", "first", "last"],
        )
        self.assertEqual(self.store.selected_item_id, "selected")

    def test_remove_only_item_clears_schedule_and_selection(self) -> None:
        assert self.store.service is not None
        self.store.service.items = [TextItem(id="only", title="Only")]
        self.store.select_item("only")

        self.store.remove_item("only")

        self.assertEqual(self.store.service.items, [])
        self.assertIsNone(self.store.selected_item_id)

    def test_refresh_song_items_updates_scheduled_title_and_slides(self) -> None:
        song_item = SongItem(
            id="scheduled-song",
            title="Old Title",
            song_id="song-1",
            selected_verses=["v1"],
        )
        assert self.store.service is not None
        self.store.service.items = [song_item]
        edited_song = Song(
            id="song-1",
            title="New Title",
            verses=[Verse("v1", "Updated lyrics")],
            verse_order=["v1"],
        )

        self.store.refresh_song_items(edited_song)

        self.assertEqual(song_item.title, "New Title")
        self.assertEqual([slide.content for slide in song_item.slides], ["Updated lyrics"])
        self.assertTrue(self.store.dirty)


if __name__ == "__main__":
    unittest.main()