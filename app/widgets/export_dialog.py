"""Export the current service as an outline or full markdown, with copy/save actions."""
from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.models.service import Service
from app.utils.exporters import generate_full_markdown, generate_outline


class ExportDialog(QDialog):
    def __init__(self, service: Service, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Service")
        self._service = service

        self._format_combo = QComboBox()
        self._format_combo.addItems(["Summary", "Full Service"])
        self._format_combo.currentIndexChanged.connect(self._refresh_preview)

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)

        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(self._copy)
        save_button = QPushButton("Save As…")
        save_button.clicked.connect(self._save)

        button_row = QHBoxLayout()
        button_row.addWidget(copy_button)
        button_row.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._format_combo)
        layout.addWidget(self._preview)
        layout.addLayout(button_row)

        self._refresh_preview()

    def _current_text(self) -> str:
        if self._format_combo.currentIndex() == 0:
            return generate_outline(self._service)
        return generate_full_markdown(self._service)

    def _refresh_preview(self, *_args) -> None:
        self._preview.setPlainText(self._current_text())

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._current_text())

    def _save(self) -> None:
        is_markdown = self._format_combo.currentIndex() == 1
        suffix = "md" if is_markdown else "txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Export", f"{self._service.name}.{suffix}", f"*.{suffix}"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._current_text())
