from __future__ import annotations

import unittest

from app.utils.update_checker import (
    is_newer_version,
    release_from_payload,
    version_parts,
)
from app.utils.versioning import bump_version, replace_project_version


class UpdateCheckerTests(unittest.TestCase):
    def test_version_parser_accepts_release_tags(self) -> None:
        self.assertEqual(version_parts("v1.12.3"), (1, 12, 3))

    def test_newer_version_comparison_handles_different_widths(self) -> None:
        self.assertTrue(is_newer_version("0.2.0", "0.1.9"))
        self.assertTrue(is_newer_version("1.0", "0.9.9"))
        self.assertFalse(is_newer_version("0.1", "0.1.0"))
        self.assertFalse(is_newer_version("0.1.0", "0.1.0"))

    def test_release_payload_uses_tag_and_release_page(self) -> None:
        release = release_from_payload(
            {
                "tag_name": "v0.2.0",
                "name": "JDP Presenter 0.2.0",
                "html_url": "https://github.com/jermwormza/jdp-presenter/releases/tag/v0.2.0",
            }
        )

        self.assertEqual(release.version, "0.2.0")
        self.assertEqual(release.name, "JDP Presenter 0.2.0")
        self.assertTrue(release.url.endswith("/v0.2.0"))

    def test_invalid_release_payload_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            release_from_payload({"message": "Not Found"})

    def test_release_versions_increment_requested_part(self) -> None:
        self.assertEqual(bump_version("0.1.0"), "0.1.1")
        self.assertEqual(bump_version("0.1.9", "minor"), "0.2.0")
        self.assertEqual(bump_version("1.9.9", "major"), "2.0.0")

    def test_pyproject_version_is_replaced_once(self) -> None:
        source = '[project]\nname = "example"\nversion = "0.1.0"\n'

        self.assertIn('version = "0.1.1"', replace_project_version(source, "0.1.1"))


if __name__ == "__main__":
    unittest.main()
