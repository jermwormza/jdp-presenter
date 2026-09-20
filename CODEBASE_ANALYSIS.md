# JDP Presenter (Python Edition) — Codebase Analysis

**Generated:** 2026-08-21 (adapted from `../NodeVersion/CODEBASE_ANALYSIS.md`)

This document describes the **target** feature set for the Python rewrite (PySide6), tracked against what NodeVersion had implemented. Since this is a fresh start, most items below are TODO — see `TODO.md` for the build order. Sections marked "carried over" describe intended parity; sections marked "changed" describe deliberate architecture differences.

---

## 1. TARGET FEATURES (parity with NodeVersion)

### Core Presentation Engine
- 🔲 **Multi-window support** — Control window (main UI) + Output window (projection display), both native `QMainWindow`s in one process (no Electron BrowserWindow/IPC)
- 🔲 **Service management** — Create, edit, save, load, delete services with order-of-service items (JSON files, same as NodeVersion)
- 🔲 **Live/Preview mode** — Toggle between preview (control window) and live (output window)
- 🔲 **Slide navigation** — Next/Previous with keyboard shortcuts (`QShortcut` for Arrow keys, Page Up/Down, Space)
- 🔲 **Black screen** — Toggle black screen during presentation
- 🔲 **Multi-display support** — `QGuiApplication.screens()` to detect displays; move Output window between them
- 🔲 **Drag-and-drop reordering** — Native Qt drag-and-drop on `QListWidget`/`QAbstractItemModel` (replaces `@dnd-kit`)

### Content Item Types
- 🔲 **Scripture** — Bible verses with configurable line breaks, reference positioning, version display
- 🔲 **Song/Hymn** — Songs with lyrics, verse order, configurable display
- 🔲 **Image** — JPG/PNG/GIF/WebP with fit options (contain/cover/fill) via `QPixmap` scaling
- 🔲 **Video** — MP4/WebM/OGG/MOV with autoplay/loop via `PySide6.QtMultimedia`
- 🔲 **PDF** — Multi-page slide support via `PySide6.QtPdf`
- 🔲 **Text** — Custom text slides
- 🔲 **PPTX** — Deferred, same as NodeVersion (consider `python-pptx` + image rendering as a stopgap)

### Theme/Display System
- 🔲 **Global theme editor** — Background (color/image/video), scripture text styles, song text styles
- 🔲 **Item-level theme overrides** — Per-item `DisplaySettings` (deep partial theme merge, same semantics as NodeVersion)
- 🔲 **Theme persistence** — Save/load themes as JSON
- 🔲 **Theme gallery** — Pre-built themes (port the 9 NodeVersion themes as Python dict/dataclass literals)
- 🔲 **Background media** — Color, image (opacity), or video (auto-loop)
- 🔲 **Text styling** — Font family, size, weight, style, color, alignment per text type
- 🔲 **Scripture-specific settings** — Verse line breaks toggle, reference/version positioning

### Bible Management
- 🔲 **Bible import** — Parse Zefania XML (reuse `import/CSB_Complete.xml` as a test fixture); `xml.etree.ElementTree` replaces `xml2js`
- 🔲 **Bible library** — Store multiple translations locally (JSON, already copied into `data/bibles/`)
- 🔲 **Active Bible selection** — Switch between loaded translations
- 🔲 **Scripture lookup** — Browse books → chapters → verses
- 🔲 **Verse search** — Full-text search across all verses
- 🔲 **Quick reference entry** — "John 3:16-21" → auto-select verses
- 🔲 **Verse range selection**
- 🔲 **Slide generation** — Auto-generate slides from verses with configurable breaks

### Song Management
- 🔲 **Song library** — CRUD with metadata (title, author, copyright, CCLI, key)
- 🔲 **Lyrics editing** — Verse/chorus/bridge labels
- 🔲 **Verse order** — Playback sequence string (e.g. "v1 c v2 c v3 c c")
- 🔲 **Smart paste** — Parse pasted lyrics with section headers
- 🔲 **Song search**
- 🔲 **Quelea parser** — Port `quelaParser.ts` logic to Python (HSQLDB SQL text format)
- 🔲 **OpenLyrics parser** — XML parsing via `xml.etree.ElementTree`
- 🔲 **Song persistence** — JSON files under `data/songs/` (no IndexedDB/Dexie needed — single process, no browser)

### Audio Recording & Transcription
- 🔲 **Audio recorder** — `PySide6.QtMultimedia` `QAudioSource`/`QMediaRecorder`, pause/resume, duration timer, VU meter
- 🔲 **VU meter visualization** — Real-time levels from `QAudioProbe`/buffer analysis
- 🔲 **Local save** — Direct filesystem write (no IPC round-trip needed)
- 🔲 **Whisper integration** — OpenAI API or local `faster-whisper` (decide per TODO #9)
- 🔲 **Transcription progress / transcript display**
- 🔲 **Recording export** — Optional Dropbox upload

### Remote Control (changed — see architecture notes)
- 🔲 **Flask-SocketIO server** — Replaces `server/index.ts` (Express + Socket.io)
- 🔲 **Remote page** — One minimal HTML page (only HTML in the whole project) for mobile Next/Prev/Live/Black
- 🔲 **QR code pairing** — Python `qrcode` package generates the pairing image, shown in a `QLabel`
- 🔲 **State sync** — Store changes pushed to phones over Socket.IO
- 🔲 **Command relay** — Thread-safe queue from Flask thread into Qt main thread

### Cloud & Export
- 🔲 **Dropbox integration** — `dropbox` Python SDK, OAuth2 via local callback server (deferred)
- 🔲 **Service export** — Markdown/outline text, same two modes as NodeVersion
- 🔲 **Copy to clipboard** — `QGuiApplication.clipboard()`
- 🔲 **Download** — Native `QFileDialog` save

### Settings & Persistence
- 🔲 **Settings store** — `settings.json` (same file NodeVersion used) instead of `localStorage`
- 🔲 **JSON files** — Services, songs, recordings metadata (SQLite via `sqlite3` only if JSON search becomes too slow)
- 🔲 **Dropbox auth tokens / OpenAI API key** — Stored in `settings.json` (consider OS keychain via `keyring` package for secrets, an upgrade over NodeVersion's plain-text storage)

---

## 2. DATA MODELS (Python dataclasses, JSON-compatible with NodeVersion files)

### Service (`app/models/service.py`)
```python
@dataclass
class Service:
    id: str
    version: str
    name: str
    date: str
    theme: "ServiceTheme"
    items: list["ServiceItem"]
    leader_notes: LeaderNotes | None = None
    created_at: str = ""
    updated_at: str = ""
```

### Service Items (tagged union via `type` discriminator field, same as NodeVersion)
```python
ServiceItemType = Literal["scripture", "song", "image", "video", "pdf", "pptx", "text"]

@dataclass
class BaseServiceItem:
    id: str
    type: ServiceItemType
    title: str
    display_settings: DisplaySettings | None
    slides: list[Slide]

# ScriptureItem(type='scripture', bible, reference, verses)
# SongItem(type='song', song_id, selected_verses, linked_video)
# ImageItem(type='image', path, fit)
# VideoItem(type='video', path, auto_play, loop)
# PdfItem(type='pdf', path, page_count)
# PptxItem(type='pptx', path, slide_count)  # no rendering yet
# TextItem(type='text', content)
```

### Theme (`app/models/theme.py`) — field-for-field port of `ServiceTheme`
```python
@dataclass
class ServiceTheme:
    background: BackgroundTheme      # type: color|image|video, color, image_path?, video_path?, opacity
    scripture: ScriptureTheme        # verse_text, reference, version, verse_line_breaks
    song: SongTheme                  # lyrics, metadata
```

Field names use `snake_case` in Python but (de)serialize to/from the exact `camelCase` JSON keys NodeVersion used, so existing `data/services/*.json` files load unmodified. Use a small `to_json_dict()`/`from_json_dict()` pair per dataclass rather than a generic auto-mapper, to keep the camelCase mapping explicit and reviewable.

### Bible (`app/models/bible.py`)
```python
@dataclass
class BibleTranslation:
    id: str
    name: str
    abbreviation: str
    language: str
    books: list["BibleBook"]

@dataclass
class BibleBook:
    number: int
    name: str
    chapters: list["BibleChapter"]

@dataclass
class BibleChapter:
    number: int
    verses: list["BibleVerse"]

@dataclass
class BibleVerse:
    number: int
    text: str
```

### Song (`app/models/song.py`)
```python
@dataclass
class Song:
    id: str
    title: str
    author: str | None
    copyright: str | None
    ccli: str | None
    key: str | None
    tempo: int | None
    verses: list["Verse"]
    verse_order: list[str] | None
    created_at: str
    updated_at: str

@dataclass
class Verse:
    label: str  # 'v1', 'c', 'b', etc.
    text: str
```

### Persistence Strategy

| Data Type | Storage | Notes |
|-----------|---------|-------|
| Services | JSON files, `data/services/{id}.json` | Same format as NodeVersion — verified via the sample file already copied over |
| Songs | JSON files, `data/songs/{id}.json` | Same, one sample file copied over |
| Bibles | JSON files, `data/bibles/{id}.json` + `index.json` | Copied verbatim (already parsed from Zefania XML) |
| Recordings | Audio files, `data/recordings/` + metadata in `data/app.db` (SQLite) | Replaces IndexedDB — a real desktop app can just use SQLite |
| Settings | `data/settings.json` | Same file/format |
| Theme | Embedded in `Service` JSON | Same as NodeVersion |

---

## 3. UI (Native Qt Windows, replacing React Pages)

### Control Window (`app/windows/control_window.py`)
**Main editing interface** — direct port of `ControlPanel.tsx`'s responsibilities into Qt layouts:
- Toolbar (`QToolBar`): New, Open, Save, Dropbox, Export, Add Scripture/Song/Image/Video/Text/PDF, Settings, Theme, Recorder
- Left dock widget (`QDockWidget`, resizable): Order-of-service list with drag-and-drop reordering
- Center: Preview panel widget showing current slide with theme applied
- Right dock widget: Output controls (display picker, Go Live, Black), Theme editor / Bible browser / Song browser / Export / Settings as stacked panels or modal `QDialog`s

### Output Window (`app/windows/output_window.py`)
- Frameless or normal `QMainWindow`, `showFullScreen()` on the chosen `QScreen`
- Renders current slide via a custom `QWidget.paintEvent` or composed `QLabel`s, matching NodeVersion's 1920×1080 scaling behavior (scale-to-fit inside the target screen's resolution)
- Listens directly to `OutputStore` signals — no message-passing needed since it's in-process
- Black by default until "Go Live"

### Remote Page (`app/server/templates/remote.html`)
- Deliberately the **only** HTML/JS in the project — phones need a browser
- Connection indicator, current slide info, big Prev/Next buttons, Live/Black toggles
- Talks to `remote_server.py` over Socket.IO

### Supporting Widgets (`app/widgets/`)
| Widget | Purpose |
|--------|---------|
| `ServiceList` | Drag-and-drop ordered list of service items |
| `PreviewPanel` | Live preview of current slide with slide thumbnails |
| `BibleBrowser` | Bible selection, book/chapter/verse navigation, quick ref entry |
| `SongBrowser` / `SongEditor` | Song library browser, smart paste, verse management |
| `ThemeEditor` / `ThemeGallery` | Edit global/item theme, browse prebuilt themes |
| `PdfViewer` | `PySide6.QtPdf` page display |
| `AudioRecorder` / `TranscriptView` | Record + show transcription |
| `ExportDialog` | Export service as markdown/outline text |
| `SettingsDialog` | API keys, Dropbox auth, remote server port |
| `ConfirmDialog` | Generic confirmation (`QMessageBox` wrapper) |
| `ServicePicker` | Load existing services |

---

## 4. INTEGRATION POINTS (changed from Electron IPC to in-process calls + one web server)

### In-Process Signals (replaces IPC handlers entirely for Control ↔ Output)
Because everything runs in one Python process, most of NodeVersion's IPC table collapses into direct method calls or signal connections:

| NodeVersion IPC Event | Python Equivalent |
|------------------------|--------------------|
| `get-displays` | `QGuiApplication.screens()` |
| `open-output-window` / `close-output-window` | `OutputWindow().show()` / `.close()` |
| `toggle-output-fullscreen` | `output_window.showFullScreen()` / `showNormal()` |
| `to-output` / `to-control` messaging | Direct signal connections between stores/windows |
| `save-recording` | `pathlib.Path.write_bytes()` in `app/persistence/` |
| `select-file` | `QFileDialog.getOpenFileName()` |
| `list-bibles` / `load-bible` / `save-bible` / `delete-bible` | `app/persistence/bible_repo.py` functions reading/writing `data/bibles/` |
| `list-media` / `save-media` / `delete-media` / `import-media` | `app/persistence/media_repo.py` |
| `list-songs` / `save-song` / `delete-song` | `app/persistence/song_repo.py` (JSON files, not IndexedDB) |
| `list-services` / `load-service` / `save-service` / `delete-service` | `app/persistence/service_repo.py` |
| `get-setting` / `set-setting` | `app/persistence/settings_repo.py` reading/writing `data/settings.json` |

### Socket.IO Events (`app/server/remote_server.py`) — kept, since phones genuinely need a network protocol
| Event | Direction | Payload | Purpose |
|-------|-----------|---------|---------|
| `connect` | Server | — | Client connects |
| `command` | Remote → Server → Qt app | `{type: 'prev'|'next'|'toggle_live'|'toggle_black'}` | Remote sends control command |
| `state_update` | Qt app → Server → All | `{title, item_index, slide_index, total_slides, is_live, is_black}` | Broadcast current state |
| `disconnect` | Server | — | Client disconnects |

### External APIs & Services
- **Dropbox OAuth2** — `dropbox` SDK; local `http.server` callback listener instead of Electron deep-link handling (deferred)
- **OpenAI Whisper API** — same REST endpoint, called via `requests`/`httpx`; or swap to local `faster-whisper` to drop the network dependency (decide before implementing TODO #9)
- **Bible Data** — Zefania XML import via `xml.etree.ElementTree`, output the same JSON shape already present in `data/bibles/`

---

## 5. OUTSTANDING / DEFERRED WORK (carried over from NodeVersion)

- **PPTX Rendering** — still no renderer; `python-pptx` can read the file, rendering to images/slides is the hard part (same as NodeVersion's unresolved state)
- **Hymn/Video Linking** — `linked_video` field on `SongItem`, no UI wired yet
- **Theme Gallery Content** — need to port the 9 prebuilt NodeVersion themes into Python
- **Dropbox App Key** — still a placeholder; deferred per user request (matches NodeVersion status)

See `TODO.md` for the prioritized build order — this document only tracks *scope*, not sequencing.
