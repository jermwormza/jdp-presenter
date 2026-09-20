"""MediaPlayerStore: drives audio/video playback for VideoItem/AudioItem service items.

Whichever of the current or next service item is a media item is treated as "active": if the
current item is media, it plays with audio+video mirrored into both the Output window and the
Control window's current-item preview; otherwise, if the next item is media, it plays as
background audio (with video, if any, monitorable only in the Next Item preview) while the
current item continues to display normally on Output.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from app.models.service import AudioItem, VideoItem
from app.stores.output_store import OutputStore
from app.stores.service_store import ServiceStore
from app.utils.media_paths import resolve_media_path

_MEDIA_TYPES = (VideoItem, AudioItem)


def apply_video_scale_mode(video_widget, scale_mode: str) -> None:
    """Map our aspect-preserving scale_mode onto QVideoWidget's more limited aspectRatioMode.

    Qt only offers "contain" (KeepAspectRatio) and "cover, cropping as needed"
    (KeepAspectRatioByExpanding) for live video; "original" and the fill_width/fill_height
    distinction are approximated as contain/cover respectively (true per-pixel/unscaled control
    would require a custom compositor, out of scope here).
    """
    if scale_mode in ("fill_width", "fill_height"):
        video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
    else:
        video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)


class MediaPlayerStore(QObject):
    playing_changed = Signal(bool)
    position_changed = Signal(int)  # milliseconds
    duration_changed = Signal(int)  # milliseconds
    active_changed = Signal(object)  # ServiceItem | None

    def __init__(self, service_store: ServiceStore, output_store: OutputStore, parent=None) -> None:
        super().__init__(parent)
        self._service_store = service_store
        self._output_store = output_store

        self._primary = QMediaPlayer(self)
        self._primary_audio = QAudioOutput(self)
        self._primary.setAudioOutput(self._primary_audio)
        self._mirror = QMediaPlayer(self)  # muted; only used to mirror a CURRENT video into Preview

        self._active_item = None
        self._active_target: str | None = None
        self._loaded_path: str | None = None
        self._output_widget = None
        self._current_preview_widget = None
        self._next_preview_widget = None
        self._kick_generation = 0
        self._kick_prev_volume = 1.0   # store volume before registration kick
        self._kick_prev_muted = False  # store mute state before registration kick
        self._kick_active_path: str | None = None  # track which media we already kicked for

        self._primary.playingChanged.connect(self.playing_changed.emit)
        self._primary.positionChanged.connect(lambda ms: self.position_changed.emit(int(ms)))
        self._primary.durationChanged.connect(lambda ms: self.duration_changed.emit(int(ms)))

        service_store.service_changed.connect(self._resync)
        output_store.position_changed.connect(self._resync)
        self._resync()

    @property
    def active_item(self):
        return self._active_item

    @property
    def active_target(self) -> str | None:
        """'current' if the live item itself is media, 'next' for background playback, else None."""
        return self._active_target

    def set_video_widgets(self, output_widget, current_preview_widget, next_preview_widget) -> None:
        """Wire the three video-capable widgets once all windows exist.

        The mirror player always targets the current-item preview widget (only ever loaded when
        the current item itself is media). The primary player's video output is switched between
        the Output window and the Next Item preview depending on which item is actually active.
        """
        self._output_widget = output_widget
        self._current_preview_widget = current_preview_widget
        self._next_preview_widget = next_preview_widget
        self._mirror.setVideoOutput(current_preview_widget)
        self._apply_primary_video_target()

    def _apply_primary_video_target(self) -> None:
        if self._output_widget is None:
            return  # widgets not wired yet
        if self._active_target == "current":
            self._primary.setVideoOutput(self._output_widget)
        elif self._active_target == "next":
            self._primary.setVideoOutput(self._next_preview_widget)
        else:
            self._primary.setVideoOutput(self._output_widget)

    def is_playing(self) -> bool:
        return self._primary.isPlaying()

    def position(self) -> int:
        return self._primary.position()

    def duration(self) -> int:
        return self._primary.duration()

    def play(self) -> None:
        self._cancel_registration_kick()
        self._primary.play()
        if self._mirror.source().isValid():
            self._mirror.play()

    def pause(self) -> None:
        self._cancel_registration_kick()
        self._primary.pause()
        self._mirror.pause()

    def stop(self) -> None:
        self._cancel_registration_kick()
        self._primary.stop()
        self._mirror.stop()

    def _cancel_registration_kick(self) -> None:
        """Invalidate any pending kick timer and restore previous volume/mute."""
        self._kick_generation += 1
        self._primary_audio.setMuted(self._kick_prev_muted)
        self._primary_audio.setVolume(self._kick_prev_volume)

    def toggle(self) -> None:
        self.pause() if self.is_playing() else self.play()

    def seek(self, position_ms: int) -> None:
        self._primary.setPosition(position_ms)
        if self._mirror.source().isValid():
            self._mirror.setPosition(position_ms)

    def _resolve_active(self):
        service = self._service_store.service
        if service is None or not service.items:
            return None, None
        current = self._output_store.current_item()
        if isinstance(current, _MEDIA_TYPES):
            return current, "current"
        next_index = self._output_store.item_index + 1
        if next_index < len(service.items):
            candidate = service.items[next_index]
            if isinstance(candidate, _MEDIA_TYPES):
                return candidate, "next"
        return None, None

    def _resync(self, *_args) -> None:
        item, target = self._resolve_active()
        if item is self._active_item and target == self._active_target:
            return
        self._active_item = item
        self._active_target = target
        self.active_changed.emit(item)
        self._apply_primary_video_target()

        if item is None:
            self._primary.stop()
            self._mirror.stop()
            self._mirror.setSource(QUrl())
            self._loaded_path = None
            self._kick_active_path = None  # reset so next media item will kick
            return

        self._primary.setLoops(QMediaPlayer.Loops.Infinite if item.loop else QMediaPlayer.Loops.Once)
        resolved = resolve_media_path(item.path)
        if resolved != self._loaded_path:
            self._loaded_path = resolved
            self._primary.setSource(QUrl.fromLocalFile(resolved))

        if target == "current" and isinstance(item, VideoItem):
            if self._mirror.source().toLocalFile() != resolved:
                self._mirror.setSource(QUrl.fromLocalFile(resolved))
        else:
            self._mirror.stop()
            self._mirror.setSource(QUrl())

        # Never auto-play, whether the media item is current or queued as next — the operator
        # always starts playback explicitly via the transport toolbar/media keys.

        # Kick playback on (silent), then pause it shortly after (not same-tick) — macOS's hardware
        # media key routing is driven largely by which app has ACTUALLY produced audio through
        # CoreAudio, not just by MPNowPlayingInfoCenter metadata. An instant play()+pause() on the
        # same tick may never let the audio engine actually start; setting volume to 0 first means
        # this never produces any audible sound even though it briefly opens a real audio route.
        # Save current volume/mute BEFORE silencing, so we can restore it after the kick.
        # Only kick if this is a NEW media item we haven't registered yet.
        if self._kick_active_path != item.path:
            self._kick_active_path = item.path
            self._kick_prev_volume = self._primary_audio.volume()
            self._kick_prev_muted = self._primary_audio.isMuted()
            # Belt-and-suspenders: both volume=0 and mute=True
            self._primary_audio.setVolume(0.0)
            self._primary_audio.setMuted(True)
            # Give the audio engine time to process the volume/mute change
            QTimer.singleShot(50, lambda: self._start_registration_kick())

    def _start_registration_kick(self) -> None:
        """Start the actual kick after volume=0/mute has taken effect."""
        self._primary.play()
        # Also kick the mirror player so the preview shows the first frame
        if self._mirror.source().isValid():
            self._mirror.play()
        self._kick_generation += 1
        generation = self._kick_generation
        QTimer.singleShot(250, lambda: self._end_registration_kick(generation))

    def _end_registration_kick(self, generation: int) -> None:
        if generation != self._kick_generation:
            return  # a newer item became active before this kick's timer fired; ignore it
        self._primary.pause()
        self._primary.setPosition(0)  # rewind to beginning after registration kick
        self._mirror.pause()
        self._mirror.setPosition(0)
        self._primary_audio.setMuted(self._kick_prev_muted)
        self._primary_audio.setVolume(self._kick_prev_volume)
