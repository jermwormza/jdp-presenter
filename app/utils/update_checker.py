"""Asynchronous GitHub Releases update checker, asset downloader, and installer launcher."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from app.version import APP_VERSION, GITHUB_LATEST_RELEASE_API

# Passed to the Inno Setup installer so its [Run] section relaunches the app after a
# silent in-place upgrade (see installer/JDP Presenter.iss).
WINDOWS_INSTALLER_ARGS = (
    "/SILENT",
    "/CLOSEAPPLICATIONS",
    "/NORESTART",
    "/AUTOUPDATE=1",
)
# Preferred asset suffixes per platform, most desirable first.
_ASSET_PREFERENCES: dict[str, tuple[str, ...]] = {
    "win32": ("-setup.exe", ".exe", ".zip"),
    "darwin": (".dmg", ".pkg", ".zip"),
    "linux": (".appimage", ".tar.gz", ".tgz", ".zip"),
}
_DOWNLOAD_DIR_NAME = "jdp-presenter-updates"


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    size: int = 0

    @property
    def is_installer(self) -> bool:
        """True when the asset can be run to upgrade in place (Windows Inno Setup installer)."""
        return self.name.casefold().endswith(".exe")


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    name: str
    url: str
    assets: tuple[ReleaseAsset, ...] = ()


def version_parts(version: str) -> tuple[int, ...]:
    match = re.search(r"\d+(?:\.\d+)*", version)
    if match is None:
        return ()
    return tuple(int(part) for part in match.group(0).split("."))


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    candidate_parts = version_parts(candidate)
    current_parts = version_parts(current)
    width = max(len(candidate_parts), len(current_parts))
    return candidate_parts + (0,) * (width - len(candidate_parts)) > current_parts + (
        0,
    ) * (width - len(current_parts))


def release_from_payload(payload: object) -> ReleaseInfo:
    if not isinstance(payload, dict):
        raise ValueError("GitHub returned an invalid release response")
    version = payload.get("tag_name")
    url = payload.get("html_url")
    name = payload.get("name") or version
    if not isinstance(version, str) or not isinstance(url, str) or not isinstance(name, str):
        raise ValueError("GitHub release response is missing required fields")
    assets: list[ReleaseAsset] = []
    for entry in payload.get("assets") or ():
        if not isinstance(entry, dict):
            continue
        asset_name = entry.get("name")
        asset_url = entry.get("browser_download_url")
        if isinstance(asset_name, str) and isinstance(asset_url, str):
            size = entry.get("size")
            assets.append(
                ReleaseAsset(asset_name, asset_url, size if isinstance(size, int) else 0)
            )
    return ReleaseInfo(
        version=version.lstrip("vV"), name=name, url=url, assets=tuple(assets)
    )


def select_asset(release: ReleaseInfo, platform: str = sys.platform) -> ReleaseAsset | None:
    """Pick the most useful downloadable asset for this platform, or None if there is none."""
    preferences = _ASSET_PREFERENCES.get(platform)
    if preferences is None:
        return None
    for suffix in preferences:
        for asset in release.assets:
            if asset.name.casefold().endswith(suffix):
                return asset
    return None


def download_destination(asset: ReleaseAsset) -> Path:
    directory = Path(tempfile.gettempdir()) / _DOWNLOAD_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory / Path(asset.name).name


def installer_command(path: Path) -> list[str]:
    """Command line for an unattended in-place upgrade using the downloaded installer."""
    return [str(path), *WINDOWS_INSTALLER_ARGS]


def launch_update(path: Path, platform: str = sys.platform) -> None:
    """Hand the downloaded asset to the OS: run the installer on Windows, otherwise open it.

    On Windows the installer needs elevation, so it is started through ShellExecute
    (os.startfile) which shows the UAC prompt instead of failing with
    ERROR_ELEVATION_REQUIRED the way CreateProcess would.
    """
    if platform == "win32":
        if path.suffix.casefold() == ".exe":
            executable, *arguments = installer_command(path)
            os.startfile(  # type: ignore[attr-defined]  # Windows-only API
                executable, "open", subprocess.list2cmdline(arguments)
            )
        else:
            os.startfile(str(path))  # type: ignore[attr-defined]
    elif platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


class UpdateDownloader(QObject):
    """Streams a release asset to the temp folder, reporting progress as it goes."""

    progress = Signal(int, int)  # bytes received, bytes total (-1 if unknown)
    finished = Signal(object)  # Path
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self._destination: Path | None = None
        self._handle: BinaryIO | None = None

    @property
    def is_downloading(self) -> bool:
        return self._reply is not None

    def download(self, asset: ReleaseAsset) -> None:
        if self._reply is not None:
            return
        self._destination = download_destination(asset)
        partial = self._destination.with_suffix(self._destination.suffix + ".part")
        try:
            self._handle = partial.open("wb")
        except OSError as exc:
            self.failed.emit(f"Could not write to {partial.parent}: {exc}")
            return
        request = QNetworkRequest(QUrl(asset.url))
        request.setRawHeader(b"Accept", b"application/octet-stream")
        request.setRawHeader(b"User-Agent", b"JDP-Presenter-Update-Checker")
        self._reply = self._manager.get(request)
        self._reply.downloadProgress.connect(self._on_progress)
        self._reply.readyRead.connect(self._on_ready_read)
        self._reply.finished.connect(self._on_finished)

    def cancel(self) -> None:
        if self._reply is not None:
            self._reply.abort()

    def _on_progress(self, received: int, total: int) -> None:
        self.progress.emit(received, total)

    def _on_ready_read(self) -> None:
        if self._reply is not None and self._handle is not None:
            self._handle.write(bytes(self._reply.readAll()))

    def _on_finished(self) -> None:
        reply = self._reply
        handle = self._handle
        destination = self._destination
        self._reply = None
        self._handle = None
        self._destination = None
        if reply is None or handle is None or destination is None:
            return
        partial = Path(handle.name)
        try:
            handle.write(bytes(reply.readAll()))
            handle.close()
            if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
                partial.unlink(missing_ok=True)
                return
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise ValueError(reply.errorString())
            status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if isinstance(status_code, int) and status_code >= 400:
                raise ValueError(f"GitHub returned HTTP {status_code} for the download")
            partial.replace(destination)
            self.finished.emit(destination)
        except (OSError, ValueError) as exc:
            partial.unlink(missing_ok=True)
            self.failed.emit(str(exc))
        finally:
            reply.deleteLater()


class UpdateChecker(QObject):
    update_available = Signal(object)  # ReleaseInfo
    up_to_date = Signal(str)
    failed = Signal(str)
    checking_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None

    def check(self) -> None:
        if self._reply is not None:
            return
        request = QNetworkRequest(QUrl(GITHUB_LATEST_RELEASE_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", b"JDP-Presenter-Update-Checker")
        self._reply = self._manager.get(request)
        self._reply.finished.connect(self._on_finished)
        self.checking_changed.emit(True)

    def _on_finished(self) -> None:
        reply = self._reply
        self._reply = None
        self.checking_changed.emit(False)
        if reply is None:
            return
        try:
            status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status_code == 404:
                raise ValueError(
                    "No public GitHub release was found. Publish a release and ensure the "
                    "repository is public."
                )
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise ValueError(reply.errorString())
            payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            release = release_from_payload(payload)
            if is_newer_version(release.version):
                self.update_available.emit(release)
            else:
                self.up_to_date.emit(release.version)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self.failed.emit(str(exc))
        finally:
            reply.deleteLater()
