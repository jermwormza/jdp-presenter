from __future__ import annotations

import os
import re
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.utils.help import HELP_ICONS, help_file_path, render_help_html


class HelpRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_every_icon_placeholder_is_known_and_rendered_inline(self) -> None:
        source = help_file_path().read_text(encoding="utf-8")
        referenced = set(re.findall(r"\{\{ICON:([a-z_]+)\}\}", source))
        self.assertTrue(referenced)
        self.assertFalse(referenced - set(HELP_ICONS), "help references an icon with no factory")

        rendered = render_help_html()

        self.assertNotIn("{{ICON:", rendered)
        self.assertNotIn("{{HOTKEY_ROWS}}", rendered)
        self.assertGreaterEqual(rendered.count('src="data:image/png;base64,'), len(referenced))
        self.assertIn("<kbd>", rendered)


if __name__ == "__main__":
    unittest.main()
