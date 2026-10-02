from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.stores.display_store import DisplayStore, preferred_output_screen


class DisplayStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_single_screen_shares_primary_and_reports_no_secondary(self) -> None:
        screens = QApplication.screens()
        self.assertEqual(len(screens), 1)

        self.assertIs(preferred_output_screen(), QApplication.primaryScreen())
        self.assertFalse(DisplayStore().has_secondary_screen)

    def test_first_non_primary_screen_is_preferred_when_available(self) -> None:
        primary = QApplication.primaryScreen()
        secondary = object()  # stand-in: only identity matters to the selection

        self.assertIs(preferred_output_screen([primary, secondary]), secondary)  # type: ignore[list-item]
        self.assertIs(preferred_output_screen([secondary, primary]), secondary)  # type: ignore[list-item]
        self.assertIsNone(preferred_output_screen([]))


if __name__ == "__main__":
    unittest.main()
