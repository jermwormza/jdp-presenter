"""Prompts for a recording filename + format/quality before starting a new audio recording."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.stores.recording_store import DEFAULT_FORMAT, DEFAULT_QUALITY, FORMATS, QUALITIES
from app.stores.settings_store import SettingsStore
from app.persistence.paths import RECORDINGS_DIR


_INVALID_FILENAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def sanitize_recording_name(name: str) -> str:
    """Return a file-name-safe recording stem, primarily for Windows."""
    sanitized = _INVALID_FILENAME_CHARACTERS.sub("_", name.strip())
    sanitized = re.sub(r"[ .]+$", "_", sanitized)
    if sanitized.partition(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
        sanitized += "_"
    return sanitized


def default_recording_name(service_name: str | None = None) -> str:
    if service_name:
        sanitized = sanitize_recording_name(service_name)
        if sanitized:
            return sanitized
    now = datetime.now()
    return now.strftime("%Y-%m-%d") + ("am" if now.hour < 12 else "pm")


def next_available_recording_name(directory: Path, base_name: str, ext: str) -> str:
    for number in range(1, 1000):
        candidate = f"{base_name}_{number:03d}"
        if not (directory / f"{candidate}.{ext}").exists():
            return candidate
    return f"{base_name}_999"


class RecordingOptionsDialog(QDialog):
    def __init__(
        self,
        settings_store: SettingsStore,
        parent=None,
        *,
        default_name: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start Recording")
        self._settings_store = settings_store
        self._default_name = default_recording_name(default_name)

        self._filename_edit = QLineEdit(self._default_name)
        self._filename_edit.setReadOnly(True)

        self._format_combo = QComboBox()
        self._format_combo.addItems(list(FORMATS.keys()))
        stored_format = settings_store.get("recordingFormat", DEFAULT_FORMAT)
        if stored_format in FORMATS:
            self._format_combo.setCurrentText(stored_format)

        self._quality_combo = QComboBox()
        self._quality_combo.addItems(list(QUALITIES.keys()))
        stored_quality = settings_store.get("recordingQuality", DEFAULT_QUALITY)
        if stored_quality in QUALITIES:
            self._quality_combo.setCurrentText(stored_quality)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("File name", self._filename_edit)
        form.addRow("Format", self._format_combo)
        form.addRow("Quality", self._quality_combo)
        self._remember_check = QCheckBox("Remember Settings")
        form.addRow(self._remember_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        """Validate filename doesn't exist, or prompt to overwrite/auto-rename."""
        filename = sanitize_recording_name(self._filename_edit.text()) or self._default_name
        self._filename_edit.setText(filename)
        fmt = self._format_combo.currentText()
        ext = FORMATS[fmt][2]

        # Get the output directory
        if self._settings_store:
            custom_dir = self._settings_store.get("recordingOutputDir", "")
            output_dir = Path(custom_dir) if custom_dir else RECORDINGS_DIR
        else:
            output_dir = RECORDINGS_DIR

        output_dir.mkdir(parents=True, exist_ok=True)
        target_path = output_dir / f"{filename}.{ext}"

        if target_path.exists():
            # File exists - offer overwrite, auto-rename, or cancel
            reply = QMessageBox.question(
                self,
                "File Already Exists",
                f"A recording named '{filename}.{ext}' already exists.\n\n"
                "Would you like to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return  # Keep dialog open

            if reply == QMessageBox.StandardButton.No:
                # Auto-rename with incrementing suffix
                new_name = next_available_recording_name(output_dir, filename, ext)
                self._filename_edit.setText(new_name)
                # Re-run validation with new name (recursive, but will terminate since new_name is unique)
                self._on_accept()
                return

        # Save settings and accept
        self._settings_store.set("recordingFormat", self._format_combo.currentText())
        self._settings_store.set("recordingQuality", self._quality_combo.currentText())
        if self._remember_check.isChecked():
            self._settings_store.set("recordingPromptForOptions", False)
        self.accept()

    def file_name(self) -> str:
        return sanitize_recording_name(self._filename_edit.text()) or self._default_name

    def format_name(self) -> str:
        return self._format_combo.currentText()

    def quality_name(self) -> str:
        return self._quality_combo.currentText()

    def extension(self) -> str:
        return FORMATS[self.format_name()][2]
