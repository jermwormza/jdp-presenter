"""On-demand QR-code overlay (hidden by default) linking to the remote control page.

Shown/hidden via a menu/toolbar toggle rather than always visible; sized proportionally to the
widget it's displayed over so it stays comfortably scannable at any window/canvas size.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QLabel, QWidget

from app.widgets.remote_pairing_dialog import make_qr_pixmap, remote_control_url

_SIZE_FRACTION = 0.4  # of the smaller dimension of the parent widget
_MIN_SIZE = 120
_PADDING = 16


class QRCodeOverlay(QLabel):
    """A QR code centered over `parent`, sized to fit it; hidden until toggled on."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._source_pixmap = make_qr_pixmap(remote_control_url())
        self.setStyleSheet(f"background-color: white; padding: {_PADDING}px; border-radius: 8px;")
        self.setToolTip("Scan to open the remote control")
        self.hide()
        parent.installEventFilter(self)
        self._reposition()

    def set_visible(self, visible: bool) -> None:
        if visible:
            self._reposition()
        self.setVisible(visible)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self._reposition()
        return super().eventFilter(watched, event)

    def _reposition(self) -> None:
        parent = self.parent()
        qr_size = max(_MIN_SIZE, int(min(parent.width(), parent.height()) * _SIZE_FRACTION))
        self.setPixmap(
            self._source_pixmap.scaled(
                qr_size, qr_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        )
        self.setFixedSize(qr_size + _PADDING * 2, qr_size + _PADDING * 2)
        x = (parent.width() - self.width()) // 2
        y = (parent.height() - self.height()) // 2
        self.move(max(0, x), max(0, y))
        self.raise_()

