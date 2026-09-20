# JDP Presenter (Python Edition) - Development TODOs

This file tracks outstanding work for the PySide6 rewrite. It mirrors `../NodeVersion/TODO.md` but reframed as a build-up plan since this is a fresh implementation, not a working app yet.

Status legend: 🔲 TODO | 🔄 IN PROGRESS | ✅ COMPLETED | ⚠️ BLOCKED

---

## Recently Completed

- ✅ **Import Facility: Bibles & Song Libraries** (2026-08-21)
  - `app/utils/importers/zefania_bible.py` — Zefania XML Bible import (case-insensitive tag matching,
    ported from NodeVersion's bibleParser.ts), `bible_repo.save_bible()` writes the translation JSON
    and updates `data/bibles/index.json`
  - `app/utils/importers/quelea_songs.py` — Quelea `.script` (HSQLDB `SONGS` table INSERTs) import,
    ported from NodeVersion's queleaParser.ts, including `\u000a`-escaped embedded newlines and
    Verse/Chorus/Bridge/Pre-Chorus/Tag section labels + verse order
  - `app/utils/importers/openlyrics_songs.py` — OpenLyrics XML import (namespace-stripped so plain
    tag lookups work), ported from NodeVersion's openLyricsParser.ts
  - `app/utils/importers/opensong_songs.py` — NEW (not present in NodeVersion): OpenSong XML import,
    `[V1]`/`[C]`/`[B]` section markers, skips chord lines prefixed with `.`
  - `app/widgets/import_dialog.py` — single "Import" toolbar action covering all four formats
    (Zefania = single file, Quelea = single file, OpenLyrics = single file, OpenSong = whole folder
    of exported song files), wired into `control_window.py`
  - `tests/test_importers.py` (4 tests) + `tests/test_bible_repo.py` (2 tests, using
    `monkeypatch`/`tmp_path` so real `data/bibles/` is never touched by the test suite)
  - NOTE: a Quelea SQLite importer was briefly added then reverted the same day — the .sqlite files
    the user found on disk turned out to be from OpenBible, not Quelea. Quelea's format is `.script`
    (HSQLDB) only for this app's purposes. See "Correction" note in session memory for full context.

- ✅ **Core Models** (2026-08-21)
  - Typed `ServiceItem` union in `app/models/service.py` (scripture/song/image/video/pdf/pptx/text),
    `DisplaySettings`, `Slide`, `ScriptureVerse` — camelCase JSON round-trip verified
  - `app/models/bible.py` and `app/models/song.py` dataclasses
  - `app/persistence/{service,song,bible,settings}_repo.py` (JSON file I/O, no Qt dependency)
  - `app/utils/theme_utils.py::merge_theme`
  - `tests/test_models_roundtrip.py` — Service/Song/Bible JSON round-trip passes against copied sample data

- ✅ **Project scaffold created** (2026-08-21)
  - `app/` package structure (models, stores, windows, widgets, server, persistence, utils)
  - Instruction files ported and reworked for Python/PySide6
  - Data files copied from `NodeVersion/data/` (bibles, songs, one sample service, settings.json)

---

## High Priority (MVP — get a working app first)

### 1. ✅ Core Models
**Description**: Port TypeScript types to Python dataclasses
**Files**: `app/models/service.py`, `app/models/song.py`, `app/models/bible.py`, `app/models/theme.py`
**Acceptance criteria**:
- [x] `Service`, `ServiceItem` (scripture/song/image/video/pdf/pptx/text) dataclasses with `to_dict`/`from_dict`
- [x] `Theme`/`DisplaySettings` dataclasses matching NodeVersion's `ServiceTheme` shape (for JSON compatibility)
- [x] Round-trips existing sample JSON in `data/services/` and `data/songs/` without data loss

### 2. ✅ Control Window Skeleton
**Description**: Minimal `QMainWindow` with service list, add-item buttons, preview panel
**Files**: `app/windows/control_window.py`, `app/widgets/service_list.py`, `app/widgets/preview_panel.py`
**Acceptance criteria**:
- [x] Can create/open/save a service to `data/services/*.json`
- [x] Can add a text item and a scripture item — text item via toolbar; scripture insertion deferred to Bible Browser (#4)
- [x] Drag-to-reorder service items (Qt's built-in `QListWidget` internal move, or `QAbstractItemModel` with drag/drop)

### 3. ✅ Output Window Skeleton
**Description**: Second window, movable to a chosen display, fullscreen projection
**Files**: `app/windows/output_window.py`, `app/stores/display_store.py`
**Acceptance criteria**:
- [x] Lists available screens via `QGuiApplication.screens()`
- [x] Moves/fullscreens the Output window onto a chosen screen
- [x] Renders current slide's theme (background color, text) via `QPainter` or styled `QLabel`s
- [x] Black-screen toggle

### 4. ✅ Bible Browser & Scripture Rendering
**Description**: Load bibles from `data/bibles/*.json` (already in NodeVersion's parsed JSON format), browse book/chapter/verse, insert as service item
**Files**: `app/stores/bible_store.py`, `app/widgets/bible_browser.py`, `app/utils/bible_utils.py`
**Acceptance criteria**:
- [x] Loads `data/bibles/index.json` to list translations
- [ ] Book → chapter → verse navigation — deferred; only quick-reference entry implemented so far
- [x] Quick reference entry (e.g. "John 3:16-21") parsed into verse selection
- [x] Selected verses become a `ScriptureItem` on the service

### 5. ✅ Song Library
**Description**: Song list/editor backed by JSON files under `data/songs/`
**Files**: `app/stores/song_store.py`, `app/widgets/song_browser.py`, `app/widgets/song_editor.py`
**Acceptance criteria**:
- [x] List/search existing songs (one sample song already copied over)
- [x] Create/edit verses with labels (v1, c, b, ...) and verse order — via smart-paste (`app/utils/song_utils.py`)
- [x] Add song (with selected verse order) as a service item

### 6. ✅ Theme Editor
**Description**: Global + per-item theme editing matching NodeVersion's `ServiceTheme` shape
**Files**: `app/stores/theme_store.py`, `app/widgets/theme_editor.py`
**Acceptance criteria**:
- [x] Background: color / image / video + opacity — only color exposed in the editor UI so far; image/video fields exist on the model but have no picker yet
- [x] Scripture text style: verse text, reference, version (font, size, weight, color, position) — editor UI covers color/size/show for the most common fields; full per-field forms deferred
- [x] Song text style: lyrics, metadata
- [x] Applies live to Output window preview — `ThemeStore.apply_theme` calls `service_store.touch()`, which both `PreviewPanel` and `OutputWindow` already listen to
- [x] Bonus: ported all 9 NodeVersion prebuilt themes (`app/utils/theme_gallery.py`) + a `ThemeGallery` picker dialog

### 7. ✅ Embedded Remote-Control Server
**Description**: Flask-SocketIO server + minimal mobile HTML page, run in a background thread
**Files**: `app/server/remote_server.py`, `app/server/templates/remote.html`
**Acceptance criteria**:
- [x] Serves remote page on port 5183 — verified with `curl` returning HTTP 200 while the Qt app runs
- [x] Prev/Next/Live/Black buttons work from a phone browser — wired via Socket.IO `command` event
- [x] Commands are marshaled safely into the Qt main thread (queue or queued signal) — `RemoteBridge` + `Qt.ConnectionType.QueuedConnection`
- [x] QR code shown in Control window for pairing (reuse `qrcode` Python package) — `RemotePairingDialog`

---

## Medium Priority

### 8. 🔲 Media Items (Image / Video / PDF)
**Description**: Add image/video/PDF service items and render them in the Output window
**Files**: `app/models/service.py`, `app/widgets/media_editor.py`, `app/windows/output_window.py`
**Notes**: Use `QMediaPlayer`/`QVideoWidget` (PySide6.QtMultimedia) for video; `QPdfDocument`/`QPdfView` (PySide6.QtPdf) for PDF — both native Qt, no browser engine needed

### 9. 🔲 Audio Recording & Transcription
**Description**: Record sermon audio, transcribe via OpenAI Whisper (or local `whisper` / `faster-whisper` package)
**Files**: `app/widgets/audio_recorder.py`, `app/utils/transcription.py`
**Notes**: Prefer a local Whisper model to avoid a network dependency, unless the user wants to keep OpenAI's hosted API (carry the API key setting over from NodeVersion either way)

### 10. ✅ Export / Outline Generation
**Description**: Export service as markdown/outline text
**Files**: `app/utils/exporters.py`
**Acceptance criteria**: Same two modes as NodeVersion — quick outline text, and full markdown with transcript — transcript inclusion deferred since audio recording (#9) isn't implemented yet; `ExportDialog` supports copy-to-clipboard and save-as

### 11. ✅ Settings & Persistence Polish
**Description**: Settings dialog for API keys, Dropbox auth, remote server port
**Files**: `app/stores/settings_store.py`, `app/widgets/settings_dialog.py`
**Note**: Remote server port field is currently informational only — `remote_server.start_server()` still starts on the hardcoded default (5183) rather than reading it back from settings

---

## Technical Debt / Deferred (carried over from NodeVersion, unchanged priority)

### 12. ⚠️ PPTX Rendering (Deferred)
**Status**: Deferred, same as NodeVersion. Consider `python-pptx` for reading + rendering slides to images as a stopgap.

### 13. ⚠️ Dropbox Integration (Deferred)
**Status**: Deferred. `dropbox` Python SDK is available when needed; OAuth flow works fine from Qt via `QDesktopServices.openUrl` + local callback server.

---

## Known Issues & Edge Cases (carried over)

### 14. 🔲 Scripture Reference Parsing Edge Cases
Same limitations as NodeVersion: no comma-separated passages, no chapter-only ranges, no validation against book structure.

### 15. 🔲 Large Bible File Performance
Profile JSON load time for large translations; consider `ijson` streaming parse or lazy per-chapter loading if it's slow.

### 16. 🔲 Media File Size Limits
No enforcement yet; define limits before shipping.

### 18. 🔲 Web Scripture Import Tool (BibleGateway and similar sites)
**Description**: A future importer to pull scripture text directly from BibleGateway and other
Bible websites, for translations/formats not already covered by our Zefania XML importer.
**Notes**:
- Poetic vs. continuous styling is **already fully data-driven and working today** — verified our
  existing ESV/NIV/CSB sample files already contain real embedded `\n` characters within a verse's
  `text` for poetic passages (e.g. Psalms) and none for prose (e.g. Genesis); this originates from
  the Zefania XML source itself (`<VERS>` elements literally contain multi-line text for poetry).
  Rendering preserves whatever line breaks are already in a verse's own text, and consecutive verses
  are always joined with a single space (never a forced line break) — so poetic structure shows up
  exactly where the source data has it, and nowhere else, with no per-book/per-verse flag needed.
  Verse numbers are shown as Unicode superscript (`app/utils/pagination.py::superscript_number`).
- The legacy `ServiceTheme.scripture.verse_line_breaks` field (kept for on-disk JSON compatibility
  with NodeVersion) is no longer read by pagination — it used to force every verse onto its own
  line regardless of poetic/prose content, which conflicted with the data-driven approach above.
- The BibleGateway importer itself (scraping/parsing their HTML, respecting their terms of use, and
  mapping their poetry line markup to real `\n` characters in `ScriptureVerse.text` — same
  convention as our existing data) is NOT built yet — this is a placeholder for that future work.

---

## Testing

### 17. 🔲 Add pytest tests for models & utils
**Files**: `tests/test_bible_utils.py`, `tests/test_service_model.py`
**Test cases**: reference parsing round-trip, JSON round-trip for `Service`/`Song`/`Theme` dataclasses

---

## Notes

- This is a **rewrite**, not a port-by-transpilation — Qt idioms (signals/slots, native widgets) replace React/Zustand/Electron IPC wholesale.
- `../NodeVersion` is kept as read-only reference for feature behavior and data formats; do not edit it as part of this project.
- Instruction files ported (2026-08-21): see `.github/instructions/`, `.github/agents/`, `.github/skills/`.
- Next steps: work top-down through "High Priority (MVP)" section in order — models → windows → bible/song → theme → remote control.
