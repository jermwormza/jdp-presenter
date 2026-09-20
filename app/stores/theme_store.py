"""ThemeStore: edits the active service's global ServiceTheme (or a per-item DisplaySettings override)."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.models.service import DisplaySettings
from app.models.theme import ServiceTheme
from app.stores.service_store import ServiceStore


class ThemeStore(QObject):
    theme_changed = Signal(object)  # ServiceTheme | None

    def __init__(self, service_store: ServiceStore) -> None:
        super().__init__()
        self._service_store = service_store

    @property
    def theme(self) -> ServiceTheme | None:
        service = self._service_store.service
        return service.theme if service is not None else None

    def apply_theme(self, theme: ServiceTheme) -> None:
        service = self._service_store.service
        if service is None:
            return
        service.theme = theme
        self.theme_changed.emit(theme)
        self._service_store.touch()

    def apply_item_override(self, item_id: str, display_settings: DisplaySettings | None) -> None:
        self._service_store.update_item(item_id, display_settings=display_settings)
