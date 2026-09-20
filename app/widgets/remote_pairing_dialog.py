"""Shows a QR code phones can scan to open the remote-control page."""
from __future__ import annotations

import io

import qrcode
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from app.utils.network_utils import get_local_ip

REMOTE_PORT = 5183


def remote_control_url() -> str:
    return f"http://{get_local_ip()}:{REMOTE_PORT}/"


def make_qr_pixmap(url: str) -> QPixmap:
    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue())
    return pixmap


class RemotePairingDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pair Remote Control")

        url = remote_control_url()
        qr_label = QLabel()
        qr_label.setPixmap(make_qr_pixmap(url))
        url_label = QLabel(url)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Scan with a phone to open the remote control:"))
        layout.addWidget(qr_label)
        layout.addWidget(url_label)
