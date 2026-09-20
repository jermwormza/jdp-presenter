"""Recordings Pane: displays saved recordings and allows playing/deleting them."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.persistence.paths import RECORDINGS_DIR
from app.utils.icons import delete_icon, open_icon, pause_icon, play_icon, refresh_icon, stop_icon


class RecordingsPane(QWidget):
    """A pane showing saved recordings with play/delete controls."""
    
    # Signal emitted when a recording is selected for playback in the media player
    recording_selected = Signal(str)  # file path

    def __init__(self, settings_store=None, parent=None) -> None:
        super().__init__(parent)
        self._settings_store = settings_store
        self._recordings_dir = self._get_recordings_dir()
        
        # Media player for preview
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._current_item: QListWidgetItem | None = None
        self._build_ui()
        self.refresh()

    def _get_recordings_dir(self) -> Path:
        """Get the configured recording output directory or default."""
        if self._settings_store:
            custom_dir = self._settings_store.get("recordingOutputDir", "")
            if custom_dir:
                p = Path(custom_dir)
                # If the custom path is relative, resolve it against the user data directory
                # to avoid pointing to the read-only bundle data folder
                if not p.is_absolute():
                    from app.persistence.paths import _get_data_dir
                    return _get_data_dir() / p
                return p
        return RECORDINGS_DIR

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(8, 4, 8, 4)
        
        title = QLabel("Recordings")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        # Refresh button
        refresh_btn = QPushButton()
        refresh_btn.setIcon(refresh_icon())
        refresh_btn.setToolTip("Refresh recordings list")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        # Open folder button
        open_folder_btn = QPushButton()
        open_folder_btn.setIcon(open_icon())
        open_folder_btn.setToolTip("Open recordings folder")
        open_folder_btn.setFixedSize(24, 24)
        open_folder_btn.clicked.connect(self._open_recordings_folder)
        header_layout.addWidget(open_folder_btn)
        layout.addLayout(header_layout)
        # Recordings list
        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.currentItemChanged.connect(lambda *_args: self._update_controls_state())
        layout.addWidget(self._list, 1)
        # Playback controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(8, 4, 8, 8)
        
        self._play_btn = QPushButton()
        self._play_btn.setIcon(play_icon())
        self._play_btn.setToolTip("Play selected recording")
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._toggle_playback)
        controls_layout.addWidget(self._play_btn)
        
        self._stop_btn = QPushButton()
        self._stop_btn.setIcon(stop_icon())
        self._stop_btn.setToolTip("Stop playback")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_playback)
        controls_layout.addWidget(self._stop_btn)
        
        controls_layout.addStretch()
        
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setStyleSheet("color: #888; font-family: monospace; font-size: 11px;")
        controls_layout.addWidget(self._time_label)
        
        layout.addLayout(controls_layout)
        # Connect player signals
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.errorOccurred.connect(self._on_player_error)

    def refresh(self) -> None:
        """Reload the recordings list from disk."""
        self._recordings_dir = self._get_recordings_dir()
        self._recordings_dir.mkdir(parents=True, exist_ok=True)
        
        self._list.clear()
        
        # Get all audio files, sorted by modification time (newest first)
        audio_extensions = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
        files = []
        for ext in audio_extensions:
            files.extend(self._recordings_dir.glob(f"*{ext}"))
        
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        for file_path in files:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(file_path))
            item.setToolTip(str(file_path))
            
            # Format display name with size and date
            stat = file_path.stat()
            size_mb = stat.st_size / (1024 * 1024)
            from datetime import datetime
            mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            
            display_text = f"{file_path.stem}\n{mod_time}  •  {size_mb:.1f} MB"
            item.setText(display_text)
            
            self._list.addItem(item)
        
        # Auto-select the newest recording so the play button works immediately.
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        
        self._update_controls_state()

    def _update_controls_state(self) -> None:
        has_selection = self._list.currentItem() is not None
        self._play_btn.setEnabled(has_selection)
        
        is_playing = self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self._stop_btn.setEnabled(is_playing)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._play_recording(item)

    def _show_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        
        menu = QMenu(self)
        
        play_action = menu.addAction("Play")
        play_action.triggered.connect(lambda: self._play_recording(item))
        
        menu.addSeparator()
        
        delete_action = menu.addAction("Delete")
        delete_action.setIcon(delete_icon())
        delete_action.triggered.connect(lambda: self._delete_recording(item))
        
        menu.addSeparator()
        
        if sys.platform == "darwin":
            file_manager = "Finder"
        elif sys.platform == "win32":
            file_manager = "Explorer"
        else:
            file_manager = "File Manager"
        open_folder_action = menu.addAction(f"Show In {file_manager}")
        open_folder_action.triggered.connect(lambda: self._show_in_file_manager(item))
        
        menu.exec(self._list.mapToGlobal(pos))

    def _play_recording(self, item: QListWidgetItem) -> None:
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", "Recording file not found.")
            return
        
        # Stop current playback if any
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.stop()
        
        self._current_item = item
        self._player.setSource(QUrl.fromLocalFile(file_path))
        self._player.play()

    def _toggle_playback(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            item = self._list.currentItem()
            if item is None and self._list.count() > 0:
                # Nothing selected — fall back to the newest recording.
                item = self._list.item(0)
                self._list.setCurrentItem(item)
            if item:
                self._play_recording(item)

    def _stop_playback(self) -> None:
        self._player.stop()
        self._current_item = None

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setIcon(pause_icon())
            self._play_btn.setToolTip("Pause")
            self._stop_btn.setEnabled(True)
        else:
            self._play_btn.setIcon(play_icon())
            self._play_btn.setToolTip("Play")
            self._stop_btn.setEnabled(False)

    def _on_position_changed(self, position: int) -> None:
        duration = self._player.duration()
        self._time_label.setText(f"{self._format_time(position)} / {self._format_time(duration)}")

    def _on_duration_changed(self, duration: int) -> None:
        position = self._player.position()
        self._time_label.setText(f"{self._format_time(position)} / {self._format_time(duration)}")

    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        if error != QMediaPlayer.Error.NoError:
            QMessageBox.warning(self, "Playback Error", f"Could not play recording:\n{error_string}")

    def _format_time(self, ms: int) -> str:
        total_seconds = ms // 1000
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def _delete_recording(self, item: QListWidgetItem) -> None:
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return
        
        reply = QMessageBox.question(
            self, "Delete Recording",
            f"Delete '{os.path.basename(file_path)}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(file_path)
                self.refresh()
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Could not delete file:\n{e}")

    def _open_recordings_folder(self) -> None:
        """Open the recordings folder in system file manager."""
        path = str(self._recordings_dir)
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as exc:
            QMessageBox.warning(self, "Open Recordings Folder", str(exc))

    def _show_in_file_manager(self, item: QListWidgetItem) -> None:
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path or not os.path.exists(file_path):
            return

        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", file_path])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", file_path])
            else:
                subprocess.Popen(["xdg-open", str(Path(file_path).parent)])
        except OSError as exc:
            QMessageBox.warning(self, "Show Recording", str(exc))