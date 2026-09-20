---
name: remote-server-guidelines
description: "Use when: adding endpoints/events in app/server/remote_server.py, updating the mobile remote page, or bridging remote commands into the Qt app. Python/Flask-SocketIO replacement for the old Electron IPC guidelines."
applyTo: "app/server/**/*.py"
---

# Remote Server & Cross-Thread Bridge Guidelines

## Why This Still Exists

Control ↔ Output communication in this app is just **direct Qt signals in one process** — no IPC layer needed (see `state-store.instructions.md`). The one place a real client/server boundary remains is the **phone remote control**, since a phone is a separate device on the network. `app/server/remote_server.py` (Flask + Flask-SocketIO) is intentionally the only networked, HTML-serving part of the app.

## Required Architecture

```
Phone browser (remote.html)
         ↓  Socket.IO event
Flask-SocketIO handler (background thread, app/server/remote_server.py)
         ↓  thread-safe hand-off (Signal with QueuedConnection, or queue.Queue + QTimer)
Qt main thread — store method call
         ↓
Signal emitted → widgets update
         ↓
Server pushes state_update back to all connected phones
```

**Never** call a Qt widget or store method directly from a Flask/SocketIO handler without crossing back onto the Qt main thread first — PySide6 objects are not thread-safe across threads.

## Running the Server Alongside Qt

```python
# app/server/remote_server.py
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, async_mode="threading")

@app.route("/")
def remote_page():
    return render_template("remote.html")

@socketio.on("command")
def handle_command(data):
    # data: {"type": "prev" | "next" | "toggle_live" | "toggle_black"}
    from app.server.bridge import remote_bridge
    remote_bridge.command_received.emit(data["type"])

def start_server(port: int = 5183) -> threading.Thread:
    thread = threading.Thread(
        target=lambda: socketio.run(app, host="0.0.0.0", port=port),
        daemon=True,
    )
    thread.start()
    return thread
```

```python
# app/server/bridge.py
from PySide6.QtCore import QObject, Signal

class RemoteBridge(QObject):
    command_received = Signal(str)

remote_bridge = RemoteBridge()
```

```python
# app/main.py (wiring, illustrative)
from PySide6.QtCore import Qt
from app.server.bridge import remote_bridge

remote_bridge.command_received.connect(
    output_store.handle_remote_command, Qt.ConnectionType.QueuedConnection
)
```

## Event Naming

Use **snake_case** for all Socket.IO event names (mirrors NodeVersion's kebab-case convention, adapted to Python style):

```
command
state_update
connect
disconnect
```

## Safe Payload Types

### ✅ Allowed
- Primitives: `str`, `int`, `float`, `bool`, `None`
- Collections: `list`, `dict` of the above (JSON-serializable only)

### ❌ Never send
- Qt objects (`QWidget`, `QScreen`, etc.) — convert to plain dicts first, exactly like NodeVersion had to convert Electron `Display` objects

### Example: Safe State Broadcast
```python
def broadcast_state(service_store, output_store) -> None:
    service = service_store.service
    socketio.emit("state_update", {
        "title": output_store.current_item_title,
        "item_index": output_store.current_item_index,
        "slide_index": output_store.current_slide_index,
        "total_slides": output_store.total_slides,
        "is_live": output_store.is_live,
        "is_black": output_store.is_black,
    })
```

## Serving the Remote Page

Keep `app/server/templates/remote.html` intentionally minimal — connection indicator, current slide title, big Prev/Next buttons, Live/Black toggle. Do not grow this into a second UI; any richer control belongs in the native Control window instead.

## QR Code Pairing

Generate the pairing QR with the `qrcode` package and display it as a `QPixmap` inside the Control window (replaces `qrcode.react` + a modal):
```python
import qrcode
from PySide6.QtGui import QPixmap
import io

def make_qr_pixmap(url: str) -> QPixmap:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buf.getvalue())
    return pixmap
```
