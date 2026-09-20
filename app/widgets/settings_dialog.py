"""Settings dialog: comprehensive app preferences with vertical tab navigation."""
from __future__ import annotations

from pathlib import Path
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.stores.settings_store import SettingsStore
from app.utils.hotkeys import (
    DEFAULT_HOTKEYS,
    HOTKEY_DEFINITIONS,
    configured_hotkeys,
    conflicting_action,
    hotkey_label,
)
from app.widgets.hotkey_capture_button import HotkeyCaptureButton
from app.persistence.paths import (
    BIBLES_DIR,
    MEDIA_DIR,
    RECORDINGS_DIR,
    SERVICES_DIR,
    SONGS_DIR,
)


class SettingsDialog(QDialog):
    def __init__(self, settings_store: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(860, 560)
        self.setMinimumSize(760, 500)
        self._settings_store = settings_store

        # Sidebar list
        self._list = QListWidget()
        self._list.setFrameShape(QListWidget.Shape.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._list.currentRowChanged.connect(self._on_page_changed)

        # Pages stack
        self._stack = QStackedWidget()

        # Build pages
        self._general_page = self._build_general_page()
        self._storage_page = self._build_storage_page()
        self._output_page = self._build_output_page()
        self._audio_page = self._build_audio_page()
        self._recording_page = self._build_recording_page()
        self._hotkeys_page = self._build_hotkeys_page()
        self._remote_page = self._build_remote_page()
        self._integrations_page = self._build_integrations_page()

        self._stack.addWidget(self._general_page)
        self._stack.addWidget(self._output_page)
        self._stack.addWidget(self._audio_page)
        self._stack.addWidget(self._recording_page)
        self._stack.addWidget(self._hotkeys_page)
        self._stack.addWidget(self._storage_page)
        self._stack.addWidget(self._remote_page)
        self._stack.addWidget(self._integrations_page)

        for title in (
            "General",
            "Presentation",
            "Audio",
            "Recording",
            "Keyboard Shortcuts",
            "Libraries",
            "Remote Control",
            "Integrations",
        ):
            item = QListWidgetItem(title)
            self._list.addItem(item)
        sidebar_width = max(
            self._list.fontMetrics().horizontalAdvance(self._list.item(index).text())
            for index in range(self._list.count())
        ) + 36
        self._list.setFixedWidth(sidebar_width)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)

        # Layout
        content_layout = QHBoxLayout()
        content_layout.addWidget(self._list)
        content_layout.addWidget(self._stack, 1)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(content_layout, 1)
        main_layout.addWidget(buttons)

        self._list.setCurrentRow(0)

    def _build_general_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._auto_save_check = QCheckBox("Auto-save service on changes")
        self._auto_save_check.setChecked(self._settings_store.get("autoSave", False))
        form.addRow(self._auto_save_check)

        self._confirm_delete_check = QCheckBox("Confirm before deleting items")
        self._confirm_delete_check.setChecked(self._settings_store.get("confirmDelete", True))
        form.addRow(self._confirm_delete_check)

        self._remember_window_check = QCheckBox("Remember window positions and sizes")
        self._remember_window_check.setChecked(self._settings_store.get("rememberWindowState", True))
        form.addRow(self._remember_window_check)

        self._check_updates_check = QCheckBox("Check for new versions on startup")
        self._check_updates_check.setChecked(
            bool(self._settings_store.get("checkForUpdatesOnStartup", True))
        )
        form.addRow(self._check_updates_check)

        return page

    def _build_integrations_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._openai_key_edit = QLineEdit(self._settings_store.get("openaiApiKey", ""))
        self._openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_key_edit.setPlaceholderText("Enter OpenAI API key")
        form.addRow("OpenAI API Key", self._openai_key_edit)

        self._dropbox_key_edit = QLineEdit(self._settings_store.get("dropboxAppKey", ""))
        self._dropbox_key_edit.setPlaceholderText("Deferred — not yet implemented")
        self._dropbox_key_edit.setEnabled(False)
        form.addRow("Dropbox App Key", self._dropbox_key_edit)

        return page

    def _build_storage_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._directory_edits: dict[str, QLineEdit] = {}

        directories = (
            ("Bibles", "biblesDirectory", str(BIBLES_DIR)),
            ("Songs", "songsDirectory", str(SONGS_DIR)),
            ("Services", "servicesDirectory", str(SERVICES_DIR)),
            ("Media", "mediaDirectory", str(MEDIA_DIR)),
        )
        for label, setting_key, default_path in directories:
            edit = QLineEdit(self._settings_store.get(setting_key, default_path))
            edit.setReadOnly(True)
            browse_button = QPushButton("Browse...")
            browse_button.clicked.connect(partial(self._browse_directory, setting_key, edit))
            row = QHBoxLayout()
            row.addWidget(edit)
            row.addWidget(browse_button)
            form.addRow(label, row)
            self._directory_edits[setting_key] = edit

        note = QLabel("Location changes take effect after JDP Presenter restarts.")
        note.setWordWrap(True)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch()
        return page

    def _browse_directory(self, setting_key: str, edit: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Library Folder",
            edit.text(),
        )
        if selected:
            edit.setText(selected)

    def _build_output_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._canvas_ratio_combo = QComboBox()
        self._canvas_ratio_combo.addItems(["4:3", "16:9", "16:10"])
        stored_ratio = self._settings_store.get("canvasRatio", "16:9")
        if stored_ratio in ("4:3", "16:9", "16:10"):
            self._canvas_ratio_combo.setCurrentText(stored_ratio)
        form.addRow("Default Aspect Ratio", self._canvas_ratio_combo)

        self._font_scale_spin = QSpinBox()
        self._font_scale_spin.setRange(50, 300)
        self._font_scale_spin.setSuffix("%")
        self._font_scale_spin.setValue(int(self._settings_store.get("fontScale", 1.0) * 100))
        form.addRow("Default Font Scale", self._font_scale_spin)

        self._media_scale_combo = QComboBox()
        self._media_scale_combo.addItems(["Fit", "Original", "Fill Width", "Fill Height"])
        # Map stored mode to display
        mode_map = {"fit": 0, "original": 1, "fill_width": 2, "fill_height": 3}
        stored_mode = self._settings_store.get("mediaScaleMode", "fit")
        self._media_scale_combo.setCurrentIndex(mode_map.get(stored_mode, 0))
        form.addRow("Default Media Scale", self._media_scale_combo)

        self._auto_advance_check = QCheckBox("Auto-advance to next item after last slide")
        self._auto_advance_check.setChecked(self._settings_store.get("autoAdvance", True))
        form.addRow(self._auto_advance_check)

        return page

    def _build_audio_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._audio_input_combo = QComboBox()
        self._audio_input_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._audio_input_combo.setMinimumContentsLength(24)
        self._populate_audio_inputs()
        stored_input = self._settings_store.get("audioInputDevice", "")
        if stored_input:
            index = self._audio_input_combo.findData(stored_input)
            if index >= 0:
                self._audio_input_combo.setCurrentIndex(index)
        form.addRow("Recording Input", self._audio_input_combo)

        self._audio_output_combo = QComboBox()
        self._audio_output_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._audio_output_combo.setMinimumContentsLength(24)
        self._populate_audio_outputs()
        stored_output = self._settings_store.get("audioOutputDevice", "")
        if stored_output:
            index = self._audio_output_combo.findData(stored_output)
            if index >= 0:
                self._audio_output_combo.setCurrentIndex(index)
        form.addRow("Monitoring Output", self._audio_output_combo)

        return page

    def _build_recording_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._rec_format_combo = QComboBox()
        self._rec_format_combo.addItems(["MP3", "WAV", "AAC (M4A)"])
        stored_fmt = self._settings_store.get("recordingFormat", "MP3")
        if stored_fmt in ("MP3", "WAV", "AAC (M4A)"):
            self._rec_format_combo.setCurrentText(stored_fmt)
        form.addRow("Default Format", self._rec_format_combo)

        self._rec_quality_combo = QComboBox()
        self._rec_quality_combo.addItems(["Low", "Normal", "High", "Very High"])
        stored_qual = self._settings_store.get("recordingQuality", "Low")
        if stored_qual in ("Low", "Normal", "High", "Very High"):
            self._rec_quality_combo.setCurrentText(stored_qual)
        form.addRow("Default Quality", self._rec_quality_combo)

        self._rec_dir_edit = QLineEdit(self._settings_store.get("recordingOutputDir", ""))
        self._rec_dir_edit.setPlaceholderText(f"Default: {RECORDINGS_DIR}")
        self._rec_dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_recording_dir)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self._rec_dir_edit)
        dir_layout.addWidget(browse_btn)
        form.addRow("Output Folder", dir_layout)

        self._recording_prompt_check = QCheckBox("Always prompt when starting a recording")
        self._recording_prompt_check.setChecked(
            bool(self._settings_store.get("recordingPromptForOptions", True))
        )
        form.addRow(self._recording_prompt_check)

        return page

    def _build_hotkeys_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._hotkey_values = configured_hotkeys(self._settings_store.get("hotkeys", {}))
        self._hotkey_buttons: dict[str, HotkeyCaptureButton] = {}
        for definition in HOTKEY_DEFINITIONS:
            button = HotkeyCaptureButton(self._hotkey_values[definition.action_id])
            button.sequence_captured.connect(
                partial(self._on_hotkey_captured, definition.action_id)
            )
            self._hotkey_buttons[definition.action_id] = button
            form.addRow(definition.label, button)

        restore_button = QPushButton("Restore Defaults")
        restore_button.clicked.connect(self._restore_default_hotkeys)
        layout.addLayout(form)
        layout.addWidget(restore_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        return page

    def _on_hotkey_captured(self, action_id: str, sequence: str) -> None:
        conflict = conflicting_action(self._hotkey_values, action_id, sequence)
        if conflict is not None:
            self._hotkey_buttons[action_id].set_sequence(self._hotkey_values[action_id])
            QMessageBox.warning(
                self,
                "Shortcut Already Used",
                f"That shortcut is already assigned to {hotkey_label(conflict)}.",
            )
            return
        self._hotkey_values[action_id] = sequence

    def _restore_default_hotkeys(self) -> None:
        self._hotkey_values = DEFAULT_HOTKEYS.copy()
        for action_id, button in self._hotkey_buttons.items():
            button.set_sequence(self._hotkey_values[action_id])

    def _populate_audio_inputs(self) -> None:
        self._audio_input_combo.clear()
        self._audio_input_combo.addItem("System Default", "")  # Empty string = default
        for device in QMediaDevices.audioInputs():
            self._audio_input_combo.addItem(device.description(), device.id().data().decode())

    def _populate_audio_outputs(self) -> None:
        self._audio_output_combo.clear()
        self._audio_output_combo.addItem("System Default", "")  # Empty string = default
        for device in QMediaDevices.audioOutputs():
            self._audio_output_combo.addItem(device.description(), device.id().data().decode())

    def _browse_recording_dir(self) -> None:
        current = self._rec_dir_edit.text()
        if not current:
            from app.persistence.paths import RECORDINGS_DIR
            current = str(RECORDINGS_DIR)
        dir_path = QFileDialog.getExistingDirectory(self, "Select Recording Output Folder", current)
        if dir_path:
            self._rec_dir_edit.setText(dir_path)

    def _build_remote_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._remote_port_spin = QSpinBox()
        self._remote_port_spin.setRange(1024, 65535)
        self._remote_port_spin.setValue(self._settings_store.get("remotePort", 5183))
        form.addRow("Remote Control Port", self._remote_port_spin)

        self._qr_auto_check = QCheckBox("Auto-show QR code when remote server starts")
        self._qr_auto_check.setChecked(self._settings_store.get("qrAutoShow", False))
        form.addRow(self._qr_auto_check)

        return page

    def _on_page_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def _save_and_accept(self) -> None:
        storage_changed = any(
            edit.text() != self._settings_store.get(setting_key, edit.text())
            for setting_key, edit in self._directory_edits.items()
        )

        # Integrations
        self._settings_store.set("openaiApiKey", self._openai_key_edit.text())
        self._settings_store.set("dropboxAppKey", self._dropbox_key_edit.text())

        # Output
        self._settings_store.set("canvasRatio", self._canvas_ratio_combo.currentText())
        self._settings_store.set("fontScale", self._font_scale_spin.value() / 100.0)
        mode_map = {0: "fit", 1: "original", 2: "fill_width", 3: "fill_height"}
        self._settings_store.set("mediaScaleMode", mode_map[self._media_scale_combo.currentIndex()])
        self._settings_store.set("autoAdvance", self._auto_advance_check.isChecked())

        # Recording and audio
        self._settings_store.set("recordingFormat", self._rec_format_combo.currentText())
        self._settings_store.set("recordingQuality", self._rec_quality_combo.currentText())
        self._settings_store.set("recordingOutputDir", self._rec_dir_edit.text())
        self._settings_store.set(
            "recordingPromptForOptions", self._recording_prompt_check.isChecked()
        )
        self._settings_store.set("audioInputDevice", self._audio_input_combo.currentData() or "")
        self._settings_store.set("audioOutputDevice", self._audio_output_combo.currentData() or "")

        # Keyboard shortcuts
        self._settings_store.set("hotkeys", self._hotkey_values.copy())

        # Storage
        for setting_key, edit in self._directory_edits.items():
            self._settings_store.set(setting_key, edit.text())

        # Remote
        self._settings_store.set("remotePort", self._remote_port_spin.value())
        self._settings_store.set("qrAutoShow", self._qr_auto_check.isChecked())

        # General
        self._settings_store.set("autoSave", self._auto_save_check.isChecked())
        self._settings_store.set("confirmDelete", self._confirm_delete_check.isChecked())
        self._settings_store.set("rememberWindowState", self._remember_window_check.isChecked())
        self._settings_store.set(
            "checkForUpdatesOnStartup", self._check_updates_check.isChecked()
        )

        if storage_changed:
            QMessageBox.information(
                self,
                "Restart Required",
                "Restart JDP Presenter to use the new storage locations.",
            )
        self.accept()
