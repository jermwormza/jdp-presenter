"""macOS-only: registers the app as a Now Playing target so hardware Play/Pause/Toggle media keys
are routed to us via MPRemoteCommandCenter, instead of being intercepted by Control Center for
whichever app macOS currently thinks is "now playing" (usually not us, since Qt has no built-in
integration with this API).

Safe to import/call on any platform: everything is guarded behind a top-level try/except so
non-macOS platforms (or a macOS venv missing the optional pyobjc packages) silently no-op.
"""
from __future__ import annotations

import sys

_available = False

if sys.platform == "darwin":
    try:
        from MediaPlayer import (
            MPMusicPlaybackStatePaused,
            MPMusicPlaybackStatePlaying,
            MPNowPlayingInfoCenter,
            MPRemoteCommandCenter,
            MPRemoteCommandHandlerStatusNoActionableNowPlayingItem,
            MPRemoteCommandHandlerStatusSuccess,
        )

        _available = True
    except ImportError:
        _available = False


def is_available() -> bool:
    return _available


class MacNowPlayingIntegration:
    """Wires MPRemoteCommandCenter's play/pause/toggle commands to a MediaPlayerStore."""

    def __init__(self, media_store) -> None:
        self._media_store = media_store
        self._handlers: list = []  # keep references alive; PyObjC blocks can be GC'd otherwise
        if not _available:
            return

        center = MPRemoteCommandCenter.sharedCommandCenter()

        def _make_handler(action):
            def handler(_event):
                # Same guard as the transport toolbar button's enabled state: a no-op with no
                # active media, rather than driving the underlying QMediaPlayer regardless.
                if media_store.active_item is None:
                    return MPRemoteCommandHandlerStatusNoActionableNowPlayingItem
                action()
                return MPRemoteCommandHandlerStatusSuccess

            return handler

        play_handler = _make_handler(media_store.play)
        pause_handler = _make_handler(media_store.pause)
        toggle_handler = _make_handler(media_store.toggle)
        self._handlers = [play_handler, pause_handler, toggle_handler]

        center.playCommand().setEnabled_(True)
        center.playCommand().addTargetWithHandler_(play_handler)
        center.pauseCommand().setEnabled_(True)
        center.pauseCommand().addTargetWithHandler_(pause_handler)
        center.togglePlayPauseCommand().setEnabled_(True)
        center.togglePlayPauseCommand().addTargetWithHandler_(toggle_handler)

        media_store.active_changed.connect(self._on_active_changed)
        media_store.playing_changed.connect(self._on_playing_changed)
        self._on_active_changed(media_store.active_item)

    def _on_active_changed(self, item) -> None:
        if not _available:
            return
        info_center = MPNowPlayingInfoCenter.defaultCenter()
        if item is None:
            info_center.setNowPlayingInfo_(None)
            info_center.setPlaybackState_(MPMusicPlaybackStatePaused)
            return
        info_center.setNowPlayingInfo_({"title": item.title or "JDP Presenter"})
        # Proactively report "paused" the moment media becomes available (even though nothing is
        # playing yet) — macOS only routes hardware media keys to apps with a definitive playback
        # state; leaving it "Unknown" until the first real play() call means the very first key
        # press (the one that's supposed to start playback) never arrives.
        if not self._media_store.is_playing():
            info_center.setPlaybackState_(MPMusicPlaybackStatePaused)

    def _on_playing_changed(self, is_playing: bool) -> None:
        if not _available:
            return
        state = MPMusicPlaybackStatePlaying if is_playing else MPMusicPlaybackStatePaused
        MPNowPlayingInfoCenter.defaultCenter().setPlaybackState_(state)
