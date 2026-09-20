from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.models.service import Service, TextItem
from app.models.theme import default_theme
from app.stores.output_store import OutputStore
from app.stores.service_store import ServiceStore


class OutputStoreTerminalBlankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.service_store = ServiceStore()
        self.service_store.set_service(
            Service(
                id="service-1",
                version="1.0",
                name="Sunday Service",
                date="2026-09-06",
                theme=default_theme(),
                items=[
                    TextItem(id="first", title="First", content="First page"),
                    TextItem(id="final", title="Final", content="Final page"),
                ],
            )
        )
        self.output_store = OutputStore(self.service_store)
        self.output_store.set_position(1)

    def test_next_slide_after_final_page_shows_terminal_blank(self) -> None:
        self.output_store.next_slide()

        self.assertIsNone(self.output_store.current_item())
        self.assertEqual(self.output_store.current_page_text(), "")
        self.assertEqual(self.output_store.item_index, 1)

        self.output_store.next_slide()
        self.assertIsNone(self.output_store.current_item())

        self.output_store.previous_slide()
        self.assertEqual(self.output_store.current_item().id, "final")

    def test_remote_next_after_final_page_shows_terminal_blank(self) -> None:
        self.output_store.handle_remote_command("next")

        self.assertIsNone(self.output_store.current_item())
        self.assertEqual(self.output_store.current_page_text(), "")

    def test_next_item_from_final_item_shows_terminal_blank(self) -> None:
        self.output_store.next_item()

        self.assertIsNone(self.output_store.current_item())
        self.assertEqual(self.output_store.current_page_text(), "")
        self.assertEqual(self.output_store.item_index, 1)

    def test_previous_item_jumps_to_previous_items_first_page(self) -> None:
        self.output_store.previous_item()

        self.assertEqual(self.output_store.current_item().id, "first")
        self.assertEqual(self.output_store.item_index, 0)
        self.assertEqual(self.output_store.slide_index, 0)


if __name__ == "__main__":
    unittest.main()