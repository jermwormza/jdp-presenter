---
name: add-service-item-type
description: "Use when: adding a new service item type (e.g., 'video', 'hymn', 'comment') to the presenter. This skill orchestrates updates across models, the Output window renderer, editor widgets, and exporters."
---

# Add Service Item Type Skill

This skill guides you through adding a completely new service item type to JDP Presenter (Python Edition). A service item is any content that can be added to a service order (scripture, song, PDF, PPTX, recording, etc.).

## What Is a Service Item Type?

Service items are dataclasses distinguished by a `type` discriminator field:
```python
# Current types (snake_case)
ServiceItemType = Literal["scripture", "song", "pdf", "pptx", "recording"]

# Example new types
ServiceItemType = Literal["scripture", "song", "pdf", "pptx", "recording", "video", "note"]
```

Each type has:
- A **model dataclass** (`app/models/service.py`)
- A **rendering path** in the Output window
- An **editor widget** (Control window dialog)
- Optional **export logic** (`app/utils/exporters.py`)

---

## Step 1: Define the Model

Add to [`app/models/service.py`](../../../app/models/service.py):

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class VideoItem(BaseServiceItem):
    type: Literal["video"] = "video"
    video_path: str = ""
    duration: float = 0.0
    auto_play: bool = False
    show_controls: bool = True

# Add to the union type
ServiceItem = ScriptureItem | SongItem | PdfItem | PptxItem | RecordingItem | VideoItem

# Add a type guard
def is_video_item(item: ServiceItem) -> bool:
    return item.type == "video"
```

---

## Step 2: Add Output Window Rendering

In [`app/windows/output_window.py`](../../../app/windows/output_window.py), add a branch to the slide renderer:

```python
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget

def _render_item(self, item: ServiceItem) -> None:
    if is_video_item(item):
        self._render_video(item)
    elif is_scripture_item(item):
        self._render_scripture(item)
    # ... other types ...

def _render_video(self, item: VideoItem) -> None:
    video_widget = QVideoWidget(self)
    player = QMediaPlayer(self)
    player.setVideoOutput(video_widget)
    player.setSource(QUrl.fromLocalFile(item.video_path))
    if item.auto_play:
        player.play()
    self._set_content_widget(video_widget)
```

Keep a reference to the `QMediaPlayer` on `self` (or a small controller object) so it isn't garbage-collected mid-playback.

---

## Step 3: Add an Editor Widget

Create [`app/widgets/video_editor.py`](../../../app/widgets/) as a `QDialog` (see the full template in `.github/agents/add-service-item-type.agent.md`):

```python
class VideoEditorDialog(QDialog):
    def __init__(self, item: VideoItem | None = None, parent=None):
        ...  # form fields for video_path, duration, auto_play, show_controls

    def result_item(self) -> VideoItem:
        ...  # build and return a VideoItem from form values
```

---

## Step 4: Wire Into the Control Window

In [`app/windows/control_window.py`](../../../app/windows/control_window.py):

```python
action = QAction("Add Video", self)
action.triggered.connect(self._add_video_item)
toolbar.addAction(action)

def _add_video_item(self) -> None:
    dialog = VideoEditorDialog(parent=self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        self._service_store.add_item(dialog.result_item())
```

---

## Step 5: Export Logic (Optional)

If the new type should appear in markdown/outline export, extend [`app/utils/exporters.py`](../../../app/utils/exporters.py) with a formatting branch for `VideoItem`.

---

## Step 6: Verify

- [ ] `mypy app/` passes
- [ ] `ruff check app/` passes
- [ ] Launch with `python -m app.main`, add one item of the new type to a service, confirm it renders on the Output window
- [ ] Confirm the item round-trips through `data/services/*.json` save/load

---

## How to Invoke

```
/add-service-item-type: Add a "note" item type that displays text with custom formatting
/add-service-item-type: Add an "animated_slide" type for image-sequence presentations
/add-service-item-type: Add a "hymn" type with lyrics and metadata
```
