---
name: widget-guidelines
description: "Use when: creating or modifying PySide6 widgets in app/widgets/. Covers file structure, QSS styling, store integration, and naming."
applyTo: "app/widgets/**/*.py"
---

# Widget Guidelines

## File Structure

One widget per module:
```
app/widgets/my_component.py   # QWidget subclass: class MyComponent(QWidget)
```

No co-located stylesheet file is required — prefer `setObjectName()` + a shared `app/resources/theme.qss` loaded once at startup, or minimal inline `setStyleSheet()` for one-off cases. Avoid scattering large inline QSS blocks across widgets.

## Widget Pattern

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from app.stores.my_store import MyStore

class MyComponent(QWidget):
    def __init__(self, store: MyStore, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("MyComponent")
        self._store = store

        layout = QVBoxLayout(self)
        self._title_label = QLabel()
        self._action_button = QPushButton("Action")
        self._action_button.clicked.connect(self._handle_click)
        layout.addWidget(self._title_label)
        layout.addWidget(self._action_button)

        store.data_changed.connect(self._on_data_changed)
        self._on_data_changed(store.data)

    def _on_data_changed(self, data: str) -> None:
        self._title_label.setText(data)

    def _handle_click(self) -> None:
        self._store.do_action()
```

## State Management Rules

1. **Shared state** → Read/write only through a store (`app/stores/`)
2. **Widget-local state** → Plain instance attributes (e.g. form field buffers before save)
3. **Never prop-drill state through constructors more than one level** — pass the store, not individual derived values
4. **Never mutate a store's internal fields directly** — call its methods, which emit the appropriate signal

### Anti-Pattern
```python
# DON'T: passing raw data through many constructor layers
ServiceList(services, on_update=..., on_delete=..., theme=..., settings=...)
```

### Correct Pattern
```python
# DO: pass the store, let the widget subscribe to what it needs
ServiceList(service_store)
```

## Naming

- Module: `snake_case.py`
- Class: `PascalCase` matching the concept (`ServiceList`, `BibleBrowser`)
- Signals defined on a widget: `snake_case`, e.g. `item_selected = Signal(str)`
- Qt object names (for QSS targeting): match the class name, e.g. `self.setObjectName("ServiceList")`

## Python Best Practices

- ✅ **Always type constructor params and public methods**
- ✅ **Disconnect signals in `closeEvent`/`deleteLater` paths if the widget can outlive its store subscription**
- ✅ **Use `@dataclass` for any small data bundles passed between widgets**
- ❌ **Never use bare `dict`/`Any` for domain data** — use the dataclasses in `app/models/`

## Common Patterns

### With Dialogs
```python
from PySide6.QtWidgets import QDialog

class ThemeEditorDialog(QDialog):
    def __init__(self, theme_store, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Theme Editor")
        # ... build form, wire OK/Cancel ...
```

### With Dynamic Theme-Driven Styling
```python
def _apply_theme(self, theme: ServiceTheme) -> None:
    self.setStyleSheet(
        f"background-color: {theme.background.color}; color: {theme.scripture.verse_text.color};"
    )
```

### With Drag-and-Drop Reordering
```python
from PySide6.QtWidgets import QListWidget, QAbstractItemView

class ServiceList(QListWidget):
    def __init__(self, service_store, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.model().rowsMoved.connect(self._on_rows_moved)
```

## Testing Widget Readiness

Before submitting a widget:
- [ ] Constructor params fully typed
- [ ] Reads/writes state only through a store, not ad-hoc globals
- [ ] `mypy app/widgets/` passes
- [ ] `ruff check app/widgets/` passes
- [ ] No unused imports/variables
- [ ] Manually verified in `python -m app.main` (no automated UI test framework yet)
