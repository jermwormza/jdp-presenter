from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app.utils.update_checker import (
    ReleaseAsset,
    ReleaseInfo,
    installer_command,
    is_newer_version,
    launch_update,
    release_from_payload,
    select_asset,
    version_parts,
)
from app.utils.versioning import bump_version, replace_project_version

_ASSETS = (
    ReleaseAsset("JDP-Presenter-linux.tar.gz", "https://example.test/linux.tar.gz", 10),
    ReleaseAsset("JDP-Presenter-macos.dmg", "https://example.test/mac.dmg", 20),
    ReleaseAsset("JDP-Presenter-windows.zip", "https://example.test/win.zip", 30),
    ReleaseAsset("JDP-Presenter-Setup.exe", "https://example.test/setup.exe", 40),
)
_RELEASE = ReleaseInfo("0.2.0", "JDP Presenter 0.2.0", "https://example.test/tag", _ASSETS)


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

    def test_release_payload_collects_downloadable_assets(self) -> None:
        release = release_from_payload(
            {
                "tag_name": "v0.2.0",
                "name": "JDP Presenter 0.2.0",
                "html_url": "https://github.com/jermwormza/jdp-presenter/releases/tag/v0.2.0",
                "assets": [
                    {
                        "name": "JDP-Presenter-Setup.exe",
                        "browser_download_url": "https://example.test/setup.exe",
                        "size": 1234,
                    },
                    {"name": "broken-entry-without-url"},
                    "not-a-dict",
                ],
            }
        )

        self.assertEqual(
            release.assets,
            (ReleaseAsset("JDP-Presenter-Setup.exe", "https://example.test/setup.exe", 1234),),
        )
        self.assertTrue(release.assets[0].is_installer)

    def test_asset_selection_prefers_native_installer_per_platform(self) -> None:
        self.assertEqual(select_asset(_RELEASE, "win32").name, "JDP-Presenter-Setup.exe")
        self.assertEqual(select_asset(_RELEASE, "darwin").name, "JDP-Presenter-macos.dmg")
        self.assertEqual(select_asset(_RELEASE, "linux").name, "JDP-Presenter-linux.tar.gz")
        self.assertIsNone(select_asset(_RELEASE, "freebsd"))

    def test_asset_selection_falls_back_to_zip_when_installer_is_missing(self) -> None:
        release = ReleaseInfo("0.2.0", "n", "u", _ASSETS[:3])
        selected = select_asset(release, "win32")
        assert selected is not None
        self.assertEqual(selected.name, "JDP-Presenter-windows.zip")
        self.assertFalse(selected.is_installer)
        self.assertIsNone(select_asset(ReleaseInfo("0.2.0", "n", "u"), "win32"))

    def test_installer_command_runs_silently_and_flags_auto_update(self) -> None:
        command = installer_command(Path("C:/tmp/JDP-Presenter-Setup.exe"))

        self.assertEqual(command[0], str(Path("C:/tmp/JDP-Presenter-Setup.exe")))
        self.assertIn("/SILENT", command)
        self.assertIn("/CLOSEAPPLICATIONS", command)
        self.assertIn("/AUTOUPDATE=1", command)

    def test_launch_update_uses_shell_execute_for_windows_installer(self) -> None:
        with patch("app.utils.update_checker.os.startfile", create=True) as startfile:
            launch_update(Path("C:/tmp/JDP-Presenter-Setup.exe"), "win32")

        startfile.assert_called_once()
        executable, operation, arguments = startfile.call_args.args
        self.assertTrue(executable.endswith("JDP-Presenter-Setup.exe"))
        self.assertEqual(operation, "open")
        self.assertEqual(arguments, "/SILENT /CLOSEAPPLICATIONS /NORESTART /AUTOUPDATE=1")

    def test_launch_update_opens_disk_image_on_macos(self) -> None:
        with patch("app.utils.update_checker.subprocess.Popen") as popen:
            launch_update(Path("/tmp/JDP-Presenter-macos.dmg"), "darwin")

        popen.assert_called_once_with(["open", str(Path("/tmp/JDP-Presenter-macos.dmg"))])

    def test_release_versions_increment_requested_part(self) -> None:
        self.assertEqual(bump_version("0.1.0"), "0.1.1")
        self.assertEqual(bump_version("0.1.9", "minor"), "0.2.0")
        self.assertEqual(bump_version("1.9.9", "major"), "2.0.0")

    def test_pyproject_version_is_replaced_once(self) -> None:
        source = '[project]\nname = "example"\nversion = "0.1.0"\n'

        self.assertIn('version = "0.1.1"', replace_project_version(source, "0.1.1"))


if __name__ == "__main__":
    unittest.main()
