"""Control window: main editing UI (service list, menu bar, live/black controls)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QDesktopServices,
    QGuiApplication,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from app.models.service import ImageItem, Service, Slide, TextItem, VideoItem
from app.models.theme import default_theme
from app.persistence import service_repo
from app.persistence.paths import SERVICES_DIR, RECORDINGS_DIR
from app.stores.bible_store import BibleStore
from app.stores.display_store import DisplayStore
from app.stores.media_store import MediaPlayerStore
from app.stores.output_store import OutputStore
from app.stores.recording_store import (
    DEFAULT_FORMAT,
    DEFAULT_QUALITY,
    FORMATS,
    QUALITIES,
    RecordingStore,
)
from app.stores.service_store import ServiceStore
from app.stores.settings_store import SettingsStore
from app.stores.song_store import SongStore
from app.stores.theme_store import ThemeStore
from app.utils.icons import (
    delete_icon,
    export_icon,
    import_icon,
    media_icon,
    move_down_icon,
    move_up_icon,
    new_icon,
    open_icon,
    output_screen_icon,
    pause_icon,
    play_icon,
    print_icon,
    qr_icon,
    record_icon,
    save_icon,
    scripture_icon,
    song_icon,
    stop_icon,
    text_icon,
)
from app.utils.help import open_help
from app.utils.hotkeys import HOTKEY_DEFINITIONS, configured_hotkeys
from app.utils.update_checker import ReleaseInfo, UpdateChecker
from app.utils.window_state import encode_geometry, encode_splitter_state, restore_splitter_state
from app.version import APP_VERSION
from app.widgets.bible_browser import BibleBrowser
from app.widgets.export_dialog import ExportDialog
from app.widgets.import_dialog import ImportDialog
from app.widgets.media_browser import MediaBrowser
from app.widgets.preview_panel import NextPreviewPanel, PreviewPanel
from app.widgets.quick_add_search import QuickAddSearch
from app.widgets.recording_indicator import RecordingIndicatorWidget
from app.widgets.recording_options_dialog import (
    RecordingOptionsDialog,
    default_recording_name,
    next_available_recording_name,
)
from app.widgets.recordings_pane import RecordingsPane
from app.widgets.service_list import ServiceList
from app.widgets.settings_dialog import SettingsDialog
from app.widgets.song_browser import SongBrowser
from app.widgets.theme_editor import ThemeEditor
from app.widgets.theme_gallery import ThemeGallery
from app.utils.exporters import generate_full_markdown, generate_outline
from app.windows.output_window import OutputWindow
class ControlWindow(QMainWindow):
    def __init__(
        self,
        service_store: ServiceStore,
        display_store: DisplayStore,
        output_store: OutputStore,
        media_store: MediaPlayerStore,
        recording_store: RecordingStore,
        bible_store: BibleStore,
        song_store: SongStore,
        theme_store: ThemeStore,
        settings_store: SettingsStore,
        output_window: OutputWindow,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("JDP Presenter — Control")
        self.resize(1200, 800)
        self._service_store = service_store
        self._display_store = display_store
        self._output_store = output_store
        self._media_store = media_store
        self._recording_store = recording_store
        self._bible_store = bible_store
        self._song_store = song_store
        self._theme_store = theme_store
        self._settings_store = settings_store
        self._output_window = output_window
        self._update_checker = UpdateChecker(self)
        self._update_check_silent = False
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.up_to_date.connect(self._on_up_to_date)
        self._update_checker.failed.connect(self._on_update_check_failed)
        self._update_checker.checking_changed.connect(self._on_update_checking_changed)
        self._current_service_path: str | None = None  # Track current service file path
        self._resume_media_after_scrub = False
        central = QWidget()
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        item_list_container = QWidget()
        item_list_layout = QVBoxLayout(item_list_container)
        item_list_layout.setContentsMargins(0, 0, 0, 0)
        item_list_layout.setSpacing(0)
        item_list_layout.addWidget(self._build_item_list_toolbar(), stretch=0)
        self._quick_add = QuickAddSearch(service_store, song_store, bible_store)
        item_list_layout.addWidget(self._quick_add, stretch=0)
        self._item_list = ServiceList(service_store, output_store, song_store)
        item_list_layout.addWidget(self._item_list, stretch=1)
        # Recordings pane below the service list
        self._recordings_pane = RecordingsPane(settings_store)
        self._recordings_pane.setMinimumHeight(120)
        item_list_layout.addWidget(self._recordings_pane, stretch=0)
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        preview_layout.addWidget(self._build_output_toolbar(), stretch=0)
        preview_layout.addWidget(self._build_media_transport_toolbar(), stretch=0)
        preview_layout.addWidget(self._build_media_scale_toolbar(), stretch=0)
        self._preview = PreviewPanel(service_store, output_store, media_store)
        preview_layout.addWidget(self._preview, stretch=1)
        next_preview_container = QWidget()
        next_preview_layout = QVBoxLayout(next_preview_container)
        next_preview_layout.setContentsMargins(0, 0, 0, 0)
        next_preview_layout.setSpacing(4)
        next_preview_layout.addWidget(QLabel("Next Item"), stretch=0)
        self._next_preview = NextPreviewPanel(service_store, output_store, media_store)
        next_preview_layout.addWidget(self._next_preview, stretch=1)
        self.preview_video_widget = self._preview.video_widget
        self.next_preview_video_widget = self._next_preview.video_widget
        self._right_splitter = QSplitter(Qt.Orientation.Vertical)
        self._right_splitter.addWidget(preview_container)
        self._right_splitter.addWidget(next_preview_container)
        self._right_splitter.setStretchFactor(0, 2)
        self._right_splitter.setStretchFactor(1, 1)
        self._right_splitter.setSizes([500, 250])
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.addWidget(item_list_container)
        self._main_splitter.addWidget(self._right_splitter)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 2)
        self._main_splitter.setSizes([350, 850])
        outer_layout.addWidget(self._main_splitter)
        self.setCentralWidget(central)
        self._build_menus()
        self.addToolBar(self._build_main_toolbar())
        self._build_shortcuts()
        self._output_store.canvas_changed.connect(self._sync_aspect_ratio_selection)
        self._recording_store.state_changed.connect(self._on_recording_state_changed)
        self._recording_store.duration_changed.connect(self._recording_indicator.set_elapsed_ms)
        self._recording_store.level_changed.connect(self._recording_indicator.set_level)
        self._recording_store.recording_completed.connect(self._on_recording_completed)
        self._recording_store.conversion_failed.connect(self._on_conversion_failed)
        # Connect pause/resume signals from the recording indicator
        self._recording_indicator.pause_requested.connect(self._recording_store.pause)
        self._recording_indicator.resume_requested.connect(self._recording_store.resume)
        # Connect dirty tracking
        self._service_store.dirty_changed.connect(self._on_dirty_changed)
        self._service_store.service_changed.connect(self._on_service_changed)
        self._update_window_title()
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._prompt_save_if_dirty():
            event.ignore()
            return  # noqa: N802 (Qt override)
        self._settings_store.set("lastServicePath", self._current_service_path or "")
        self._settings_store.set("controlWindowGeometry", encode_geometry(self))
        self._settings_store.set("outputWindowGeometry", encode_geometry(self._output_window))
        self._settings_store.set("controlMainSplitterState", encode_splitter_state(self._main_splitter))
        self._settings_store.set("controlPreviewSplitterState", encode_splitter_state(self._right_splitter))
        self._output_window.close()
        super().closeEvent(event)

    def restore_layout(self, main_splitter_state: str | None, preview_splitter_state: str | None) -> None:
        restore_splitter_state(self._main_splitter, main_splitter_state)
        restore_splitter_state(self._right_splitter, preview_splitter_state)
    def set_current_service_path(self, path: str | None) -> None:
        """Track the persisted file backing the active service."""
        self._current_service_path = path
    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        self._add_action(file_menu, "New", self._new_service)
        self._add_action(file_menu, "Open…", self._open_service)
        self._add_action(file_menu, "Save", self._save_service)
        self._add_action(file_menu, "Save As…", self._save_service_as)
        file_menu.addSeparator()
        self._add_action(file_menu, "Import…", self._open_import_dialog)
        self._add_action(file_menu, "Export…", self._open_export_dialog)
        self._add_action(file_menu, "Print…", self._open_print_dialog)
        file_menu.addSeparator()
        self._add_action(file_menu, "Settings…", self._open_settings_dialog)
        insert_menu = menu_bar.addMenu("&Insert")
        self._add_action(insert_menu, "Add Text…", self._add_text_item)
        self._add_action(insert_menu, "Add Scripture…", self._add_scripture_item)
        self._add_action(insert_menu, "Add Song…", self._add_song_item)
        self._add_action(insert_menu, "Add Media…", self._add_media_item)
        theme_menu = menu_bar.addMenu("&Theme")
        self._add_action(theme_menu, "Theme Editor…", self._open_theme_editor)
        self._add_action(theme_menu, "Theme Gallery…", self._open_theme_gallery)
        output_menu = menu_bar.addMenu("&Output")
        self._show_hide_menu_action = QAction("Hide", self)
        self._show_hide_menu_action.triggered.connect(self._toggle_show_hide)
        output_menu.addAction(self._show_hide_menu_action)
        self._update_show_hide_button(self._output_store.is_black)
        output_menu.addSeparator()
        self._add_action(output_menu, "View Output on Secondary Screen", self._show_output_on_secondary)
        aspect_menu = output_menu.addMenu("Aspect Ratio")
        aspect_group = QActionGroup(self)
        aspect_group.setExclusive(True)
        self._aspect_ratio_actions = {}
        for ratio in ("4:3", "16:9", "16:10"):
            ratio_action = QAction(ratio, self, checkable=True)
            ratio_action.setChecked(ratio == self._output_store.canvas_ratio)
            ratio_action.triggered.connect(lambda _checked=False, r=ratio: self._output_store.set_canvas_ratio(r))
            aspect_group.addAction(ratio_action)
            aspect_menu.addAction(ratio_action)
            self._aspect_ratio_actions[ratio] = ratio_action
        font_menu = output_menu.addMenu("Font Size")
        self._add_action(font_menu, "Increase", self._output_store.increase_font_scale)
        self._add_action(font_menu, "Decrease", self._output_store.decrease_font_scale)
        output_menu.addSeparator()
        self._qr_code_menu_action = QAction("Show QR Code", self, checkable=True)
        self._qr_code_menu_action.triggered.connect(self._toggle_qr_code)
        output_menu.addAction(self._qr_code_menu_action)
        help_menu = menu_bar.addMenu("&Help")
        self._add_action(
            help_menu,
            "JDP Presenter Help…",
            lambda: open_help(self._settings_store),
        )
        help_menu.addSeparator()
        self._check_updates_action = self._add_action(
            help_menu,
            "Check for Updates…",
            self.check_for_updates,
        )
    def _add_action(self, menu, text: str, handler) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(handler)
        menu.addAction(action)
        return action

    def check_for_updates(self, *, silent: bool = False) -> None:
        self._update_check_silent = silent
        self._update_checker.check()

    def check_for_updates_on_startup(self) -> None:
        if bool(self._settings_store.get("checkForUpdatesOnStartup", True)):
            self.check_for_updates(silent=True)

    def _on_update_checking_changed(self, checking: bool) -> None:
        self._check_updates_action.setEnabled(not checking)

    def _on_update_available(self, release: ReleaseInfo) -> None:
        reply = QMessageBox.question(
            self,
            "Update Available",
            f"JDP Presenter {release.version} is available. You are using {APP_VERSION}.\n\n"
            "Open the GitHub Releases page to download it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl(release.url))

    def _on_up_to_date(self, latest_version: str) -> None:
        if not self._update_check_silent:
            QMessageBox.information(
                self,
                "No Updates Available",
                f"JDP Presenter {APP_VERSION} is current (latest release: {latest_version}).",
            )

    def _on_update_check_failed(self, detail: str) -> None:
        if self._update_check_silent:
            print(f"[UPDATE] Check failed: {detail}", flush=True)
            return
        QMessageBox.warning(
            self,
            "Update Check Failed",
            f"JDP Presenter could not check GitHub Releases.\n\n{detail}",
        )

    def _configure_toolbar(self, toolbar: QToolBar) -> None:
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(22, 22))

    def _build_main_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Main Toolbar")
        self._configure_toolbar(toolbar)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setMinimumHeight(44)
        new_action = QAction(new_icon(), "New", self)
        new_action.setToolTip("New Service")
        new_action.triggered.connect(self._new_service)
        toolbar.addAction(new_action)
        open_action = QAction(open_icon(), "Open", self)
        open_action.setToolTip("Open Service")
        open_action.triggered.connect(self._open_service)
        toolbar.addAction(open_action)
        save_action = QAction(save_icon(), "Save", self)
        save_action.setToolTip("Save Service")
        save_action.triggered.connect(self._save_service)
        toolbar.addAction(save_action)
        toolbar.addSeparator()
        import_action = QAction(import_icon(), "Import", self)
        import_action.setToolTip("Import")
        import_action.triggered.connect(self._open_import_dialog)
        toolbar.addAction(import_action)
        export_action = QAction(export_icon(), "Export", self)
        export_action.setToolTip("Export")
        export_action.triggered.connect(self._open_export_dialog)
        toolbar.addAction(export_action)
        toolbar.addSeparator()
        print_action = QAction(print_icon(), "Print", self)
        print_action.setToolTip("Print")
        print_action.triggered.connect(self._open_print_dialog)
        toolbar.addAction(print_action)
        toolbar.addSeparator()
        # Recording section
        self._record_toolbar_action = QAction(record_icon(), "Record", self)
        self._record_toolbar_action.setToolTip("Start Recording")
        self._record_toolbar_action.triggered.connect(self._start_recording)
        toolbar.addAction(self._record_toolbar_action)
        self._recording_indicator = RecordingIndicatorWidget()
        toolbar.addWidget(self._recording_indicator)
        return toolbar
    def _build_output_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Output")
        self._configure_toolbar(toolbar)
        self._show_hide_action = QAction("")
        self._show_hide_action.triggered.connect(self._toggle_show_hide)
        toolbar.addAction(self._show_hide_action)
        toolbar.addSeparator()
        decrease_action = QAction("A-", self)
        decrease_action.triggered.connect(self._output_store.decrease_font_scale)
        toolbar.addAction(decrease_action)
        increase_action = QAction("A+", self)
        increase_action.triggered.connect(self._output_store.increase_font_scale)
        toolbar.addAction(increase_action)
        toolbar.addSeparator()
        aspect_group = QActionGroup(self)
        aspect_group.setExclusive(True)
        self._aspect_ratio_toolbar_actions = {}
        for ratio in ("4:3", "16:9", "16:10"):
            ratio_action = QAction(ratio, self, checkable=True)
            ratio_action.setChecked(ratio == self._output_store.canvas_ratio)
            ratio_action.triggered.connect(lambda _checked=False, r=ratio: self._output_store.set_canvas_ratio(r))
            aspect_group.addAction(ratio_action)
            toolbar.addAction(ratio_action)
            self._aspect_ratio_toolbar_actions[ratio] = ratio_action
        self._output_store.is_black_changed.connect(self._update_show_hide_button)
        self._update_show_hide_button(self._output_store.is_black)
        toolbar.addSeparator()
        # Media playback play/pause button, placed to the left of the QR-code button.
        self._media_play_action = QAction(play_icon(), "", self)
        self._media_play_action.setToolTip("Play/Pause Media")
        self._media_play_action.triggered.connect(self._media_store.toggle)
        self._media_play_action.setEnabled(False)
        toolbar.addAction(self._media_play_action)
        self._qr_code_toolbar_action = QAction(qr_icon(), "", self, checkable=True)
        self._qr_code_toolbar_action.setToolTip("Show QR Code for Remote Control")
        self._qr_code_toolbar_action.triggered.connect(self._toggle_qr_code)
        toolbar.addAction(self._qr_code_toolbar_action)
        secondary_output_action = QAction(output_screen_icon(), "", self)
        secondary_output_action.setToolTip("View Output on Secondary Screen")
        secondary_output_action.triggered.connect(self._show_output_on_secondary)
        toolbar.addAction(secondary_output_action)
        return toolbar
    def _build_media_transport_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Media")
        self._configure_toolbar(toolbar)
        self._media_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._media_seek_slider.setRange(0, 0)
        self._media_seek_slider.setEnabled(False)
        self._media_seek_slider.setTracking(True)
        self._media_seek_slider.sliderPressed.connect(self._on_media_scrub_started)
        self._media_seek_slider.valueChanged.connect(self._on_media_scrubbed)
        self._media_seek_slider.sliderReleased.connect(self._on_media_scrub_finished)
        toolbar.addWidget(self._media_seek_slider)
        self._media_store.active_changed.connect(self._on_media_active_changed)
        self._media_store.playing_changed.connect(self._on_media_playing_changed)
        self._media_store.duration_changed.connect(self._media_seek_slider.setMaximum)
        self._media_store.position_changed.connect(self._on_media_position_changed)
        return toolbar
    def _on_media_active_changed(self, item) -> None:
        has_media = item is not None
        self._resume_media_after_scrub = False
        self._media_play_action.setEnabled(has_media)
        self._media_seek_slider.setEnabled(has_media)
        if not has_media:
            self._media_seek_slider.setValue(0)
    def _on_media_playing_changed(self, is_playing: bool) -> None:
        self._media_play_action.setIcon(pause_icon() if is_playing else play_icon())
    def _on_media_position_changed(self, position_ms: int) -> None:
        if not self._media_seek_slider.isSliderDown():
            self._media_seek_slider.setValue(position_ms)

    def _on_media_scrub_started(self) -> None:
        self._resume_media_after_scrub = self._media_store.is_playing()
        if self._resume_media_after_scrub:
            self._media_store.pause()
        self._media_store.seek(self._media_seek_slider.value())

    def _on_media_scrubbed(self, position_ms: int) -> None:
        if self._media_seek_slider.isSliderDown():
            self._media_store.seek(position_ms)

    def _on_media_scrub_finished(self) -> None:
        self._media_store.seek(self._media_seek_slider.value())
        if self._resume_media_after_scrub:
            self._media_store.play()
        self._resume_media_after_scrub = False
    def _build_media_scale_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Media Scale")
        self._configure_toolbar(toolbar)
        scale_group = QActionGroup(self)
        scale_group.setExclusive(True)
        self._scale_mode_actions: dict[str, QAction] = {}
        for mode, label in (
            ("fit", "Fit"),
            ("original", "Original"),
            ("fill_width", "Fill Width"),
            ("fill_height", "Fill Height"),
        ):
            action = QAction(label, self, checkable=True)
            action.triggered.connect(lambda _checked=False, m=mode: self._set_current_scale_mode(m))
            scale_group.addAction(action)
            toolbar.addAction(action)
            self._scale_mode_actions[mode] = action
        self._scale_toolbar = toolbar
        self._output_store.position_changed.connect(self._sync_scale_mode_toolbar)
        self._service_store.service_changed.connect(self._sync_scale_mode_toolbar)
        self._sync_scale_mode_toolbar()
        return toolbar
    def _set_current_scale_mode(self, mode: str) -> None:
        item = self._output_store.current_item()
        if not isinstance(item, (ImageItem, VideoItem)):
            return
        self._service_store.update_item(item.id, scale_mode=mode)
    def _sync_scale_mode_toolbar(self, *_args) -> None:
        item = self._output_store.current_item()
        is_visual_media = isinstance(item, (ImageItem, VideoItem))
        self._scale_toolbar.setEnabled(is_visual_media)
        mode = item.scale_mode if is_visual_media else "fit"
        action = self._scale_mode_actions.get(mode)
        if action is not None:
            action.setChecked(True)
    def _build_item_list_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Service Items")
        self._configure_toolbar(toolbar)
        toolbar.setMinimumHeight(36)
        add_song_action = QAction(song_icon(), "", self)
        add_song_action.setToolTip("Add Song…")
        add_song_action.triggered.connect(self._add_song_item)
        toolbar.addAction(add_song_action)
        add_scripture_action = QAction(scripture_icon(), "", self)
        add_scripture_action.setToolTip("Add Scripture…")
        add_scripture_action.triggered.connect(self._add_scripture_item)
        toolbar.addAction(add_scripture_action)
        add_text_action = QAction(text_icon(), "", self)
        add_text_action.setToolTip("Add Text…")
        add_text_action.triggered.connect(self._add_text_item)
        toolbar.addAction(add_text_action)
        add_media_action = QAction(media_icon(), "", self)
        add_media_action.setToolTip("Add Media…")
        add_media_action.triggered.connect(self._add_media_item)
        toolbar.addAction(add_media_action)
        toolbar.addSeparator()
        move_up_action = QAction(move_up_icon(), "", self)
        move_up_action.setToolTip("Move Selected Item Up")
        move_up_action.triggered.connect(lambda: self._item_list.move_selected("up"))
        toolbar.addAction(move_up_action)
        move_down_action = QAction(move_down_icon(), "", self)
        move_down_action.setToolTip("Move Selected Item Down")
        move_down_action.triggered.connect(lambda: self._item_list.move_selected("down"))
        toolbar.addAction(move_down_action)
        delete_action = QAction(delete_icon(), "", self)
        delete_action.setToolTip("Delete Selected Item")
        delete_action.triggered.connect(self._delete_selected_item)
        toolbar.addAction(delete_action)
        return toolbar
    def _delete_selected_item(self) -> None:
        item_id = self._service_store.selected_item_id
        if item_id is None:
            return
        self._service_store.remove_item(item_id)
    def _toggle_show_hide(self) -> None:
        self._set_live(self._output_store.is_black)
    def _update_show_hide_button(self, is_black: bool) -> None:
        text = "Show" if is_black else "Hide"
        self._show_hide_action.setText(text)
        menu_action = getattr(self, "_show_hide_menu_action", None)
        if menu_action is not None:
            menu_action.setText(text)
    def _toggle_qr_code(self, checked: bool) -> None:
        self._qr_code_menu_action.setChecked(checked)
        self._qr_code_toolbar_action.setChecked(checked)
        self._output_window.qr_overlay.set_visible(checked)
        self._preview.qr_overlay.set_visible(checked)
    def _sync_aspect_ratio_selection(self, ratio: str) -> None:
        action = self._aspect_ratio_actions.get(ratio)
        if action is not None:
            action.setChecked(True)
        toolbar_action = self._aspect_ratio_toolbar_actions.get(ratio)
        if toolbar_action is not None:
            toolbar_action.setChecked(True)
    def _build_shortcuts(self) -> None:
        handlers = {
            "previous_slide": self._output_store.previous_slide,
            "next_slide": self._output_store.next_slide,
            "previous_item": self._output_store.previous_item,
            "next_item": self._output_store.next_item,
            "media_toggle": self._media_store.toggle,
            "toggle_show_hide": self._toggle_show_hide,
            "decrease_font": self._output_store.decrease_font_scale,
            "increase_font": self._output_store.increase_font_scale,
            "black_output": lambda: self._set_live(False),
            "toggle_recording": self._start_recording,
            "pause_recording": self._toggle_recording_pause,
            "show_hotkeys": self._show_hotkey_help,
        }
        self._shortcuts: dict[str, QShortcut] = {}
        for definition in HOTKEY_DEFINITIONS:
            shortcut = QShortcut(QKeySequence(), self)
            shortcut.activated.connect(handlers[definition.action_id])
            self._shortcuts[definition.action_id] = shortcut
        self._apply_hotkeys()
        self._settings_store.settings_changed.connect(self._on_hotkey_settings_changed)
        self._quick_add.input_focus_changed.connect(
            lambda focused: self._set_hotkeys_enabled(not focused)
        )

    def _apply_hotkeys(self) -> None:
        hotkeys = configured_hotkeys(self._settings_store.get("hotkeys", {}))
        for action_id, shortcut in self._shortcuts.items():
            shortcut.setKey(QKeySequence(hotkeys[action_id]))

    def _on_hotkey_settings_changed(self, _settings: dict) -> None:
        self._apply_hotkeys()

    def _set_hotkeys_enabled(self, enabled: bool) -> None:
        for shortcut in self._shortcuts.values():
            shortcut.setEnabled(enabled)

    def _show_hotkey_help(self) -> None:
        hotkeys = configured_hotkeys(self._settings_store.get("hotkeys", {}))
        lines = [
            f"{QKeySequence(hotkeys[item.action_id]).toString(QKeySequence.SequenceFormat.NativeText)}"
            f"    {item.label}"
            for item in HOTKEY_DEFINITIONS
        ]
        QMessageBox.information(self, "Current Keyboard Shortcuts", "\n".join(lines))

    def _toggle_recording_pause(self) -> None:
        if self._recording_store.state == "recording":
            self._recording_store.pause()
        elif self._recording_store.state == "paused":
            self._recording_store.resume()
    def _on_dirty_changed(self, dirty: bool) -> None:
        """Update window title to show unsaved changes indicator."""
        self._update_window_title()
    def _on_service_changed(self, _service: Service | None) -> None:
        """Update the title when the active service changes."""
        self._update_window_title()
    def _update_window_title(self) -> None:
        base_title = "JDP Presenter — Control"
        service = self._service_store.service
        if service is not None and service.name.strip():
            service_name = " ".join(service.name.split())
            base_title += f" — {service_name}"
        self.setWindowTitle(f"{base_title} *" if self._service_store.dirty else base_title)
    def _prompt_save_if_dirty(self) -> bool:
        """Prompt user to save if there are unsaved changes.
        Returns True if operation should continue (saved, discarded, or no changes),
        False if user cancelled.
        """
        if not self._service_store.dirty or self._service_store.service is None:
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "The current service has unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        elif reply == QMessageBox.StandardButton.Save:
            self._save_service()
            # If save was cancelled (e.g. user cancelled Save As dialog), don't continue
            return not self._service_store.dirty
        else:  # Discard
            return True
    def _new_service(self) -> None:
        if not self._prompt_save_if_dirty():
            return
        # Prompt for service name
        name, ok = QInputDialog.getText(self, "New Service", "Service name:", text="New Service")
        if not ok or not name.strip():
            return
        name = name.strip()
        service = Service(
            id=str(uuid.uuid4()),
            version="1.0",
            name=name,
            date=datetime.now().strftime("%Y-%m-%d"),
            theme=default_theme(),
            items=[],
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._service_store.set_service(service)
        self._current_service_path = None  # New service has no saved path yet
    def _add_text_item(self) -> None:
        if self._service_store.service is None:
            return
        content, ok = QInputDialog.getMultiLineText(self, "Add Text Item", "Slide content:")
        if not ok or not content:
            return
        self._service_store.add_item(
            TextItem(
                id=str(uuid.uuid4()),
                title=content.splitlines()[0][:40],
                content=content,
                slides=[Slide(id=str(uuid.uuid4()), content=content)],
            )
        )
    def _add_scripture_item(self) -> None:
        if self._service_store.service is None:
            return
        BibleBrowser(self._bible_store, self._service_store, parent=self).exec()
    def _add_song_item(self) -> None:
        if self._service_store.service is None:
            return
        SongBrowser(self._song_store, self._service_store, parent=self).exec()
    def _add_media_item(self) -> None:
        if self._service_store.service is None:
            return
        MediaBrowser(self._service_store, parent=self).exec()
    def _open_import_dialog(self) -> None:
        ImportDialog(self._bible_store, self._song_store, parent=self).exec()
    def _open_theme_editor(self) -> None:
        if self._service_store.service is None:
            return
        ThemeEditor(self._theme_store, parent=self).exec()
    def _open_theme_gallery(self) -> None:
        if self._service_store.service is None:
            return
        ThemeGallery(self._theme_store, parent=self).exec()
    def _open_service(self) -> None:
        if not self._prompt_save_if_dirty():
            return
        service_ids = service_repo.list_service_ids()
        if not service_ids:
            QMessageBox.information(self, "Open Service", "No saved services found in data/services/.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open Service", str(SERVICES_DIR), "*.json")
        if not path:
            return
        service_id = path.rsplit("/", 1)[-1].removesuffix(".json")
        self._service_store.set_service(service_repo.load_service_from_path(path))
        self.set_current_service_path(path)
    def _save_service(self) -> None:
        service = self._service_store.service
        if service is None:
            return
        service.updated_at = datetime.now(timezone.utc).isoformat()
        if self._current_service_path is None:
            self._save_service_as()
        else:
            service_repo.save_service_to_path(service, self._current_service_path)
            self._service_store.mark_saved()
    def _save_service_as(self) -> None:
        service = self._service_store.service
        if service is None:
            return
        service.updated_at = datetime.now(timezone.utc).isoformat()
        # Suggest a filename based on service name
        suggested_name = service.name.strip() or "New Service"
        # Sanitize filename
        import re
        suggested_name = re.sub(r'[<>:"/\\|?*]', '_', suggested_name)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Service As", str(SERVICES_DIR / f"{suggested_name}.json"), "*.json"
        )
        if not path:
            return
        service_repo.save_service_to_path(service, path)
        self.set_current_service_path(path)
        self._service_store.mark_saved()
    def _set_live(self, is_live: bool) -> None:
        self._output_store.set_live(is_live)
        self._output_store.set_black(not is_live)
    def _show_output_on_secondary(self) -> None:
        screens = QGuiApplication.screens()
        target = screens[1] if len(screens) > 1 else screens[0]
        self._display_store.set_target_screen(target)
        self._output_window.setGeometry(target.geometry())
        self._output_window.showFullScreen()
    def _open_export_dialog(self) -> None:
        if self._service_store.service is None:
            return
        ExportDialog(self._service_store.service, parent=self).exec()
    def _open_print_dialog(self) -> None:
        if self._service_store.service is None:
            return
        service = self._service_store.service
        dialog = QDialog(self)
        dialog.setWindowTitle("Print Service")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose print format:"))
        full_service_btn = QPushButton("Full Service")
        full_service_btn.clicked.connect(lambda: self._print_full_service(service, dialog))
        summary_btn = QPushButton("Summary")
        summary_btn.clicked.connect(lambda: self._print_summary(service, dialog))
        layout.addWidget(full_service_btn)
        layout.addWidget(summary_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(cancel_btn)
        dialog.exec()
    def _print_full_service(self, service: Service, dialog: QDialog) -> None:
        dialog.accept()
        QTimer.singleShot(0, lambda: self._show_print_preview(
            generate_full_markdown(service), "Full Service", "md"
        ))
    def _print_summary(self, service: Service, dialog: QDialog) -> None:
        dialog.accept()
        QTimer.singleShot(0, lambda: self._show_print_preview(
            generate_outline(service), "Summary", "txt"
        ))
    def _show_print_preview(self, text: str, title: str, suffix: str) -> None:
        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle(f"Print Preview — {title}")
        preview_dialog.resize(700, 500)
        layout = QVBoxLayout(preview_dialog)
        preview = QPlainTextEdit()
        preview.setPlainText(text)
        preview.setReadOnly(True)
        layout.addWidget(preview)
        button_row = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(text))
        save_btn = QPushButton("Save As…")
        save_btn.clicked.connect(lambda: self._save_print_output(text, suffix))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(preview_dialog.accept)
        button_row.addWidget(copy_btn)
        button_row.addWidget(save_btn)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)
        preview_dialog.exec()
    def _save_print_output(self, text: str, suffix: str) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Print Output", f"output.{suffix}", f"*.{suffix}"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
    def _open_settings_dialog(self) -> None:
        SettingsDialog(self._settings_store, parent=self).exec()
    # --- Recording handlers ---
    def _start_recording(self) -> None:
        if self._recording_store.is_active:
            self._stop_recording()
            return
        service = self._service_store.service
        schedule_name = service.name if service is not None else None
        prompt_for_options = bool(
            self._settings_store.get("recordingPromptForOptions", True)
        )
        if prompt_for_options:
            dialog = RecordingOptionsDialog(
                self._settings_store,
                self,
                default_name=schedule_name,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            file_name = dialog.file_name()
            fmt = dialog.format_name()
            quality = dialog.quality_name()
            ext = dialog.extension()
        else:
            fmt = self._settings_store.get("recordingFormat", DEFAULT_FORMAT)
            if fmt not in FORMATS:
                fmt = DEFAULT_FORMAT
            quality = self._settings_store.get("recordingQuality", DEFAULT_QUALITY)
            if quality not in QUALITIES:
                quality = DEFAULT_QUALITY
            file_name = default_recording_name(schedule_name)
            ext = FORMATS[fmt][2]
        # Use custom output directory from settings, or default
        output_dir = self._recording_store._get_recording_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        if not prompt_for_options and (output_dir / f"{file_name}.{ext}").exists():
            file_name = next_available_recording_name(output_dir, file_name, ext)
        path = str(output_dir / f"{file_name}.{ext}")
        self._recording_store.start(path, fmt, quality)
        self._record_toolbar_action.setIcon(stop_icon())
        self._record_toolbar_action.setText("Stop")
        self._recording_indicator.setVisible(True)
        self._recording_indicator.set_recording(True)
    def _stop_recording(self) -> None:
        self._recording_store.stop()
        # UI will be reset by _on_recording_state_changed when state becomes "idle"
    def _on_recording_state_changed(self, state: str) -> None:
        if state == "recording":
            self._recording_indicator.set_paused(False)
            self._recording_indicator.set_recording(True)
        elif state == "paused":
            self._recording_indicator.set_paused(True)
            self._recording_indicator.set_recording(True)
        elif state == "idle":
            self._recording_indicator.set_recording(False)
            self._recording_indicator.setVisible(False)
            self._record_toolbar_action.setIcon(record_icon())
            self._record_toolbar_action.setText("Record")
            # NOTE: the recordings list is refreshed in _on_recording_completed,
            # which fires only after any ffmpeg post-processing has finished.
    def _on_recording_completed(self, path: str, format_name: str) -> None:
        """Refresh the recordings list once the final file exists.
        For MP3 (ffmpeg-converted) recordings this fires after the temp WAV has
        been transcoded, so the new file is guaranteed to be on disk.
        """
        self._recordings_pane.refresh()

    def _on_conversion_failed(self, path: str, detail: str) -> None:
        """Tell the user where the temporary lossless capture was retained."""
        QMessageBox.warning(
            self,
            "Recording Conversion Failed",
            f"Could not convert the recording to the requested format.\n\n"
            f"Reason: {detail}\n\n"
            f"The lossless WAV capture remains in temporary storage at:\n{path}\n\n"
            "Install ffmpeg (or bundle tools/ffmpeg) to convert to MP3/M4A.",
        )
