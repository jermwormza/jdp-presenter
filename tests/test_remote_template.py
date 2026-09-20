from __future__ import annotations

import unittest

from app.server.remote_server import app


class RemoteTemplateTests(unittest.TestCase):
    def test_phone_previews_follow_controls_and_tablet_reorders_them(self) -> None:
        response = app.test_client().get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertLess(html.index('class="controls"'), html.index('class="previews"'))
        self.assertIn('grid-template-areas: "header" "now" "controls" "previews"', html)
        self.assertIn('grid-template-areas: "header" "previews" "now" "controls"', html)
        self.assertEqual(html.count('id="current-preview"'), 1)
        self.assertEqual(html.count('id="next-preview"'), 1)


if __name__ == "__main__":
    unittest.main()