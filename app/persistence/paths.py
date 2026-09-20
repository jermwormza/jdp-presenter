"""Central on-disk paths for preferences and user-selectable content libraries."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = APP_ROOT.parent

if getattr(sys, "frozen", False):
    if sys.platform == "darwin":
        CONFIG_DIR = Path.home() / "Library" / "Application Support" / "JDP Presenter"
        DEFAULT_DATA_DIR = CONFIG_DIR
    elif sys.platform == "win32":
        CONFIG_DIR = Path(
            os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        ) / "JDP Presenter"
        DEFAULT_DATA_DIR = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "jdp-presenter"
    else:
        CONFIG_DIR = Path.home() / ".config" / "jdp-presenter"
        DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "JDP Presenter"
else:
    CONFIG_DIR = PROJECT_ROOT / "data"
    DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

USER_DATA_DIR = DEFAULT_DATA_DIR
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Initialize data directory on first run
_initialized = False

def _ensure_data_initialized() -> None:
    """Copy bundled data for package formats that include seed data inside the bundle."""
    global _initialized
    if _initialized:
        return
    _initialized = True
    
    if not getattr(sys, 'frozen', False):
        return  # Development mode - use project data directly
    
    marker_file = DEFAULT_DATA_DIR / ".initialized"
    if marker_file.exists():
        return  # Already initialized
    
    # Get bundled data path (available at runtime via sys._MEIPASS)
    bundled_data = Path(getattr(sys, "_MEIPASS", "")) / "data"
    
    # Copy bundled data to user data directory
    if bundled_data.exists():
        DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
        for item in bundled_data.iterdir():
            dest = DEFAULT_DATA_DIR / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
    
        marker_file.write_text("initialized", encoding="utf-8")


def _load_path_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _configured_directory(setting_key: str, default_subpath: str) -> Path:
    configured = _load_path_settings().get(setting_key)
    if isinstance(configured, str) and configured.strip():
        return Path(os.path.expandvars(configured)).expanduser()
    return DEFAULT_DATA_DIR / default_subpath

def _get_data_dir() -> Path:
    _ensure_data_initialized()
    return DEFAULT_DATA_DIR

# Module-level constants that lazily initialize
class _LazyDir:
    def __init__(
        self,
        subpath: str,
        setting_key: str | None = None,
        configured_subpath: str = "",
    ) -> None:
        self._subpath = subpath
        self._setting_key = setting_key
        self._configured_subpath = configured_subpath
        self._path: Path | None = None
    
    @property
    def path(self) -> Path:
        if self._path is None:
            _ensure_data_initialized()
            self._path = (
                _configured_directory(self._setting_key, self._subpath)
                / self._configured_subpath
                if self._setting_key
                else _get_data_dir() / self._subpath
            )
            self._path.mkdir(parents=True, exist_ok=True)
        return self._path
    
    def __truediv__(self, other) -> Path:
        return self.path / other
    
    def __str__(self) -> str:
        return str(self.path)
    
    def __fspath__(self) -> str:
        return str(self.path)
    
    def __getattr__(self, name):
        return getattr(self.path, name)

class _LazyFile:
    def __init__(
        self,
        subpath: str,
        setting_key: str | None = None,
        configured_name: str = "",
    ) -> None:
        self._subpath = subpath
        self._setting_key = setting_key
        self._configured_name = configured_name
        self._path: Path | None = None
    
    @property
    def path(self) -> Path:
        if self._path is None:
            self._path = (
                _configured_directory(self._setting_key, str(Path(self._subpath).parent))
                / self._configured_name
                if self._setting_key
                else _get_data_dir() / self._subpath
            )
            self._path.parent.mkdir(parents=True, exist_ok=True)
        return self._path
    
    def __truediv__(self, other) -> Path:
        return self.path / other
    
    def __str__(self) -> str:
        return str(self.path)
    
    def __fspath__(self) -> str:
        return str(self.path)
    
    def __getattr__(self, name):
        return getattr(self.path, name)

# Lazy-initialized paths (directories)
SERVICES_DIR = _LazyDir("services", "servicesDirectory")
SONGS_DIR = _LazyDir("songs", "songsDirectory")
BIBLES_DIR = _LazyDir("bibles", "biblesDirectory")
MEDIA_DIR = _LazyDir("media", "mediaDirectory")
MEDIA_IMAGES_DIR = _LazyDir("media/images", "mediaDirectory", "images")
MEDIA_VIDEOS_DIR = _LazyDir("media/videos", "mediaDirectory", "videos")
MEDIA_AUDIO_DIR = _LazyDir("media/audio", "mediaDirectory", "audio")
RECORDINGS_DIR = _LazyDir("recordings", "recordingsDirectory")

# Lazy-initialized paths (files)
BIBLES_INDEX_FILE = _LazyFile("bibles/index.json", "biblesDirectory", "index.json")

# For backwards compatibility
DATA_DIR = _LazyDir("")
