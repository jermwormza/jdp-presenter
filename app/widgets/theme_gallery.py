"""Theme gallery dialog: browse and apply one of the prebuilt themes."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QVBoxLayout

from app.stores.theme_store import ThemeStore
from app.utils.theme_gallery import THEME_METADATA, get_prebuilt_theme


class ThemeGallery(QDialog):
    def __init__(self, theme_store: ThemeStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Theme Gallery")
        self._theme_store = theme_store

        self._list = QListWidget()
        for meta in THEME_METADATA:
            item = QListWidgetItem(f"{meta.label} — {meta.description}")
            item.setData(1, meta.key)
            self._list.addItem(item)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._apply_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addWidget(buttons)

    def _apply_and_accept(self) -> None:
        current = self._list.currentItem()
        if current is None:
            self.reject()
            return
        theme = get_prebuilt_theme(current.data(1))
        if theme is not None:
            self._theme_store.apply_theme(theme)
        self.accept()
