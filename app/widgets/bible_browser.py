"""Bible browser dialog: pick a translation, enter a quick reference, insert as a ScriptureItem."""
from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.models.service import ScriptureItem, Slide
from app.models.theme import default_theme
from app.stores.bible_store import BibleStore
from app.stores.service_store import ServiceStore
from app.utils.bible_utils import find_verses, format_reference, parse_reference
from app.utils.canvas import DEFAULT_CANVAS_RATIO, size_for_ratio
from app.utils.pagination import paginate_item
from app.widgets.slide_renderer import SlideRenderer


class BibleBrowser(QDialog):
    def __init__(self, bible_store: BibleStore, service_store: ServiceStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Insert Scripture")
        self.resize(950, 600)
        self._bible_store = bible_store
        self._service_store = service_store

        self._translation_combo = QComboBox()
        self._reference_edit = QLineEdit()
        self._reference_edit.setPlaceholderText('e.g. "John 3:16-21" or "1 Cor 13:4-7"')
        self._preview_content = QWidget()
        self._preview_layout = QVBoxLayout(self._preview_content)
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_layout.setSpacing(10)
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setWidget(self._preview_content)
        insert_button = QPushButton("Insert")
        insert_button.clicked.connect(self._insert)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        form = QFormLayout()
        form.addRow("Translation", self._translation_combo)
        form.addRow("Reference", self._reference_edit)
        left_layout.addLayout(form)
        left_layout.addWidget(insert_button)
        left_layout.addStretch(1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        right_layout.addWidget(QLabel("Preview"))
        right_layout.addWidget(self._preview_scroll, stretch=1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 630])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        bible_store.index_changed.connect(self._populate_translations)
        self._translation_combo.currentIndexChanged.connect(self._on_translation_changed)
        self._reference_edit.textChanged.connect(self._update_preview)
        if not bible_store.index:
            bible_store.load_index()
        else:
            self._populate_translations(bible_store.index)

    def _populate_translations(self, index) -> None:
        self._translation_combo.blockSignals(True)
        self._translation_combo.clear()
        for entry in index:
            self._translation_combo.addItem(f"{entry.name} ({entry.abbreviation})", entry.id)
        preferred_index = self._translation_combo.findData(
            self._bible_store.preferred_translation_id
        )
        self._translation_combo.setCurrentIndex(preferred_index if preferred_index >= 0 else 0)
        self._translation_combo.blockSignals(False)
        self._on_translation_changed()

    def _on_translation_changed(self, *_args) -> None:
        bible_id = self._translation_combo.currentData()
        if bible_id is not None:
            self._bible_store.set_active_translation(bible_id)
        self._update_preview()

    def _current_theme(self):
        service = self._service_store.service
        return service.theme if service is not None else default_theme()

    def _clear_preview(self) -> None:
        self._preview_content.setMinimumHeight(0)
        while self._preview_layout.count():
            child = self._preview_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def _update_preview(self, *_args) -> None:
        self._clear_preview()
        translation = self._bible_store.active_translation
        if translation is None:
            return
        try:
            parsed = parse_reference(self._reference_edit.text())
            verses = find_verses(translation, parsed)
        except ValueError:
            return
        if not verses:
            return

        resolved_book = verses[0].book if verses else None
        reference_text = format_reference(parsed, resolved_book)
        item = ScriptureItem(
            id="preview",
            title=reference_text,
            bible=translation.id,
            reference=reference_text,
            verses=verses,
        )
        theme = self._current_theme()
        pages = paginate_item(item, theme, size_for_ratio(DEFAULT_CANVAS_RATIO))
        for page_index, page_text in enumerate(pages):
            renderer = SlideRenderer(self._preview_content)
            renderer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            renderer.setMinimumSize(320, 240)
            renderer.set_black(False)
            renderer.render(
                item,
                theme,
                page_text,
                translation.abbreviation,
                page_index=page_index,
                total_pages=len(pages),
            )
            self._preview_layout.addWidget(renderer)
        self._preview_layout.addStretch(1)
        self._preview_layout.activate()
        self._preview_content.setMinimumHeight(self._preview_layout.sizeHint().height())
        self._preview_scroll.verticalScrollBar().setValue(0)

    def _insert(self) -> None:
        if self._service_store.service is None:
            QMessageBox.warning(self, "Insert Scripture", "No service is open.")
            return

        bible_id = self._translation_combo.currentData()
        if bible_id is None:
            QMessageBox.warning(self, "Insert Scripture", "No Bible translation available.")
            return
        self._bible_store.set_active_translation(bible_id)
        translation = self._bible_store.active_translation
        if translation is None:
            return

        try:
            parsed = parse_reference(self._reference_edit.text())
            verses = find_verses(translation, parsed)
        except ValueError as exc:
            QMessageBox.warning(self, "Insert Scripture", str(exc))
            return

        if not verses:
            QMessageBox.warning(self, "Insert Scripture", "No verses found for that reference.")
            return

        resolved_book = verses[0].book
        reference_text = format_reference(parsed, resolved_book)
        slide_content = "\n".join(v.text for v in verses)
        item = ScriptureItem(
            id=str(uuid.uuid4()),
            title=reference_text,
            bible=translation.id,
            reference=reference_text,
            verses=verses,
            slides=[Slide(id=str(uuid.uuid4()), content=slide_content)],
        )
        self._service_store.add_item(item)
        self.accept()

