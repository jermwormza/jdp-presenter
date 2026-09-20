---
name: add-page-mode-agent
description: "Multi-step agent for adding a new top-level window/mode to the Python presenter app. Creates a window class, wiring in app/main.py, and any needed store. Python/PySide6 replacement for the old React-page agent."
---

# Add Window/Mode Agent

This agent guides you through adding a completely new window or mode to the presenter application (beyond Control, Output, and the phone Remote page).

## What You Provide

The agent will ask:
1. **Window name** (e.g., "Analytics", "Preview", "Settings")
2. **Purpose** — what does this window do?
3. **Data needs** — what stores does it need access to? (service_store, song_store, output_store, etc.)
4. **Window kind** — separate top-level `QMainWindow`, a `QDockWidget` inside Control, or a modal `QDialog`?

## Workflow

The agent will:

1. **Create window/dialog class** → Add `app/windows/{name}_window.py` (or `app/widgets/{name}_dialog.py` for a modal)
2. **Wire construction** → Instantiate it in `app/main.py`, passing the required store instances
3. **Create/update stores** → Add necessary store classes under `app/stores/` if needed (see `state-store.instructions.md`)
4. **Connect signals** → Subscribe to the stores it needs; emit any new signals other windows should react to
5. **Add a menu/toolbar entry** → In the Control window, add a `QAction` to open/show it
6. **Verify** → Run the app (`python -m app.main`), confirm it opens and updates live

## Architecture Pattern

Since there's no URL-param routing here, each "mode" is just a real Python object created once and shown/hidden as needed:

```python
# app/main.py
from app.windows.analytics_window import AnalyticsWindow

analytics_window = AnalyticsWindow(service_store, recording_store)

# In control_window.py, add a menu action:
action = QAction("Analytics", self)
action.triggered.connect(analytics_window.show)
toolbar.addAction(action)
```

```python
# app/windows/analytics_window.py
from PySide6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget

class AnalyticsWindow(QMainWindow):
    def __init__(self, service_store, recording_store, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Service Analytics")
        self._service_store = service_store
        self._recording_store = recording_store

        central = QWidget()
        layout = QVBoxLayout(central)
        self._items_label = QLabel()
        self._recordings_label = QLabel()
        layout.addWidget(self._items_label)
        layout.addWidget(self._recordings_label)
        self.setCentralWidget(central)

        service_store.service_changed.connect(self._refresh)
        recording_store.recordings_changed.connect(self._refresh)
        self._refresh(service_store.service)

    def _refresh(self, *_args) -> None:
        service = self._service_store.service
        self._items_label.setText(f"Items: {len(service.items) if service else 0}")
        self._recordings_label.setText(f"Recordings: {len(self._recording_store.recordings)}")
```

## Window/Mode Options

| Mode kind | When to use |
|-----------|-------------|
| Separate `QMainWindow` | Independent tool the user may want open alongside Control (Analytics, standalone Settings) |
| `QDockWidget` inside Control | Panel that should live inside the main editing UI (a sidebar) |
| Modal `QDialog` | One-off configuration flow (Export options, Theme editor) |

## Example Modes

**Preview Mode** — a dock widget inside Control showing a scaled-down live copy of the Output window, synced via `output_store` signals.

**Analytics Window** — separate `QMainWindow`, reads `service_store` and `recording_store`, no write actions.

**Settings Window** — modal `QDialog`, reads/writes `settings_store`, has its own "Save"/"Cancel" buttons.

## How to Invoke

```
/add-page-mode: Create a "Preview" dock widget showing the output live
/add-page-mode: Add an "Analytics" window with service duration and item stats
/add-page-mode: Create a "Slides" window for reordering presentation slides
```

The agent handles window creation, store wiring, and menu/toolbar integration.
