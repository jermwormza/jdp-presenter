"""Entry point: creates shared stores and the two native windows.

Uses an early splash screen to mask PyInstaller cold-start latency (~15s).
On macOS, the splash requires the event loop to be running, so we start it
immediately and do heavy initialization via QTimer.singleShot.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# ─── 1. Create QApplication + Splash IMMEDIATELY (before any heavy imports) ───
from PySide6.QtWidgets import QApplication, QMessageBox

app = QApplication(sys.argv)
app.setApplicationName("JDP Presenter")
app.setOrganizationName("JDP")
app.setQuitOnLastWindowClosed(False)

from app.utils.app_style import install_system_theme

install_system_theme(app)

# Redirect stdout/stderr to a log file for .app bundle / frozen-exe debugging.
# The destination is platform-specific: macOS uses ~/Library/Logs, Windows uses
# %LOCALAPPDATA%, Linux uses ~/.local/share.
if getattr(sys, 'frozen', False):
    if sys.platform == "darwin":
        log_dir = os.path.join(os.path.expanduser("~"), "Library", "Logs", "JDP Presenter")
    elif sys.platform == "win32":
        log_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "JDP Presenter", "Logs"
        )
    else:
        log_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "JDP Presenter", "Logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")
    log_file = open(log_path, "a", buffering=1)  # line-buffered
    sys.stdout = log_file
    sys.stderr = log_file
    print(f"[MAIN] Log file: {log_path}", flush=True)

# Import splash AFTER QApplication exists
from app.utils.splash import create_splash

splash = create_splash(app)
splash.show_message("Loading UI modules…")

# ─── 2. Heavy imports (PySide6 stores, widgets, etc.) ───
from PySide6.QtCore import Qt, QTimer

from app.persistence import service_repo
from app.persistence.library_package import (
    bootstrap_starter_library,
    convert_legacy_library,
    detect_legacy_library,
    replace_with_starter_library,
)
from app.server import remote_server
from app.server.bridge import remote_bridge
from app.stores.bible_store import BibleStore
from app.stores.display_store import DisplayStore
from app.stores.media_store import MediaPlayerStore
from app.stores.output_store import OutputStore
from app.stores.recording_store import RecordingStore
from app.stores.recording_store import DEFAULT_FORMAT, DEFAULT_QUALITY, FORMATS
from app.stores.service_store import ServiceStore
from app.stores.settings_store import SettingsStore
from app.stores.song_store import SongStore
from app.stores.theme_store import ThemeStore
from app.utils import canvas as canvas_util
from app.utils.mac_now_playing import MacNowPlayingIntegration
from app.utils.pagination import paginate_item
from app.utils.theme_utils import merge_theme
from app.utils.window_state import restore_geometry
from app.widgets.recording_options_dialog import default_recording_name
from app.windows.control_window import ControlWindow
from app.windows.output_window import OutputWindow


def _load_initial_service(
    service_store: ServiceStore,
    settings_store: SettingsStore,
) -> str | None:
    remembered_path = settings_store.get("lastServicePath", "")
    if isinstance(remembered_path, str) and remembered_path:
        path = Path(remembered_path)
        if path.is_file():
            try:
                service_store.set_service(service_repo.load_service_from_path(path))
                return str(path)
            except (OSError, ValueError, KeyError):
                print(f"[INIT] Could not restore service: {path}", flush=True)

    service_ids = service_repo.list_service_ids()
    if service_ids:
        service_id = service_ids[0]
        service_store.set_service(service_repo.load_service(service_id))
        return str(service_repo.SERVICES_DIR / f"{service_id}.json")
    return None


def _wire_remote_control(
    service_store: ServiceStore,
    output_store: OutputStore,
    media_store: MediaPlayerStore,
    recording_store: RecordingStore,
    settings_store: SettingsStore,
) -> None:
    def start_remote_recording() -> None:
        service = service_store.service
        name = default_recording_name(service.name if service is not None else None)
        format_name = settings_store.get("recordingFormat", DEFAULT_FORMAT)
        quality_name = settings_store.get("recordingQuality", DEFAULT_QUALITY)
        if format_name not in FORMATS:
            format_name = DEFAULT_FORMAT
        extension = FORMATS[format_name][2]
        output_dir = recording_store._get_recording_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{name}.{extension}"
        suffix = 1
        while path.exists():
            path = output_dir / f"{name}_{suffix:03d}.{extension}"
            suffix += 1
        recording_store.start(str(path), format_name, quality_name)

    def handle_command(command: str) -> None:
        if command in {"next", "prev", "toggle_live", "toggle_black"}:
            output_store.handle_remote_command(command)
        elif command == "media_play":
            media_store.play()
        elif command == "media_pause":
            media_store.pause()
        elif command == "media_stop":
            media_store.stop()
        elif command == "recording_start" and not recording_store.is_active:
            start_remote_recording()
        elif command == "recording_pause" and recording_store.state == "recording":
            recording_store.pause()
        elif command == "recording_resume" and recording_store.state == "paused":
            recording_store.resume()
        elif command == "recording_stop":
            recording_store.stop()

    remote_bridge.command_received.connect(handle_command, Qt.ConnectionType.QueuedConnection)

    def broadcast(*_args) -> None:
        item = output_store.current_item()
        service = service_store.service
        next_item = None
        next_pages = [""]
        if service is not None and output_store.item_index + 1 < len(service.items):
            next_item = service.items[output_store.item_index + 1]
            next_theme = merge_theme(service.theme, next_item.display_settings)
            next_pages = paginate_item(
                next_item,
                next_theme,
                output_store.canvas_size(),
                output_store.font_scale,
            ) or [""]
        theme = merge_theme(service.theme, item.display_settings) if service and item else None
        next_theme = (
            merge_theme(service.theme, next_item.display_settings) if service and next_item else None
        )
        remote_server.broadcast_state(
            {
                "title": item.title if item else "",
                "next_title": next_item.title if next_item else "",
                "slide_index": output_store.slide_index,
                "total_slides": len(output_store.current_pages()),
                "current_text": output_store.current_page_text(),
                "next_text": next_pages[0],
                "current_type": item.type if item else "",
                "next_type": next_item.type if next_item else "",
                "current_background": theme.background.color if theme else "#000000",
                "next_background": next_theme.background.color if next_theme else "#000000",
                "current_color": (
                    theme.song.lyrics.color if item and item.type == "song" else theme.scripture.verse_text.color
                ) if theme else "#ffffff",
                "next_color": (
                    next_theme.song.lyrics.color
                    if next_item and next_item.type == "song"
                    else next_theme.scripture.verse_text.color
                ) if next_theme else "#ffffff",
                "is_live": output_store.is_live,
                "is_black": output_store.is_black,
                "media_active": media_store.active_item is not None,
                "media_playing": media_store.is_playing(),
                "recording_state": recording_store.state,
            }
        )

    output_store.position_changed.connect(broadcast)
    output_store.is_live_changed.connect(broadcast)
    output_store.is_black_changed.connect(broadcast)
    service_store.service_changed.connect(broadcast)
    media_store.active_changed.connect(broadcast)
    media_store.playing_changed.connect(broadcast)
    recording_store.state_changed.connect(broadcast)
    broadcast()
    remote_server.start_server()


def _restore_output_preferences(output_store: OutputStore, settings_store: SettingsStore) -> None:
    output_store.set_canvas_ratio(settings_store.get("canvasRatio", canvas_util.DEFAULT_CANVAS_RATIO))
    output_store.set_font_scale(settings_store.get("fontScale", 1.0))
    output_store.canvas_changed.connect(lambda ratio: settings_store.set("canvasRatio", ratio))
    output_store.font_scale_changed.connect(lambda scale: settings_store.set("fontScale", scale))


def _prepare_libraries_for_startup(splash: 'SplashScreen') -> bool:
    """Handle legacy-library upgrades before any repository opens its database."""
    legacy = detect_legacy_library()
    if not legacy.requires_decision:
        seeded = bootstrap_starter_library()
        if seeded.songs or seeded.bibles:
            print(
                f"[INIT] Imported starter library: {seeded.songs} songs, {seeded.bibles} Bibles",
                flush=True,
            )
        return True

    prompt = QMessageBox(splash)
    prompt.setWindowTitle("Upgrade Libraries")
    prompt.setIcon(QMessageBox.Icon.Question)
    prompt.setText("An existing JDP Presenter library was found.")
    prompt.setInformativeText(
        f"Found approximately {legacy.songs} song file(s) and {legacy.bibles} Bible(s).\n\n"
        "Convert Existing keeps your current library and imports it into the new database format. "
        "Use Packaged Library replaces the active library with the one included in this installer.\n\n"
        "Your existing files and application settings will be retained either way. The next step "
        "may take several minutes; keep JDP Presenter open until the main window appears."
    )
    convert_button = prompt.addButton("Convert Existing", QMessageBox.ButtonRole.AcceptRole)
    replace_button = prompt.addButton("Use Packaged Library", QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = prompt.addButton(QMessageBox.StandardButton.Cancel)
    prompt.setDefaultButton(convert_button)
    prompt.exec()
    clicked = prompt.clickedButton()
    if clicked == cancel_button:
        QApplication.instance().quit()
        return False

    splash.raise_()
    splash.start_progress(
        "Converting libraries - please keep JDP Presenter open…"
        if clicked == convert_button
        else "Installing packaged libraries - please keep JDP Presenter open…"
    )
    QApplication.processEvents()
    if clicked == convert_button:
        summary = convert_legacy_library()
        action = "Converted existing library"
    elif clicked == replace_button:
        summary = replace_with_starter_library()
        action = "Installed packaged library"
    else:
        QApplication.instance().quit()
        return False
    splash.stop_progress()
    print(f"[INIT] {action}: {summary.songs} songs, {summary.bibles} Bibles", flush=True)
    return True


# Global references to prevent GC
_control_window = None
_output_window = None


def _initialize_and_show(splash: 'SplashScreen') -> None:
    """Initialize all stores, windows, and wiring. Called after event loop starts."""
    try:
        _do_initialize_and_show(splash)
    except Exception:
        # Never die silently: log the full traceback and surface it to the user.
        import traceback
        traceback.print_exc()
        try:
            splash.hide()
        except Exception:
            pass
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "JDP Presenter — Startup Error", traceback.format_exc())
        QApplication.instance().quit()


def _do_initialize_and_show(splash: 'SplashScreen') -> None:
    """All heavy init, wrapped by _initialize_and_show so startup failures stay visible."""
    global _control_window, _output_window

    print("[INIT] Starting initialization", flush=True)
    splash.show_message("Initializing stores…")

    service_store = ServiceStore()
    display_store = DisplayStore()
    output_store = OutputStore(service_store)
    media_store = MediaPlayerStore(service_store, output_store)
    settings_store = SettingsStore()
    recording_store = RecordingStore(settings_store)
    bible_store = BibleStore(settings_store)
    song_store = SongStore()
    theme_store = ThemeStore(service_store)

    print("[INIT] Stores created", flush=True)
    splash.show_message("Preparing libraries…")
    if not _prepare_libraries_for_startup(splash):
        return
    splash.show_message("Creating windows…")

    output_window = OutputWindow(service_store, output_store, media_store)
    control_window = ControlWindow(
        service_store,
        display_store,
        output_store,
        media_store,
        recording_store,
        bible_store,
        song_store,
        theme_store,
        settings_store,
        output_window,
    )
    media_store.set_video_widgets(
        output_window.video_widget, control_window.preview_video_widget, control_window.next_preview_video_widget
    )
    now_playing_integration = MacNowPlayingIntegration(media_store)  # noqa: F841 (keeps PyObjC targets alive)

    _control_window = control_window
    _output_window = output_window

    print("[INIT] Windows created", flush=True)
    splash.show_message("Wiring remote control…")
    _wire_remote_control(
        service_store,
        output_store,
        media_store,
        recording_store,
        settings_store,
    )

    splash.show_message("Restoring preferences…")
    _restore_output_preferences(output_store, settings_store)

    splash.show_message("Restoring service…")
    control_window.set_current_service_path(_load_initial_service(service_store, settings_store))

    restore_geometry(control_window, settings_store.get("controlWindowGeometry"))
    restore_geometry(output_window, settings_store.get("outputWindowGeometry"))
    control_window.restore_layout(
        settings_store.get("controlMainSplitterState"),
        settings_store.get("controlPreviewSplitterState"),
    )

    print("[MAIN] About to show control_window", flush=True)
    control_window.show()
    print(f"[MAIN] control_window visible: {control_window.isVisible()}, geometry: {control_window.geometry()}", flush=True)
    
    print("[MAIN] About to show output_window", flush=True)
    output_window.show()
    print(f"[MAIN] output_window visible: {output_window.isVisible()}, geometry: {output_window.geometry()}", flush=True)

    app.setQuitOnLastWindowClosed(True)
    splash.finish_loading(control_window)
    QTimer.singleShot(1500, control_window.check_for_updates_on_startup)
    print("[INIT] Done", flush=True)


def main() -> int:
    # Defer heavy initialization until event loop is running (so splash is visible on macOS)
    QTimer.singleShot(0, lambda: _initialize_and_show(splash))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
