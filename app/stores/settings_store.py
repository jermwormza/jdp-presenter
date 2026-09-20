"""SettingsStore: flat app preferences, backed by data/settings.json."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from app.persistence import settings_repo


class SettingsStore(QObject):
    settings_changed = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._settings: dict[str, Any] = settings_repo.load_settings()

    @property
    def settings(self) -> dict[str, Any]:
        return self._settings

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        settings_repo.save_settings(self._settings)
        self.settings_changed.emit(self._settings)
