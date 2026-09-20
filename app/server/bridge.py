"""Thread-safe bridge: carries commands from the Flask-SocketIO thread onto the Qt main thread."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class RemoteBridge(QObject):
    command_received = Signal(str)


remote_bridge = RemoteBridge()
