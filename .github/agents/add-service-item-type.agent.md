---
name: service-item-type-agent
description: "Multi-step agent that orchestrates adding a new service item type. Handles model definitions, rendering in the Output window, editor widgets, and export logic. Python/PySide6 replacement for the old React service-item-type agent."
---

# Add Service Item Type Agent

This agent guides you through adding a completely new service item type (e.g., video, note, hymn) by orchestrating changes across the model, Output rendering, editor widget, and exporters.

## What You Provide

The agent will ask you to specify:
1. **Item type name** (snake_case, e.g., `video`, `animated_slide`, `hymn`)
2. **Data shape** — key fields (e.g., `video_path`, `duration`, `auto_play`)
3. **Display behavior** — how it renders on the Output window (e.g., fullscreen video with controls)
4. **Editor UI** — what controls are needed to configure the item

## Workflow

The agent will:

1. **Add model dataclass** → `{Type}Item` in `app/models/service.py`, added to the `ServiceItem` union and a `is_{type}_item()` type guard
2. **Add Output rendering** → New branch in `app/windows/output_window.py`'s slide renderer (or a dedicated widget in `app/widgets/`)
3. **Add editor widget** → `app/widgets/{type}_editor.py`
4. **Wire into Control window** → Add a toolbar button + editor invocation in `app/windows/control_window.py`
5. **Optional export logic** → Extend `app/utils/exporters.py` if the item should appear in markdown/outline export
6. **Verify** → Run `mypy`/`ruff`, launch the app, add one item of the new type end-to-end

## Guided Example

**User:** "Add a new video item type"

**Agent steps:**
1. Ask for video fields: `video_path`, `duration`, `auto_play`, `show_controls`
2. Add `VideoItem` dataclass with those fields
```python
@dataclass
class VideoItem(BaseServiceItem):
    type: Literal["video"] = "video"
    video_path: str = ""
    duration: float = 0.0
    auto_play: bool = False
    show_controls: bool = True
```
3. Add a render branch in `output_window.py` using `PySide6.QtMultimedia.QMediaPlayer` + `QVideoWidget`
4. Add `VideoEditor` widget (form: file picker for path, duration spin box, two checkboxes)
5. Add "Add Video" toolbar action + modal invocation in `control_window.py`
6. Verify: `mypy app/`, `ruff check app/`, then manually add a video item and confirm it plays on the Output window

Result: Users can now add videos to services.

## Editor Widget Template

```python
from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QDialogButtonBox
import uuid
from app.models.service import VideoItem

class VideoEditorDialog(QDialog):
    def __init__(self, item: VideoItem | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Item")
        self._item = item

        self._path_edit = QLineEdit(item.video_path if item else "")
        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(0, 36000)
        self._duration_spin.setValue(int(item.duration) if item else 0)
        self._auto_play_check = QCheckBox("Auto-play")
        self._auto_play_check.setChecked(item.auto_play if item else False)
        self._controls_check = QCheckBox("Show controls")
        self._controls_check.setChecked(item.show_controls if item else True)

        form = QFormLayout(self)
        form.addRow("Video path", self._path_edit)
        form.addRow("Duration (s)", self._duration_spin)
        form.addRow(self._auto_play_check)
        form.addRow(self._controls_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def result_item(self) -> VideoItem:
        return VideoItem(
            id=self._item.id if self._item else str(uuid.uuid4()),
            type="video",
            title=self._path_edit.text().rsplit("/", 1)[-1] or "Video",
            display_settings=self._item.display_settings if self._item else None,
            slides=self._item.slides if self._item else [],
            video_path=self._path_edit.text(),
            duration=float(self._duration_spin.value()),
            auto_play=self._auto_play_check.isChecked(),
            show_controls=self._controls_check.isChecked(),
        )
```

---

## How to Invoke

```
/add-service-item-type: Add a "note" item type that displays text with custom formatting
/add-service-item-type: Add an "animated_slide" type for image-sequence presentations
/add-service-item-type: Add a "hymn" type with lyrics and metadata
```

The agent handles all implementation details and file creation.
