#!/usr/bin/env python3
"""Export the bundled help guide (with inline toolbar icons) to a PDF.

Usage:
    python tools/export_help_pdf.py [output.pdf]

Renders app/resources/help/index.html through the same code the app uses for
Help → JDP Presenter Help…, then prints it with a headless Chromium-based browser
(Microsoft Edge or Google Chrome). Defaults to dist/JDP-Presenter-Help.pdf.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.utils.help import render_help_html  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def find_browser() -> Path | None:
    for name in ("msedge", "msedge.exe", "chrome", "chrome.exe", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return Path(found)
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ]
    return next((path for path in candidates if path.exists()), None)


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "JDP-Presenter-Help.pdf"
    browser = find_browser()
    if browser is None:
        print("No Microsoft Edge or Google Chrome installation found for PDF printing.")
        return 1

    QApplication.instance() or QApplication([])  # needed to rasterize the toolbar icons
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        html_path = Path(temporary) / "help.html"
        html_path.write_text(render_help_html(), encoding="utf-8")
        subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={output.resolve()}",
                html_path.resolve().as_uri(),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    print(f"Wrote {output} ({output.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
