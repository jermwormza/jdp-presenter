"""Download-and-install flow for a newer GitHub release."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QProgressDialog, QWidget

from app.utils.update_checker import ReleaseAsset, UpdateDownloader


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


class UpdateDownloadDialog(QProgressDialog):
    """Modal progress dialog that streams a release asset to disk.

    Emits ``download_finished`` with the saved path, or ``download_failed`` with a
    message. Cancelling aborts the transfer and emits nothing.
    """

    download_finished = Signal(object)  # Path
    download_failed = Signal(str)

    def __init__(self, asset: ReleaseAsset, version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UpdateDownloadDialog")
        self.setWindowTitle(f"Downloading JDP Presenter {version}")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumDuration(0)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setRange(0, 0)
        self.setMinimumWidth(420)
        self._asset = asset
        self._downloader = UpdateDownloader(self)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished.connect(self._on_finished)
        self._downloader.failed.connect(self._on_failed)
        self.canceled.connect(self._downloader.cancel)
        self.setLabelText(f"Connecting to GitHub to download {asset.name}…")

    def start(self) -> None:
        self._downloader.download(self._asset)
        self.show()

    def _on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.setRange(0, total)
            self.setValue(received)
            self.setLabelText(
                f"Downloading {self._asset.name}\n"
                f"{_format_size(received)} of {_format_size(total)}"
            )
        else:
            self.setLabelText(f"Downloading {self._asset.name}\n{_format_size(received)}")

    def _on_finished(self, path: Path) -> None:
        self.hide()
        self.download_finished.emit(path)
        self.deleteLater()

    def _on_failed(self, message: str) -> None:
        self.hide()
        self.download_failed.emit(message)
        self.deleteLater()


def install_instructions(path: Path, platform: str = sys.platform) -> str:
    """Human-readable description of what happens after the download completes."""
    if platform == "win32" and path.suffix.casefold() == ".exe":
        return (
            "The update has been downloaded. JDP Presenter will now close and the installer "
            "will upgrade it in place, then relaunch the app.\n\n"
            "Windows may ask for permission to continue."
        )
    if platform == "darwin":
        return (
            f"The update has been downloaded to:\n{path}\n\n"
            "JDP Presenter will now quit and open the disk image. Drag the new JDP Presenter "
            "into your Applications folder to replace the current version, then relaunch it."
        )
    return (
        f"The update has been downloaded to:\n{path}\n\n"
        "JDP Presenter will now quit and open that folder. Extract the archive over your "
        "existing installation, then relaunch the app."
    )
