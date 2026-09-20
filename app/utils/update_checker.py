"""Asynchronous GitHub Releases update checker."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from app.version import APP_VERSION, GITHUB_LATEST_RELEASE_API


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    name: str
    url: str


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
    return ReleaseInfo(version=version.lstrip("vV"), name=name, url=url)


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
