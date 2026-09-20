---
name: add-remote-feature-agent
description: "Multi-step agent for adding new remote control features. Handles Flask-SocketIO events, store updates, the mobile remote.html page, and Output window sync. Python replacement for the old Socket.io/React remote agent."
---

# Add Remote Control Feature Agent

This agent guides you through implementing a new remote control feature that allows mobile users to control the presenter output.

## What You Provide

The agent will ask:
1. **Feature name** (e.g., "Next Slide", "Adjust Theme", "Start Recording")
2. **Data to sync** (e.g., display settings, service state, recording status)
3. **Mobile UI** — what buttons/controls appear on `remote.html`
4. **Effect on Output window** — what changes when the command arrives

## Workflow

The agent will:

1. **Add Socket.IO event** → Update `app/server/remote_server.py` to receive the event and emit an update
2. **Add a bridge signal** → Extend `app/server/bridge.py`'s `RemoteBridge` with a new `Signal`
3. **Connect into a store** → Wire the bridge signal to a store method with `Qt.ConnectionType.QueuedConnection` (see `remote-server.instructions.md`)
4. **Add remote.html UI** → Add the button/control and its Socket.IO `emit()` call
5. **Broadcast state back** → Update `broadcast_state()` so phones see the new state
6. **Test sync** → Verify mobile → Qt app → phones round-trip works

## Architecture Pattern

```python
# 1. Store holds the state
class DisplayStore(QObject):
    brightness_changed = Signal(int)

    def __init__(self):
        super().__init__()
        self._brightness = 100

    def set_brightness(self, value: int) -> None:
        self._brightness = value
        self.brightness_changed.emit(value)

# 2. Bridge signal carries the cross-thread event
class RemoteBridge(QObject):
    set_brightness_requested = Signal(int)

# 3. remote_server.py Socket.IO handler
@socketio.on("set_brightness")
def handle_set_brightness(data):
    remote_bridge.set_brightness_requested.emit(data["value"])

# 4. main.py wiring (queued connection crosses the thread boundary safely)
remote_bridge.set_brightness_requested.connect(
    display_store.set_brightness, Qt.ConnectionType.QueuedConnection
)

# 5. Output window reacts
display_store.brightness_changed.connect(output_window.apply_brightness)
```

```html
<!-- remote.html -->
<input type="range" min="0" max="100" oninput="socket.emit('set_brightness', {value: this.value})">
```

## Example Features

**Theme Control** — Mobile: color picker input; Output: background color changes live; sync via `theme_store`.

**Service Navigation** — Mobile: Next/Previous buttons; Output: advances current item/slide; sync via `output_store`.

**Recording Control** — Mobile: Start/Stop button; Output: recording indicator; sync via `recording_store`.

## How to Invoke

```
/add-remote-feature: Add brightness control to the remote page
/add-remote-feature: Add service navigation (next/previous item)
/add-remote-feature: Add a theme color picker on the remote page
```

The agent handles the Socket.IO event, the thread-safe bridge signal, and the `remote.html` control.
