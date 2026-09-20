from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.models.service import ScriptureItem, ScriptureVerse
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication

from app.utils.pagination import (
    _paginate_scripture_lines,
    _wrap_text_to_lines,
    format_scripture_text,
)


class ScriptureFormattingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_prose_poetry_transitions_preserve_paragraph_boundaries(self) -> None:
        item = ScriptureItem(
            id="scripture",
            verses=[
                ScriptureVerse("Psalms", 1, 1, "Prose opening."),
                ScriptureVerse("Psalms", 1, 2, "Poetry line one\nPoetry line two"),
                ScriptureVerse("Psalms", 1, 3, "Prose closing."),
            ],
        )

        self.assertEqual(
            format_scripture_text(item),
            "¹ Prose opening.\n\n² Poetry line one\n  Poetry line two\n\n³ Prose closing.",
        )

    def test_poetry_lines_and_wrapped_continuations_use_hanging_indents(self) -> None:
        metrics = QFontMetrics(QFont("Arial", 12))
        text = "¹ First authored poetry line\n  Second authored poetry line"
        max_width = metrics.horizontalAdvance("¹ First authored")

        lines = _wrap_text_to_lines(text, metrics, max_width)

        self.assertEqual(lines[0], "¹ First authored")
        self.assertTrue(lines[1].startswith("    "))
        second_source_line = next(line for line in lines if "Second" in line)
        self.assertTrue(second_source_line.startswith("  Second"))
        second_wrapped_index = lines.index(second_source_line) + 1
        self.assertTrue(lines[second_wrapped_index].startswith("    "))

    def test_wrapped_prose_remains_flush_left(self) -> None:
        metrics = QFontMetrics(QFont("Arial", 12))
        max_width = metrics.horizontalAdvance("¹ The revelation")

        lines = _wrap_text_to_lines(
            "¹ The revelation of Jesus Christ that God gave him to show his servants",
            metrics,
            max_width,
        )

        self.assertGreater(len(lines), 1)
        self.assertTrue(all(line == line.lstrip() for line in lines[1:]))

    def test_explicit_poetry_stanza_gap_is_preserved(self) -> None:
        item = ScriptureItem(
            id="scripture",
            verses=[ScriptureVerse("Psalms", 2, 1, "First line\n\nSecond stanza")],
        )

        self.assertEqual(
            format_scripture_text(item),
            "¹ First line\n\n  Second stanza",
        )

    def test_poetry_verse_moves_to_next_page_when_it_fits_there(self) -> None:
        lines = ["¹ First", "  continuation", "² Second", "  continuation"]

        pages = _paginate_scripture_lines(lines, 3)

        self.assertEqual(
            pages,
            ["¹ First\n  continuation", "² Second\n  continuation"],
        )

    def test_poetry_verse_may_split_when_longer_than_a_page(self) -> None:
        lines = ["¹ First", "  second", "  third", "  fourth"]

        pages = _paginate_scripture_lines(lines, 3)

        self.assertEqual(pages, ["¹ First\n  second\n  third", "  fourth"])


if __name__ == "__main__":
    unittest.main()