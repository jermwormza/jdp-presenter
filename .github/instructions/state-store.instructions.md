---
name: state-store-guidelines
description: "Use when: creating or modifying store classes in app/stores/. Covers Qt Signal-based state, typed patterns, and multi-domain organization. Python/PySide6 replacement for the old Zustand-store guidelines."
applyTo: "app/stores/**/*.py"
---

# State Store Guidelines (Qt Signals, replacing Zustand)

## Store File Organization

Each **domain** gets its own store module:
```
app/stores/
  service_store.py      # Services, items, ordering
  song_store.py         # Songs, lyrics, metadata
  bible_store.py        # Bible selections, passages
  output_store.py        # Display settings, theming
  recording_store.py    # Recording state, exports
  settings_store.py     # App preferences
  theme_store.py         # Color schemes, fonts
  ui_store.py             # Modal/panel state
  display_store.py       # Display detection, fullscreen
```

**Never** mix concerns in a single store. Compute derived state in a method or a plain function in `app/utils/`, not by stuffing more fields into an unrelated store.

## Store Pattern

### Definition
```python
# app/stores/service_store.py
from PySide6.QtCore import QObject, Signal
from app.models.service import Service, ServiceItem

class ServiceStore(QObject):
    service_changed = Signal(object)       # Service | None
    selected_item_changed = Signal(object) # str | None

    def __init__(self) -> None:
        super().__init__()
        self._service: Service | None = None
        self._selected_item_id: str | None = None

    @property
    def service(self) -> Service | None:
        return self._service

    def set_service(self, service: Service | None) -> None:
        self._service = service
        self._selected_item_id = None
        self.service_changed.emit(service)
        self.selected_item_changed.emit(None)

    def select_item(self, item_id: str) -> None:
        self._selected_item_id = item_id
        self.selected_item_changed.emit(item_id)

    def add_item(self, item: ServiceItem) -> None:
        if self._service is None:
            return
        self._service.items.append(item)
        self.service_changed.emit(self._service)

    def update_item(self, item_id: str, **updates: object) -> None:
        if self._service is None:
            return
        for item in self._service.items:
            if item.id == item_id:
                for key, value in updates.items():
                    setattr(item, key, value)
                break
        self.service_changed.emit(self._service)

    def remove_item(self, item_id: str) -> None:
        if self._service is None:
            return
        self._service.items = [i for i in self._service.items if i.id != item_id]
        self.service_changed.emit(self._service)

    def move_item(self, item_id: str, direction: str) -> None:
        if self._service is None:
            return
        items = self._service.items
        index = next((i for i, it in enumerate(items) if it.id == item_id), -1)
        if index == -1:
            return
        if direction == "up" and index == 0:
            return
        if direction == "down" and index == len(items) - 1:
            return
        new_index = index - 1 if direction == "up" else index + 1
        items[index], items[new_index] = items[new_index], items[index]
        self.service_changed.emit(self._service)
```

## State Update Rules

### ✅ Correct: mutate the store's own private field, then emit
```python
def add_item(self, item: ServiceItem) -> None:
    if self._service is None:
        return
    self._service.items.append(item)
    self.service_changed.emit(self._service)
```

### ❌ Avoid: widgets reaching into store internals directly
```python
# DON'T: a widget mutating store state itself and hoping a signal fires
store._service.items.append(item)   # no signal emitted, other widgets go stale
```

### ❌ Avoid: silently swallowing "no current service" cases with default construction
```python
# DON'T: fabricate a Service just to avoid a None check
def add_item(self, item):
    self._service = self._service or Service(...)  # hides real bugs
```

## Using Stores in Widgets

### Basic Subscription
```python
class ServicePanel(QWidget):
    def __init__(self, service_store: ServiceStore, parent=None):
        super().__init__(parent)
        self._store = service_store
        service_store.service_changed.connect(self._render)
        self._render(service_store.service)

    def _render(self, service: Service | None) -> None:
        # rebuild list widgets from `service.items`
        ...
```

### Cross-Thread Emission (remote control → store)
Signals emitted from a non-Qt thread (e.g. the Flask-SocketIO background thread) must use a **queued connection** so the slot runs on the Qt main thread:
```python
from PySide6.QtCore import Qt

remote_bridge.command_received.connect(
    service_store.handle_remote_command, Qt.ConnectionType.QueuedConnection
)
```
Never call a store method directly from a Flask/SocketIO handler thread without going through a queued signal — Qt widgets are not thread-safe.

## Store Construction & Sharing

Create every store **once** in `app/main.py` and pass the same instance to both the Control window and the Output window (and the remote server bridge). Do not construct a second `ServiceStore` for the Output window — that was the Electron version's IPC problem; in one process, sharing an object reference is enough.
