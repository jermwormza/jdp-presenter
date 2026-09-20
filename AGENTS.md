---
name: jdp-presenter-agents
description: "Agent instructions for JDP Presenter (Python Edition): a PySide6 (Qt) dual-window presenter app with projection display and remote control. Rewritten from the NodeVersion (Electron/React) to avoid HTML/CSS/JS entirely."
---

# JDP Presenter (Python Edition): Agent Instructions

This is a multi-window **desktop** presenter application built with **Python 3.11+, PySide6 (Qt for Python)**. It controls projection displays and supports remote control from mobile devices via a small embedded web server (the only place HTML is still involved, since phones need a browser).

This is a from-scratch rewrite of `../NodeVersion` (Electron + Vite + React), created because the JS/CSS/Electron toolchain became unmanageable. Prefer native Qt widgets and Python data classes over any web technology.

## Quick Start

**Install & Develop:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

**Build (packaging, later milestone):**
```bash
pyinstaller --windowed --name "JDP Presenter" app/main.py
```

**Ports:** Embedded remote-control web server runs on **5183** (kept the same port as NodeVersion for muscle memory).

---

## Architecture: Two Native Windows + One Lightweight Web Endpoint

Unlike the Electron version's "one SPA rendered three ways", the Python version uses **real, separate objects** for each context — no URL-param mode switching needed.

### 1. Control Window (`app/windows/control_window.py`)
- Main `QMainWindow` — service editing, Bible/song browsing, theme editing, recording UI
- Built from `QWidget` panels in `app/widgets/`
- Talks to the Output window via in-process Qt signals (no IPC serialization needed — it's the same process)

### 2. Output Window (`app/windows/output_window.py`)
- A second `QMainWindow` (or frameless `QWidget`), moved to a projector/secondary display and shown fullscreen
- Pure renderer: listens to signals from the shared `OutputStore`, draws the current slide with the active theme
- No business logic lives here

### 3. Application State (`app/stores/`)
- Python replacement for the Zustand stores: plain classes holding state + emitting `Signal`s on change (see `state-store` instructions)
- One store per domain: `service_store.py`, `song_store.py`, `bible_store.py`, `output_store.py`, `settings_store.py`, `theme_store.py`, `ui_store.py`, `display_store.py`, `recording_store.py`
- Because Control and Output run **in the same process**, sharing state is just passing the same store instance around — no IndexedDB or preload bridge required

### 4. Embedded Remote-Control Server (`app/server/remote_server.py`)
- `Flask` + `Flask-SocketIO`, run in a background thread from within the Qt app
- Serves one minimal mobile page (`app/server/templates/remote.html`) — Next/Prev/Live/Black buttons only
- Relays commands into the Qt app via a thread-safe queue/signal, and pushes state updates back out to connected phones
- This is intentionally the *only* HTML in the project

---

## File Organization & Naming Conventions

### Widget Structure
```
app/widgets/widget_name.py   # QWidget subclass, snake_case module, PascalCase class
```
No CSS modules — styling is done with Qt Style Sheets (QSS) applied inline or from `app/resources/theme.qss`, kept minimal.

### Stores (`app/stores/`)
Each domain has a dedicated store class (see AGENTS/NodeVersion mapping below):
- `service_store.py` — Services, items, ordering
- `song_store.py` — Songs, lyrics, metadata
- `bible_store.py` — Bible selections, viewing state
- `output_store.py` — Output display settings, theming
- `recording_store.py` — Recording state, exports
- `settings_store.py` — App preferences
- `theme_store.py` — Color schemes, fonts
- `ui_store.py` — UI state (modals, panels)
- `display_store.py` — Display detection, fullscreen state

### Utilities (`app/utils/`)
Domain-grouped utility functions (ported 1:1 in spirit from NodeVersion):
- `bible_utils.py`, `exporters.py`, `scripture_utils.py`
- `dropbox_sync.py` — Cloud sync integration
- `ical_utils.py` — Imported calendar handling

### Models (`app/models/`)
Centralized domain dataclasses (replaces `src/types/`):
- `service.py` — `Service`, `ServiceItem` (scripture, song, pdf, pptx, recording)
- `song.py` — Song metadata
- `bible.py` — Bible versions, passages
- `theme.py` — `Theme`, display settings

### Naming Patterns
| Context | Pattern | Example |
|---------|---------|---------|
| Qt widget classes | PascalCase | `BibleBrowser`, `ServiceList` |
| Modules/files | snake_case | `bible_browser.py`, `service_list.py` |
| Qt Signals | snake_case, past-tense or `*_changed` | `service_changed`, `slide_advanced` |
| Store methods | snake_case | `set_service()`, `add_item()`, `move_item()` |
| Service item types | snake_case | `scripture`, `song`, `pdf`, `pptx`, `recording` |

---

## Python & Code Quality

- **Type hints required** on all public functions/methods; run `mypy app/` before considering work done
- **Dataclasses** (`@dataclass`) for all models; avoid bare dicts for domain data
- **Formatting**: `black` + `ruff` (config in `pyproject.toml`)
- Avoid `Any`; prefer `TypedDict`/`Protocol`/generics where dynamic shapes are unavoidable

---

## State Management with Signal-Based Stores

All shared application state flows through store objects that subclass `QObject` and expose `Signal`s. **Never use ad-hoc globals or pass mutable state through function args across widgets.**

Example pattern:
```python
# app/stores/service_store.py
from PySide6.QtCore import QObject, Signal
from app.models.service import Service, ServiceItem

class ServiceStore(QObject):
    service_changed = Signal(object)  # emits Service | None

    def __init__(self):
        super().__init__()
        self._service: Service | None = None

    @property
    def service(self) -> Service | None:
        return self._service

    def set_service(self, service: Service) -> None:
        self._service = service
        self.service_changed.emit(service)

    def add_item(self, item: ServiceItem) -> None:
        if self._service is None:
            return
        self._service.items.append(item)
        self.service_changed.emit(self._service)

# Usage in a widget
store.service_changed.connect(self._on_service_changed)
store.add_item(new_item)
```

Widgets subscribe via `store.signal.connect(handler)` in their constructor and disconnect on `closeEvent` if needed.

---

## Data Persistence

- **Songs / Bibles**: SQLite databases under the configured `songs/` and `bibles/` folders. Portable `.jdplibrary` archives contain OpenLyrics songs and Zefania Bibles.
- **Services**: JSON files on disk under `data/services/`
- **Recordings**: audio files under `data/recordings/`, metadata in a small SQLite DB (`data/app.db`) via `sqlite3` — replaces Dexie/IndexedDB
- **Settings**: `data/settings.json` (same file format as NodeVersion)
- **Auto-sync** to Dropbox available via `utils/dropbox_sync.py` (deferred; see TODO.md)

---

## Inter-Window & Remote Communication Patterns

### In-Process (Control ↔ Output)
Because both windows live in the same Python process, prefer **direct signal connections** over any message-passing abstraction:
```python
output_store.slide_changed.connect(output_window.render_slide)
```
No serialization, no IPC handlers, no preload bridge — this eliminates an entire class of bugs from the Electron version.

### Remote (Phone ↔ App)
1. `RemoteControl` mobile page (served by Flask-SocketIO) emits an event (`prev`, `next`, `toggle_live`, `toggle_black`)
2. `remote_server.py` receives it on a background thread and puts a command on a thread-safe `queue.Queue`
3. The Qt main thread polls the queue via a `QTimer` (or the command is delivered via `Signal` using `Qt.QueuedConnection` from a `QThread` worker) and applies it to the stores
4. Store changes are pushed back to connected phones over Socket.IO

**Never touch Qt widgets directly from the Flask/SocketIO thread** — always marshal through a queue or a Qt signal with a queued connection.

---

## Common Pitfalls & Gotchas

1. **Cross-thread Qt calls**: Flask-SocketIO runs in a background thread; never call widget methods directly from it
2. **Blocking the UI thread**: Long operations (Bible XML import, Whisper transcription) must run in a `QThread` or `QRunnable`, not the main thread
3. **No test runner yet**: Use `pytest`; add tests as modules are ported
4. **Type hints**: `mypy` should be run before considering a module "done"
5. **QSS scoping**: Qt Style Sheets cascade like CSS — use `objectName` selectors to scope styles to a widget instead of global rules
6. **Two windows, one store**: Don't create separate `ServiceStore` instances for Control and Output — share one instance created in `main.py`

---

## Build & Release Process (Target)

**Development:**
- `python -m app.main` — Launches both windows

**Production (future):**
- `pyinstaller` to produce a single-folder/single-file app bundle per OS
- Icons: reuse concepts from `public/icon.icns` etc. once assets are ported

---

## When Working on Features

### Adding a New Service Item Type
1. Add a new dataclass to `app/models/service.py` and register it in the `ServiceItem` union
2. Add rendering logic in `output_window.py` (or a dedicated renderer widget in `app/widgets/`)
3. Add an editor widget under `app/widgets/`
4. Update `utils/exporters.py` if the export/markdown format changes

### Modifying Display Handling
1. Update `display_store.py` with new state
2. Use `QGuiApplication.screens()` to enumerate displays (replaces Electron's `screen` API)
3. Move the Output window with `window.setGeometry(screen.geometry())` + `showFullScreen()`
4. Test with multiple displays (macOS: `System Settings > Displays`)

### Adding Remote Control Features
1. Add/extend a Socket.IO event in `app/server/remote_server.py`
2. Add the control to `app/server/templates/remote.html`
3. Bridge the event into the relevant store via the thread-safe queue
4. Update `display_store`/`output_store` as needed

### Changes to Persistence
1. Bump the SQLite `user_version` and add a migration in `app/persistence/` when a library schema changes.
2. Test legacy JSON migration and `.jdplibrary` OpenLyrics/Zefania round-trips before rebuilding the starter package.

---

## Resources & Documentation

- **PySide6**: [Official docs](https://doc.qt.io/qtforpython/)
- **Flask-SocketIO**: [Docs](https://flask-socketio.readthedocs.io/)
- **Qt Signals & Slots**: core to the store pattern used throughout this app
- **Original app for reference**: `../NodeVersion` (do not run it as part of this project; read-only reference for behavior/parity)
