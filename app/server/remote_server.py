"""Embedded remote-control server: Flask-SocketIO, run in a background thread alongside Qt.

Only networked, HTML-serving part of the app — phones need a browser. Commands received here
must never touch Qt widgets directly; they go through app.server.bridge.remote_bridge, connected
in app/main.py with Qt.ConnectionType.QueuedConnection to safely cross onto the Qt main thread.
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Any

from flask import Flask, render_template
from flask_socketio import SocketIO

from app.server.bridge import remote_bridge


def _template_dir() -> str:
    """Resolve the templates folder, which Flask cannot auto-detect when frozen."""
    if getattr(sys, "frozen", False):
        # _MEIPASS points at the bundle's resource folder (e.g. .../Contents/Resources)
        base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
        return os.path.join(base, "templates")
    return os.path.join(os.path.dirname(__file__), "templates")


app = Flask(__name__, template_folder=_template_dir())
_socketio: SocketIO | None = None
_latest_state: dict[str, Any] = {}
_state_lock = threading.Lock()


def get_socketio() -> SocketIO:
    """Lazily create SocketIO instance to avoid frozen-app import issues with async modes."""
    global _socketio
    if _socketio is None:
        # Use threading async_mode which doesn't require external dependencies
        _socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")
    return _socketio


@app.route("/")
def remote_page() -> str:
    return render_template("remote.html")


@get_socketio().on("command")
def handle_command(data: dict[str, Any]) -> None:
    command_type = data.get("type")
    if command_type:
        remote_bridge.command_received.emit(command_type)


@get_socketio().on("connect")
def handle_connect() -> None:
    with _state_lock:
        state = dict(_latest_state)
    if state:
        get_socketio().emit("state_update", state)


def broadcast_state(state: dict[str, Any]) -> None:
    with _state_lock:
        _latest_state.clear()
        _latest_state.update(state)
    get_socketio().emit("state_update", state)


def start_server(port: int = 5183) -> threading.Thread:
    socketio = get_socketio()
    thread = threading.Thread(
        target=lambda: socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True),
        daemon=True,
    )
    thread.start()
    return thread
