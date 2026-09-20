from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PACKAGE_SOURCES = (
    "data/starter-library.jdplibrary",
    "data/services",
    "data/media",
    "data/import",
)


class PublicDistributionTests(unittest.TestCase):
    def test_build_script_does_not_bundle_private_content(self) -> None:
        build_script = (ROOT / "build_local.py").read_text(encoding="utf-8").replace("\\", "/")

        for source in FORBIDDEN_PACKAGE_SOURCES:
            self.assertNotIn(f"ROOT / '{source.replace('/', "' / '")}'", build_script)

    def test_ci_does_not_bundle_private_content_or_install_ffmpeg(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn('--add-data "data', workflow)
        self.assertNotIn("install ffmpeg", workflow)

    def test_windows_installer_does_not_copy_private_content(self) -> None:
        installer = (ROOT / "installer" / "JDP Presenter.iss").read_text(
            encoding="utf-8"
        )

        for source in ("starter-library.jdplibrary", "data\\services", "data\\media", "data\\import"):
            self.assertNotIn(source, installer)

    def test_ffmpeg_is_not_bundled_and_installer_links_official_download(self) -> None:
        build_script = (ROOT / "build_local.py").read_text(encoding="utf-8")
        installer = (ROOT / "installer" / "JDP Presenter.iss").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("--add-binary", build_script)
        self.assertNotIn("_ensure_ffmpeg", build_script)
        self.assertIn("FileSearch('ffmpeg.exe', GetEnv('PATH'))", installer)
        self.assertIn("https://ffmpeg.org/download.html", installer)

    def test_binary_distributions_include_license_notices(self) -> None:
        build_script = (ROOT / "build_local.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
            encoding="utf-8"
        )
        installer = (ROOT / "installer" / "JDP Presenter.iss").read_text(
            encoding="utf-8"
        )

        for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            self.assertIn(filename, build_script)
            self.assertIn(filename, workflow)
        self.assertIn('Source: "..\\dist\\JDP Presenter\\*"', installer)

    def test_private_content_patterns_are_ignored(self) -> None:
        ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8")

        for rule in (
            "data/settings.json",
            "data/starter-library.jdplibrary",
            "data/import/",
            "data/services/*.json",
            "data/media/audio/",
            "data/media/images/",
            "data/media/videos/",
            "tools/ffmpeg/ffmpeg*",
        ):
            self.assertIn(rule, ignore_rules)


if __name__ == "__main__":
    unittest.main()
