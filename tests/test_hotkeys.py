from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.utils.hotkeys import DEFAULT_HOTKEYS, configured_hotkeys, conflicting_action
from app.utils.help import render_help_html
from app.widgets.hotkey_capture_button import HotkeyCaptureButton


class HotkeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_requested_default_hotkeys(self) -> None:
        self.assertEqual(DEFAULT_HOTKEYS["previous_item"], "Left")
        self.assertEqual(DEFAULT_HOTKEYS["next_item"], "Right")
        self.assertEqual(DEFAULT_HOTKEYS["media_toggle"], "Space")
        self.assertEqual(DEFAULT_HOTKEYS["toggle_show_hide"], ".")
        self.assertEqual(DEFAULT_HOTKEYS["decrease_font"], "-")
        self.assertEqual(DEFAULT_HOTKEYS["increase_font"], "+")
        self.assertEqual(DEFAULT_HOTKEYS["show_hotkeys"], "?")

    def test_stored_hotkeys_override_defaults(self) -> None:
        hotkeys = configured_hotkeys({"media_toggle": "Ctrl+M"})

        self.assertEqual(hotkeys["media_toggle"], "Ctrl+M")
        self.assertEqual(hotkeys["next_item"], "Right")

    def test_conflict_detection_uses_normalized_sequences(self) -> None:
        hotkeys = configured_hotkeys({})

        self.assertEqual(conflicting_action(hotkeys, "media_toggle", "Right"), "next_item")

    def test_capture_button_records_next_key_combination(self) -> None:
        button = HotkeyCaptureButton("Space")
        captured: list[str] = []
        button.sequence_captured.connect(captured.append)

        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        QTest.keyClick(button, Qt.Key.Key_M, Qt.KeyboardModifier.ControlModifier)

        self.assertEqual(button.sequence, "Ctrl+M")
        self.assertEqual(captured, ["Ctrl+M"])

    def test_help_renders_current_configured_hotkeys(self) -> None:
        class SettingsStub:
            def get(self, _key: str, _default=None):
                return {"media_toggle": "Ctrl+M"}

        html = render_help_html(SettingsStub())  # type: ignore[arg-type]

        self.assertIn("<kbd>Ctrl+M</kbd>", html)
        self.assertIn("Play/Pause Media", html)
        self.assertNotIn("{{HOTKEY_ROWS}}", html)


if __name__ == "__main__":
    unittest.main()
