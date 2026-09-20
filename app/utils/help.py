"""Resolve and open the bundled HTML help guide."""
from __future__ import annotations

import sys
import tempfile
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from app.utils.hotkeys import HOTKEY_DEFINITIONS, configured_hotkeys

if TYPE_CHECKING:
    from app.stores.settings_store import SettingsStore


def help_file_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "help" / "index.html"
    return Path(__file__).resolve().parents[1] / "resources" / "help" / "index.html"


def render_help_html(settings_store: SettingsStore | None = None) -> str:
    source = help_file_path().read_text(encoding="utf-8")
    stored = settings_store.get("hotkeys", {}) if settings_store is not None else {}
    hotkeys = configured_hotkeys(stored)
    rows = "".join(
        f"<tr><td><kbd>{escape(hotkeys[item.action_id])}</kbd></td>"
        f"<td>{escape(item.label)}</td></tr>"
        for item in HOTKEY_DEFINITIONS
    )
    return source.replace("{{HOTKEY_ROWS}}", rows)


def open_help(settings_store: SettingsStore | None = None) -> bool:
    rendered_path = Path(tempfile.gettempdir()) / "jdp-presenter-help.html"
    rendered_path.write_text(render_help_html(settings_store), encoding="utf-8")
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(rendered_path)))
