"""Media browser dialog: pick an image/video/audio file from the data/media library and insert it,
or add a file straight from disk without saving it into the library.
"""
from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.service import AudioItem, ImageItem, Slide, VideoItem
from app.persistence import media_library_repo
from app.persistence.paths import MEDIA_AUDIO_DIR, MEDIA_IMAGES_DIR, MEDIA_VIDEOS_DIR
from app.stores.service_store import ServiceStore
from app.utils.icons import pause_icon, play_icon

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

_CATEGORIES = {
    "Images": (MEDIA_IMAGES_DIR, IMAGE_EXTENSIONS),
    "Videos": (MEDIA_VIDEOS_DIR, VIDEO_EXTENSIONS),
    "Audio": (MEDIA_AUDIO_DIR, AUDIO_EXTENSIONS),
}

_SCALE_MODES = [("fit", "Fit"), ("original", "Original"), ("fill_width", "Fill Width"), ("fill_height", "Fill Height")]


def _category_for_path(path: Path) -> str | None:
    suffix = path.suffix.lower()
    for category, (_directory, extensions) in _CATEGORIES.items():
        if suffix in extensions:
            return category
    return None


class MediaBrowser(QDialog):
    def __init__(self, service_store: ServiceStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Insert Media")
        self.resize(1000, 620)
        self._service_store = service_store

        self._category_combo = QComboBox()
        self._category_combo.addItems(list(_CATEGORIES.keys()))
        self._category_combo.currentTextChanged.connect(self._refresh_list)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._update_preview)

        import_button = QPushButton("Import to Library")
        import_button.setToolTip("Copy files or a folder into the reusable media library")
        import_menu = QMenu(import_button)
        import_menu.addAction("Files...", self._import_files)
        import_menu.addAction("Folder...", self._import_folder)
        import_button.setMenu(import_menu)
        add_from_disk_button = QPushButton("Add from Disk…")
        add_from_disk_button.setToolTip("Insert a file directly without saving it into the library")
        add_from_disk_button.clicked.connect(self._add_from_disk)
        delete_button = QPushButton("Delete from Library…")
        delete_button.clicked.connect(self._delete_from_library)
        insert_button = QPushButton("Insert")
        insert_button.clicked.connect(self._insert)

        button_row = QHBoxLayout()
        button_row.addWidget(import_button)
        button_row.addWidget(add_from_disk_button)
        button_row.addWidget(delete_button)
        button_row.addWidget(insert_button)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        left_layout.addWidget(QLabel("Category"))
        left_layout.addWidget(self._category_combo)
        left_layout.addWidget(self._list, stretch=1)
        left_layout.addLayout(button_row)

        # --- Preview: image label / video widget, plus play/pause + seek for video & audio ---
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._video_widget = QVideoWidget()

        self._preview_stack = QStackedWidget()
        self._preview_stack.addWidget(self._image_label)
        self._preview_stack.addWidget(self._video_widget)

        self._preview_player = QMediaPlayer(self)
        self._preview_audio = QAudioOutput(self)
        self._preview_player.setAudioOutput(self._preview_audio)
        self._preview_player.setVideoOutput(self._video_widget)
        self._preview_player.playingChanged.connect(self._on_preview_playing_changed)

        self._preview_play_button = QPushButton()
        self._preview_play_button.setIcon(play_icon())
        self._preview_play_button.setEnabled(False)
        self._preview_play_button.clicked.connect(self._toggle_preview_playback)

        self._preview_slider = QSlider(Qt.Orientation.Horizontal)
        self._preview_slider.setRange(0, 0)
        self._preview_slider.setEnabled(False)
        self._preview_slider.sliderMoved.connect(self._preview_player.setPosition)

        self._preview_player.durationChanged.connect(lambda ms: self._preview_slider.setMaximum(int(ms)))
        self._preview_player.positionChanged.connect(self._on_preview_position_changed)

        preview_controls = QHBoxLayout()
        preview_controls.addWidget(self._preview_play_button)
        preview_controls.addWidget(self._preview_slider, stretch=1)

        self._scale_mode_combo = QComboBox()
        for value, label in _SCALE_MODES:
            self._scale_mode_combo.addItem(label, value)
        self._scale_mode_combo.setEnabled(False)
        self._scale_mode_combo.currentIndexChanged.connect(self._on_scale_mode_changed)
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Library scale:"))
        scale_row.addWidget(self._scale_mode_combo, stretch=1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        right_layout.addWidget(QLabel("Preview"))
        right_layout.addWidget(self._preview_stack, stretch=1)
        right_layout.addLayout(preview_controls)
        right_layout.addLayout(scale_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 680])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self._refresh_list()

    def _current_category(self) -> tuple[Path, set[str]]:
        return _CATEGORIES[self._category_combo.currentText()]

    def _refresh_list(self, *_args) -> None:
        self._list.clear()
        directory, extensions = self._current_category()
        directory.mkdir(parents=True, exist_ok=True)
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix.lower() in extensions:
                list_item = QListWidgetItem(path.name)
                list_item.setData(Qt.ItemDataRole.UserRole, str(path))
                self._list.addItem(list_item)
        self._update_preview()

    def _update_preview(self, *_args) -> None:
        self._preview_player.stop()
        self._preview_player.setSource(QUrl())
        current = self._list.currentItem()
        category = self._category_combo.currentText()

        if current is None:
            self._preview_stack.setCurrentWidget(self._image_label)
            self._image_label.setPixmap(QPixmap())
            self._image_label.setText("No file selected")
            self._preview_play_button.setEnabled(False)
            self._preview_slider.setEnabled(False)
            self._scale_mode_combo.setEnabled(False)
            return

        path = Path(current.data(Qt.ItemDataRole.UserRole))

        if category == "Images":
            self._preview_stack.setCurrentWidget(self._image_label)
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self._image_label.setText("Could not load image")
            else:
                self._image_label.setPixmap(
                    pixmap.scaled(
                        self._image_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self._preview_play_button.setEnabled(False)
            self._preview_slider.setEnabled(False)
        elif category == "Videos":
            self._preview_stack.setCurrentWidget(self._video_widget)
            self._preview_player.setSource(QUrl.fromLocalFile(str(path)))
            self._preview_play_button.setEnabled(True)
            self._preview_slider.setEnabled(True)
        else:  # Audio — no visual, but still previewable via play/pause
            self._preview_stack.setCurrentWidget(self._image_label)
            self._image_label.setPixmap(QPixmap())
            self._image_label.setText(f"🔊  {path.name}")
            self._preview_player.setSource(QUrl.fromLocalFile(str(path)))
            self._preview_play_button.setEnabled(True)
            self._preview_slider.setEnabled(True)

        self._scale_mode_combo.setEnabled(category in ("Images", "Videos"))
        if category in ("Images", "Videos"):
            stored_mode = media_library_repo.get_scale_mode(str(path))
            index = self._scale_mode_combo.findData(stored_mode)
            self._scale_mode_combo.blockSignals(True)
            self._scale_mode_combo.setCurrentIndex(index if index >= 0 else 0)
            self._scale_mode_combo.blockSignals(False)

    def _toggle_preview_playback(self) -> None:
        if self._preview_player.isPlaying():
            self._preview_player.pause()
        else:
            self._preview_player.play()

    def _on_preview_playing_changed(self, is_playing: bool) -> None:
        self._preview_play_button.setIcon(pause_icon() if is_playing else play_icon())

    def _on_preview_position_changed(self, position_ms: int) -> None:
        if not self._preview_slider.isSliderDown():
            self._preview_slider.setValue(int(position_ms))

    def _on_scale_mode_changed(self, _index: int) -> None:
        current = self._list.currentItem()
        if current is None:
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        media_library_repo.set_scale_mode(path, self._scale_mode_combo.currentData())

    def _import_files(self) -> None:
        all_extensions = sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS)
        filter_str = f"Media Files (*{' *'.join(all_extensions)})"
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Media Files", "", filter_str
        )
        if not file_paths:
            return
        self._import_paths(Path(file_path) for file_path in file_paths)

    def _import_folder(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(self, "Import Media Folder")
        if not folder_path:
            return
        self._import_paths(path for path in Path(folder_path).rglob("*") if path.is_file())

    def _import_paths(self, paths: Iterable[Path]) -> None:
        imported = 0
        skipped = 0
        errors: list[str] = []

        for source in paths:
            category = _category_for_path(source)
            if category is None:
                skipped += 1
                continue
            directory, _extensions = _CATEGORIES[category]
            directory.mkdir(parents=True, exist_ok=True)
            destination = self._available_destination(directory, source.name)
            try:
                shutil.copy2(source, destination)
                imported += 1
            except OSError as exc:
                errors.append(f"{source.name}: {exc}")

        self._refresh_list()
        message = f"Imported {imported} media file{'s' if imported != 1 else ''}."
        if skipped:
            message += f" Skipped {skipped} unsupported file{'s' if skipped != 1 else ''}."
        if errors:
            message += "\n\nCould not import:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                message += f"\n...and {len(errors) - 10} more."
            QMessageBox.warning(self, "Import Media", message)
        else:
            QMessageBox.information(self, "Import Media", message)

    @staticmethod
    def _available_destination(directory: Path, file_name: str) -> Path:
        destination = directory / file_name
        if not destination.exists():
            return destination

        source_name = Path(file_name)
        counter = 2
        while True:
            destination = directory / f"{source_name.stem} ({counter}){source_name.suffix}"
            if not destination.exists():
                return destination
            counter += 1

    def _add_from_disk(self) -> None:
        if self._service_store.service is None:
            QMessageBox.warning(self, "Add from Disk", "No service is open.")
            return
        all_extensions = sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS)
        filter_str = f"Media Files (*{' *'.join(all_extensions)})"
        file_path, _ = QFileDialog.getOpenFileName(self, "Add Media from Disk", "", filter_str)
        if not file_path:
            return
        path = Path(file_path)
        category = _category_for_path(path)
        if category is None:
            QMessageBox.warning(self, "Add from Disk", "Unsupported file type.")
            return
        self._insert_item(category, str(path), scale_mode="fit")
        self.accept()

    def _delete_from_library(self) -> None:
        current = self._list.currentItem()
        if current is None:
            QMessageBox.warning(self, "Delete from Library", "Select a file first.")
            return
        path = Path(current.data(Qt.ItemDataRole.UserRole))
        confirm = QMessageBox.question(
            self, "Delete from Library", f'Delete "{path.name}" from the library? This cannot be undone.'
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Delete from Library", str(exc))
            return
        media_library_repo.remove_entry(str(path))
        self._refresh_list()

    def _insert(self) -> None:
        if self._service_store.service is None:
            QMessageBox.warning(self, "Insert Media", "No service is open.")
            return
        current = self._list.currentItem()
        if current is None:
            QMessageBox.warning(self, "Insert Media", "No file selected.")
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        category = self._category_combo.currentText()
        scale_mode = media_library_repo.get_scale_mode(path) if category in ("Images", "Videos") else "fit"
        self._insert_item(category, path, scale_mode)
        self.accept()

    def _insert_item(self, category: str, path: str, scale_mode: str) -> None:
        title = Path(path).name

        if category == "Images":
            item = ImageItem(
                id=str(uuid.uuid4()),
                title=title,
                path=path,
                scale_mode=scale_mode,
                slides=[Slide(id=str(uuid.uuid4()), content=title)],
            )
        elif category == "Videos":
            item = VideoItem(
                id=str(uuid.uuid4()),
                title=title,
                path=path,
                auto_play=True,
                scale_mode=scale_mode,
                slides=[Slide(id=str(uuid.uuid4()), content=title)],
            )
        else:
            item = AudioItem(
                id=str(uuid.uuid4()),
                title=title,
                path=path,
                auto_play=True,
                slides=[Slide(id=str(uuid.uuid4()), content=title)],
            )

        self._service_store.add_item(item)

        self.accept()
