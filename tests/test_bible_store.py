from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from app.models.bible import BibleIndexEntry, BibleTranslation
from app.stores.bible_store import BibleStore
from app.stores.settings_store import SettingsStore


class BibleStoreTests(unittest.TestCase):
    def test_active_translation_is_loaded_from_and_saved_to_preferences(self) -> None:
        settings_store = Mock(spec=SettingsStore)
        settings_store.get.return_value = "csb"
        translation = BibleTranslation("csb", "Christian Standard Bible", "CSB", "en")
        store = BibleStore(settings_store)
        store._index = [
            BibleIndexEntry("csb", "Christian Standard Bible", "CSB", "en", "csb.sqlite3")
        ]

        self.assertEqual(store.preferred_translation_id, "csb")
        with patch("app.stores.bible_store.bible_repo.load_bible", return_value=translation):
            store.set_active_translation("csb")

        self.assertIs(store.active_translation, translation)
        settings_store.set.assert_called_once_with("lastBibleTranslationId", "csb")


if __name__ == "__main__":
    unittest.main()