# Codebase Exploration: Theme, Scripture, & Service State (Python Edition)

Adapted from `../NodeVersion/CODEBASE_EXPLORATION.md`. Describes the target dataclass structure for the Python rewrite — field names and JSON shape are kept 1:1 compatible with NodeVersion so the copied `data/` files load without migration.

## 1. Theme Structure

### Location & Definition (target)
- **Type Definition**: `app/models/theme.py`
- **Default Theme**: `DEFAULT_THEME` constant in the same module
- **Store**: `app/stores/theme_store.py` manages the active theme; `app/stores/service_store.py` holds it as part of the current `Service`

### ServiceTheme Dataclasses

```python
from dataclasses import dataclass, field
from typing import Literal

Position = Literal["bottom-right", "bottom-left", "top-left", "top-right"]

@dataclass
class TextStyle:
    font_family: str
    font_size: int
    font_weight: str   # 'normal' | 'bold'
    font_style: str     # 'normal' | 'italic'
    color: str
    text_align: Literal["left", "center", "right"] | None = None

@dataclass
class ReferenceStyle(TextStyle):
    position: Position = "bottom-right"

@dataclass
class VersionStyle(TextStyle):
    show: bool = True
    position: Position = "bottom-left"

@dataclass
class MetadataStyle(TextStyle):
    show: bool = True
    position: Literal["bottom-left", "bottom-right"] = "bottom-left"

@dataclass
class BackgroundTheme:
    type: Literal["color", "image", "video"] = "color"
    color: str = "#000000"
    image_path: str | None = None
    video_path: str | None = None
    opacity: float = 1.0

@dataclass
class ScriptureTheme:
    verse_text: TextStyle
    reference: ReferenceStyle
    version: VersionStyle
    verse_line_breaks: bool = False

@dataclass
class SongTheme:
    lyrics: TextStyle
    metadata: MetadataStyle

@dataclass
class ServiceTheme:
    background: BackgroundTheme
    scripture: ScriptureTheme
    song: SongTheme
```

### Theme Properties (unchanged semantics from NodeVersion)

| Property | Type | Description | Default |
|----------|------|-------------|---------|
| `background.type` | 'color', 'image', 'video' | Background rendering type | 'color' |
| `background.color` | hex string | Fallback/primary background color | '#000000' |
| `background.image_path` | str \| None | Path to background image | None |
| `background.video_path` | str \| None | Path to background video | None |
| `background.opacity` | float | Layer opacity (0-1) | 1.0 |
| `scripture.verse_text` | TextStyle | Verse text styling | 48px white Inter |
| `scripture.reference` | ReferenceStyle | Book/chapter ref styling | 32px cyan, bold, bottom-right |
| `scripture.version` | VersionStyle | Bible translation label | 24px slate, italic, shown, bottom-left |
| `scripture.verse_line_breaks` | bool | Add newline between verses | False |
| `song.lyrics` | TextStyle | Song lyric styling | 56px white, bold Inter |
| `song.metadata` | MetadataStyle | Song title/author styling | 24px gray, normal, shown, bottom-left |

### Default Theme Creation (target, matches NodeVersion values)

```python
DEFAULT_THEME = ServiceTheme(
    background=BackgroundTheme(type="color", color="#000000", opacity=1.0),
    scripture=ScriptureTheme(
        verse_text=TextStyle("Inter", 48, "normal", "normal", "#ffffff", "left"),
        reference=ReferenceStyle("Inter", 32, "bold", "normal", "#22d3ee", position="bottom-right"),
        version=VersionStyle("Inter", 24, "normal", "italic", "#94a3b8", show=True, position="bottom-left"),
        verse_line_breaks=False,
    ),
    song=SongTheme(
        lyrics=TextStyle("Inter", 56, "bold", "normal", "#ffffff"),
        metadata=MetadataStyle("Inter", 24, "normal", "normal", "#94a3b8", show=True, position="bottom-left"),
    ),
)
```

### JSON Compatibility

NodeVersion serialized this as camelCase JSON (`fontFamily`, `fontSize`, `verseLineBreaks`, `imagePath`, ...). Since the copied `data/services/*.json` files use that exact shape, each dataclass needs matching `to_json_dict()` / `from_json_dict(d)` methods that translate `snake_case` Python attributes to/from the existing `camelCase` keys — do **not** rename the on-disk JSON keys.

### Theme Usage in Widgets (target)

#### ThemeEditor Widget
- **File**: `app/widgets/theme_editor.py`
- **Pattern**:
  - Two modes: `global` (affects entire service, edits `ServiceStore`'s theme) or `item` (per-item override stored in that item's `display_settings`)
  - Global theme updates call `service_store.update_theme(...)`, which emits `service_changed`

#### ThemeGallery Widget
- **File**: `app/widgets/theme_gallery.py`
- **Pattern**: Applies a prebuilt theme (Python literal, ported from NodeVersion's `themeGallery.ts`) via `theme_store.apply_theme(theme)`

#### PreviewPanel Widget
- **File**: `app/widgets/preview_panel.py`
- **Pattern**: Renders current service items with the active theme for in-window preview (same content as the Output window, scaled down)

### Per-Item Display Overrides

**Type**: `DisplaySettings` in `app/models/service.py`

```python
@dataclass
class DisplaySettings:
    # Shallow partial overrides of ServiceTheme fields (None = inherit global)
    background: BackgroundTheme | None = None
    scripture: ScriptureTheme | None = None
    song: SongTheme | None = None
    custom_qss: str | None = None   # replaces NodeVersion's customCSS
    verse_range: str | None = None  # forces verse breaks
```

- Item-level overrides are **shallow partials** of `ServiceTheme`, same as NodeVersion's `DeepPartial<ServiceTheme>` — merge logic lives in a small `merge_theme(base, override)` helper in `app/utils/theme_utils.py`
- Calculated at render time for scripture (font sizes affect slide breaks), same as NodeVersion
