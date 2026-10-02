"""Resolve and open the bundled HTML help guide."""
from __future__ import annotations

import base64
import re
import sys
import tempfile
from collections.abc import Callable
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QBuffer, QIODevice, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon

from app.utils import icons
from app.utils.hotkeys import HOTKEY_DEFINITIONS, configured_hotkeys

if TYPE_CHECKING:
    from app.stores.settings_store import SettingsStore

_ICON_PLACEHOLDER_RE = re.compile(r"\{\{ICON:([a-z_]+)\}\}")
_ICON_RENDER_SIZE = 22
# Toolbar icons referenced from the help page as {{ICON:name}}; rendered from the same
# factories the Control window uses so the guide always matches the running app.
HELP_ICONS: dict[str, Callable[[], QIcon]] = {
    "new": icons.new_icon,
    "open": icons.open_icon,
    "save": icons.save_icon,
    "import": icons.import_icon,
    "export": icons.export_icon,
    "print": icons.print_icon,
    "record": icons.record_icon,
    "stop": icons.stop_icon,
    "song": icons.song_icon,
    "scripture": icons.scripture_icon,
    "text": icons.text_icon,
    "media": icons.media_icon,
    "move_up": icons.move_up_icon,
    "move_down": icons.move_down_icon,
    "delete": icons.delete_icon,
    "play": icons.play_icon,
    "pause": icons.pause_icon,
    "qr": icons.qr_icon,
    "output_screen": icons.output_screen_icon,
}


def help_file_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "help" / "index.html"
    return Path(__file__).resolve().parents[1] / "resources" / "help" / "index.html"


def icon_data_uri(icon: QIcon, size: int = _ICON_RENDER_SIZE) -> str:
    """Encode an icon as a PNG data URI (rendered at 2x for crisp display on HiDPI screens)."""
    pixmap = icon.pixmap(size * 2, size * 2)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    encoded = base64.b64encode(bytes(buffer.data())).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _render_icon_placeholders(source: str) -> str:
    if QGuiApplication.instance() is None:
        return _ICON_PLACEHOLDER_RE.sub("", source)

    def replace(match: re.Match[str]) -> str:
        factory = HELP_ICONS.get(match.group(1))
        if factory is None:
            return ""
        return (
            f'<img class="icon" width="{_ICON_RENDER_SIZE}" height="{_ICON_RENDER_SIZE}" '
            f'src="{icon_data_uri(factory())}" alt="">'
        )

    return _ICON_PLACEHOLDER_RE.sub(replace, source)


def render_help_html(settings_store: SettingsStore | None = None) -> str:
    source = help_file_path().read_text(encoding="utf-8")
    stored = settings_store.get("hotkeys", {}) if settings_store is not None else {}
    hotkeys = configured_hotkeys(stored)
    rows = "".join(
        f"<tr><td><kbd>{escape(hotkeys[item.action_id])}</kbd></td>"
        f"<td>{escape(item.label)}</td></tr>"
        for item in HOTKEY_DEFINITIONS
    )
    return _render_icon_placeholders(source.replace("{{HOTKEY_ROWS}}", rows))


def open_help(settings_store: SettingsStore | None = None) -> bool:
    rendered_path = Path(tempfile.gettempdir()) / "jdp-presenter-help.html"
    rendered_path.write_text(render_help_html(settings_store), encoding="utf-8")
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(rendered_path)))
