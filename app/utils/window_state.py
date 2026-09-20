"""Persist and restore Qt geometry/layout state as base64 settings strings."""
from __future__ import annotations

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QSplitter, QWidget


def encode_geometry(window: QWidget) -> str:
    return bytes(window.saveGeometry().toBase64()).decode("ascii")


def restore_geometry(window: QWidget, encoded: str | None) -> None:
    if not encoded:
        return
    window.restoreGeometry(QByteArray.fromBase64(encoded.encode("ascii")))


def encode_splitter_state(splitter: QSplitter) -> str:
    return bytes(splitter.saveState().toBase64()).decode("ascii")


def restore_splitter_state(splitter: QSplitter, encoded: str | None) -> None:
    if not encoded:
        return
    splitter.restoreState(QByteArray.fromBase64(encoded.encode("ascii")))
