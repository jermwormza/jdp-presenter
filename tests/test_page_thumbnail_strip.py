from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QLabel

from app.models.service import TextItem
from app.models.theme import default_theme
from app.widgets.page_thumbnail_strip import PageThumbnailStrip


class PageThumbnailStripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_page_captions_are_exactly_one_text_line_high(self) -> None:
        strip = PageThumbnailStrip()
        strip.resize(240, 480)
        strip.set_pages(
            TextItem(id="text", title="Text", content="Page content"),
            default_theme(),
            ["First page", "Second page"],
            QSize(1600, 900),
            1.0,
        )

        captions = [
            label
            for container in strip._containers
            for label in container.findChildren(QLabel)
            if label.text().startswith("Page ")
        ]

        self.assertEqual(len(captions), 2)
        for caption in captions:
            self.assertEqual(caption.minimumHeight(), caption.fontMetrics().height())
            self.assertEqual(caption.maximumHeight(), caption.fontMetrics().height())


if __name__ == "__main__":
    unittest.main()
