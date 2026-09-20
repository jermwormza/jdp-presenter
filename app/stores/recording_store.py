"""RecordingStore: wraps PortAudio (via sounddevice) for audio-only recording.

Uses ``sounddevice``/PortAudio for capture instead of Qt Multimedia's
``QMediaRecorder``, because Qt 6's recorder exposes none of the pieces this
feature actually needs:

  * no real audio-level signal (Qt 6 removed ``QAudioProbe``), so a genuine VU
    meter is impossible from ``QMediaRecorder`` -- hence the old fake meter;
  * pause/resume under the FFmpeg backend is erratic (the crash you hit);
  * MP3 encoding isn't supported for live capture, hence the temp-WAV + ffmpeg
    workaround (which we keep for the final encode only).

With PortAudio we capture raw PCM directly, so we get a real-time VU level
(RMS averaged over the last second), reliable pause/resume, and an accurate
clock. MP3/M4A conversion is still done with ffmpeg after recording (reusing
the existing ``_ffmpeg_binary`` resolver), so the packaging/licensing story is
unchanged.

Public API (unchanged): signals ``state_changed`` / ``duration_changed`` /
``level_changed`` / ``recording_completed``, plus ``start``/``stop``/``pause``/
``resume`` and the ``is_active`` / ``state`` properties.
"""
from __future__ import annotations

import collections
import math
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtMultimedia import QMediaDevices, QMediaRecorder

# Kept as plain (codec-label, codec, extension) tuples so the
# recording-options dialog keeps working unchanged.
FORMATS: dict[str, tuple[str, str, str]] = {
    "MP3": ("MP3", "mp3", "mp3"),
    "WAV": ("WAV", "wav", "wav"),
    "AAC (M4A)": ("AAC", "aac", "m4a"),
}

# Reverse lookup kept for any external callers.
FORMAT_EXTENSIONS: dict[str, str] = {
    name: ext for name, (_codec, _sub, ext) in FORMATS.items()
}

# Qt quality enum values are retained for API compatibility (the settings
# dialog persists a quality *name*; we map that name to an ffmpeg bitrate
# below via CONVERT_BITRATES).
QUALITIES: dict[str, QMediaRecorder.Quality] = {
    "Low": QMediaRecorder.Quality.LowQuality,
    "Normal": QMediaRecorder.Quality.NormalQuality,
    "High": QMediaRecorder.Quality.HighQuality,
    "Very High": QMediaRecorder.Quality.VeryHighQuality,
}

# Target bitrate per quality name for the ffmpeg post-process step.
CONVERT_BITRATES: dict[str, str] = {
    "Low": "128k",
    "Normal": "192k",
    "High": "256k",
    "Very High": "320k",
}

# Path to a separately installed ffmpeg binary, used for converting the
# captured WAV to the requested format when it isn't WAV. Resolution order:
#   1. $JDP_FFMPEG (explicit override)
#   2. a copy placed next to the running executable
#   3. bare "ffmpeg" on the PATH
def _ffmpeg_binary() -> str:
    override = os.environ.get("JDP_FFMPEG")
    if override:
        return override

    candidates: list[Path] = []
    names = ["ffmpeg.exe"] if os.name == "nt" else ["ffmpeg"]

    exe_dir = Path(sys.executable).resolve().parent
    for n in names:
        candidates.append(exe_dir / n)
        candidates.append(exe_dir / "bin" / n)

    for cand in candidates:
        if cand.exists() and os.access(cand, os.X_OK):
            return str(cand)

    return "ffmpeg"


FFMPEG_BINARY = _ffmpeg_binary()

DEFAULT_FORMAT = "MP3"
DEFAULT_QUALITY = "Low"

_SAMPLE_RATE = 48000
_CHANNELS = 1
_LEVEL_WINDOW_S = 1.0
_RECORDING_TEMP_DIR = Path(tempfile.gettempdir()) / "jdp-presenter" / "recordings"


class RecordingStore(QObject):
    """PortAudio-backed audio recorder with a real-time VU monitor."""

    state_changed = Signal(str)           # "idle" | "recording" | "paused"
    duration_changed = Signal(int)        # milliseconds of recorded audio
    level_changed = Signal(float)         # 0.0-1.0, averaged RMS over last second
    recording_completed = Signal(str, str)  # (path, format_name)
    conversion_failed = Signal(str, str)  # (path, detail) — emitted when ffmpeg post-processing errors

    def __init__(self, settings_store=None, parent=None) -> None:
        super().__init__(parent)
        self._settings_store = settings_store

        # --- capture state ---
        self._state = "idle"
        self._stream = None
        self._samplerate = _SAMPLE_RATE
        self._recorded_frames = 0
        self._wave = None

        # float32 chunks (-1..1) captured by the PortAudio callback thread,
        # drained by the Qt main-thread UI timer.
        self._audio_buf = collections.deque(maxlen=512)
        self._level_lock = threading.Lock()
        # (timestamp, rms) samples for the rolling VU average.
        self._level_ring = collections.deque(maxlen=1024)

        # --- finalize / convert state ---
        self._pending_convert = False
        self._converting = False
        self._temp_path = None
        self._encoded_temp_path = None
        self._requested_path = None
        self._requested_format_name = None
        self._actual_format_name = None
        self._quality_name = None
        self._actual_file_path = None

        # Timer that drives the VU meter + clock on the main thread.
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(100)
        self._ui_timer.timeout.connect(self._on_ui_tick)

        # ffmpeg post-processing (MP3/M4A) -- async, reuses _ffmpeg_binary()
        # resolution so bundled .app/.exe builds work.
        self._converter = QProcess(self)
        self._converter.finished.connect(self._on_convert_finished)
        # A missing/broken ffmpeg binary must fail fast (and visibly), not hang
        # forever waiting for a subprocess that never produced output.
        self._converter.errorOccurred.connect(self._on_convert_error)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @property
    def is_active(self) -> bool:
        return self._state != "idle"

    @property
    def state(self) -> str:
        return self._state

    def start(self, path: str, format_name: str, quality_name: str) -> None:
        """Begin recording into the requested format/quality."""
        if self._state != "idle":
            self.stop()

        _file_format, _codec, requested_ext = FORMATS.get(
            format_name, FORMATS[DEFAULT_FORMAT]
        )
        target_path = self._ensure_extension(path, requested_ext)

        self._requested_path = target_path
        self._requested_format_name = format_name
        self._quality_name = quality_name

        # Reset per-take bookkeeping.
        self._recorded_frames = 0
        self._pending_convert = False
        self._converting = False
        self._temp_path = None
        self._encoded_temp_path = None
        self._actual_file_path = None
        self._level_ring.clear()
        with self._level_lock:
            self._audio_buf.clear()

        # Capture losslessly to a temp WAV; transcode to the requested
        # (non-WAV) format afterwards, or just rename for WAV.
        temp_path = self._make_temp_path(target_path, "wav", "capture")
        self._temp_path = temp_path
        self._actual_format_name = "WAV"

        # IMPORTANT: Query device sample rate BEFORE opening the WAV writer,
        # so the file header matches the actual capture rate. Otherwise the
        # recorded file plays back at the wrong speed (e.g. double speed if
        # device is 96 kHz but header says 48 kHz).
        self._samplerate = self._device_samplerate()
        self._open_writer(temp_path)

        self._stream = sd.InputStream(
            samplerate=self._samplerate,
            channels=_CHANNELS,
            dtype="float32",
            device=self._device_index(),
            callback=self._audio_callback,
        )
        self._stream.start()

        self._pending_convert = requested_ext != "wav"

        self._state = "recording"
        self._ui_timer.start()
        self.state_changed.emit("recording")

    def pause(self) -> None:
        """Pause capture (WAV writer stays open so resume can append)."""
        if self._state == "recording" and self._stream is not None:
            try:
                self._stream.stop()
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[recording] pause failed: {exc}")
            self._state = "paused"
            self.state_changed.emit("paused")

    def resume(self) -> None:
        """Resume capture after a pause."""
        if self._state == "paused" and self._stream is not None:
            try:
                self._stream.start()
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[recording] resume failed: {exc}")
            self._state = "recording"
            self.state_changed.emit("recording")

    def stop(self) -> None:
        """Stop capture, finalize the temp file, and convert if needed."""
        if self._state == "idle":
            return

        # Stop the PortAudio stream and the UI timer.
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:
                pass
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        self._ui_timer.stop()

        # Finalize the WAV capture.
        if self._wave is not None:
            try:
                self._wave.close()
            except Exception:
                pass
            self._wave = None

        self._state = "idle"
        self.state_changed.emit("idle")

        # Either transcode (MP3/M4A) or promote the temp WAV to final path.
        if self._pending_convert and self._temp_path:
            self._start_conversion()
        else:
            self._finalize_wav()

    # ------------------------------------------------------------------ #
    # Capture helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ensure_extension(path: str, ext: str) -> str:
        if ext and not path.lower().endswith(f".{ext}"):
            if "." in Path(path).name:
                return str(Path(path).with_suffix(f".{ext}"))
            return f"{path}.{ext}"
        return path

    @staticmethod
    def _make_temp_path(target_path: str, ext: str, purpose: str = "capture") -> str:
        stem = Path(target_path).stem
        _RECORDING_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        return str(
            _RECORDING_TEMP_DIR / f".{stem}.{uuid.uuid4().hex}.{purpose}.{ext}"
        )

    def _open_writer(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._wave = wave.open(path, "wb")
        self._wave.setnchannels(_CHANNELS)
        self._wave.setsampwidth(2)  # 16-bit PCM
        self._wave.setframerate(self._samplerate)

    @staticmethod
    def _rms_to_level(rms: float) -> float:
        """Map an RMS value (0..1) to a 0..1 VU reading (dB-style scale)."""
        if rms <= 1e-6:
            return 0.0
        db = 20.0 * math.log10(max(rms, 1e-6))
        # -60 dBFS -> 0%, 0 dBFS -> 100%, with a quiet noise floor near 0%.
        return max(0.0, min(1.0, (db + 60.0) / 60.0))

    def _device_index(self):
        """Resolve a PortAudio input device index from settings, else default."""
        raw = ""
        if self._settings_store is not None:
            raw = self._settings_store.get("audioInputDevice", "")
        if not raw:
            return sd.default.device[0]
        # The settings dialog stores a Qt AudioDevice id; map it to a PortAudio
        # index by matching the human-readable description.
        try:
            for dev in QMediaDevices.audioInputs():
                if dev.id().data().decode() == raw:
                    desc = dev.description()
                    for idx, info in enumerate(sd.query_devices()):
                        if (
                            info.get("max_input_channels", 0) > 0
                            and desc.lower() in str(info.get("name", "")).lower()
                        ):
                            return idx
                    break
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[recording] device lookup failed: {exc}")
        return sd.default.device[0]

    def _device_samplerate(self) -> int:
        try:
            idx = self._device_index()
            info = sd.query_devices(idx, "input")
            return int(round(info.get("default_samplerate")))
        except Exception:
            return _SAMPLE_RATE

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        """PortAudio real-time callback -- just enqueue the float32 samples."""
        try:
            chunk = indata.copy()
            with self._level_lock:
                self._audio_buf.append(chunk)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[recording] audio callback error: {exc}")

    def _on_ui_tick(self) -> None:
        """Main-thread tick: flush samples to the WAV, meter levels, tick clock."""
        with self._level_lock:
            chunks = list(self._audio_buf)
            self._audio_buf.clear()

        if chunks:
            data = np.concatenate(chunks, axis=0)        # (frames, channels)
            mono = data.mean(axis=1)                        # mix down to mono
            n = len(mono)
            if n and self._wave is not None:
                int16 = (np.clip(mono, -1.0, 1.0) * 32767.0).astype("<i2")
                self._wave.writeframes(int16.tobytes())

            self._recorded_frames += n
            rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2))) if n else 0.0

            now = time.monotonic()
            self._level_ring.append((now, rms))
            cutoff = now - _LEVEL_WINDOW_S
            while self._level_ring and self._level_ring[0][0] < cutoff:
                self._level_ring.popleft()

            if self._level_ring:
                avg_rms = sum(r for _, r in self._level_ring) / len(self._level_ring)
                level = self._rms_to_level(avg_rms)
            else:
                level = 0.0
            self.level_changed.emit(level)

            ms = int(self._recorded_frames / self._samplerate * 1000)
            self.duration_changed.emit(ms)
        else:
            # No new audio this tick. During a pause the VU reads quiet.
            if self._state == "paused":
                self.level_changed.emit(0.0)
            elif self._state == "idle":
                self._ui_timer.stop()

    # ------------------------------------------------------------------ #
    # Conversion (reuses the existing ffmpeg path)
    # ------------------------------------------------------------------ #
    def _finalize_wav(self) -> None:
        """Promote the temp WAV to its final location (WAV target)."""
        final = self._requested_path
        if self._temp_path and final:
            try:
                self._promote_completed_file(self._temp_path, final)
            except OSError as exc:
                self._conversion_failed(f"could not move finalized WAV: {exc}")
                return
        self._actual_file_path = final
        self._actual_format_name = "WAV"
        self._cleanup_temp()
        self._emit_completed(final or self._temp_path or "", "WAV")

    def _start_conversion(self) -> None:
        """Transcode the captured temp WAV to the requested final format."""
        if not self._temp_path or not self._requested_path:
            self._emit_completed(
                self._actual_file_path or self._requested_path or "",
                self._actual_format_name or DEFAULT_FORMAT,
            )
            return
        if not os.path.exists(self._temp_path):
            self._conversion_failed(f"capture file missing: {self._temp_path}")
            return

        bitrate = CONVERT_BITRATES.get(self._quality_name, "192k")
        ext = FORMATS.get(self._requested_format_name, FORMATS[DEFAULT_FORMAT])[2]
        if ext == "mp3":
            codec_args = ["-codec:a", "libmp3lame", "-b:a", bitrate]
        elif ext == "m4a":
            codec_args = ["-c:a", "aac", "-b:a", bitrate, "-f", "mp4"]
        else:  # WAV - handled by _finalize_wav, not reached here
            codec_args = []
        self._encoded_temp_path = self._make_temp_path(
            self._requested_path, ext, "encoded"
        )
        args = ["-y", "-i", self._temp_path, *codec_args, self._encoded_temp_path]

        self._converting = True
        self._converter.start(FFMPEG_BINARY, args)

    @property
    def ffmpeg_path(self) -> str:
        """The ffmpeg binary resolved at import time ('' if unset / not found)."""
        return FFMPEG_BINARY

    def _ffmpeg_available(self) -> bool:
        """True iff we think the configured ffmpeg binary can actually run.

        Uses the same resolver as the rest of the module, so when the binary is
        bundled (or overridden via ``JDP_FFMPEG``) it is found; otherwise falls
        back to a PATH lookup and reports whether that succeeded.
        """
        if not FFMPEG_BINARY or FFMPEG_BINARY == "ffmpeg":
            return shutil.which("ffmpeg") is not None
        try:
            return Path(FFMPEG_BINARY).exists()
        except OSError:
            return False

    def _on_convert_error(self, error) -> None:
        """QProcess failed to even start (e.g. binary missing) — fail fast + visibly."""
        self._converting = False
        detail = f"could not start ffmpeg ({error.name if hasattr(error, 'name') else error})"
        self._conversion_failed(detail)

    def _on_convert_finished(self, exit_code: int, _exit_status) -> None:
        if not self._converting:
            return
        self._converting = False
        if (
            exit_code == 0
            and self._encoded_temp_path
            and self._requested_path
            and os.path.exists(self._encoded_temp_path)
        ):
            try:
                self._promote_completed_file(
                    self._encoded_temp_path, self._requested_path
                )
            except OSError as exc:
                self._conversion_failed(f"could not move encoded recording: {exc}")
                return
            self._cleanup_temp()
            self._emit_completed(
                self._requested_path, self._requested_format_name or DEFAULT_FORMAT
            )
        else:
            err = bytes(self._converter.readAllStandardError()).decode(errors="replace")
            self._conversion_failed(err.strip() or f"ffmpeg exited with code {exit_code}")

    def _conversion_failed(self, detail: str) -> None:
        """Keep the lossless capture in temporary storage for recovery."""
        kept = None
        if self._temp_path and os.path.exists(self._temp_path):
            kept = self._temp_path
        self._cleanup_temp(keep_capture=True)
        self._emit_completed(kept or self._requested_path or "", "WAV")
        print(f"[recording] ffmpeg conversion failed ({detail}); kept {kept}")
        self.conversion_failed.emit(kept or self._requested_path or "", detail)

    @staticmethod
    def _promote_completed_file(source_path: str, destination_path: str) -> None:
        """Move a completed file, staging cross-volume copies before final rename."""
        source = Path(source_path)
        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(source, destination)
            return
        except OSError:
            staging = destination.with_name(
                f".{destination.name}.{uuid.uuid4().hex}.moving"
            )

        try:
            shutil.copy2(source, staging)
            os.replace(staging, destination)
            source.unlink()
        except OSError:
            staging.unlink(missing_ok=True)
            raise

    def _cleanup_temp(self, keep_capture: bool = False) -> None:
        if self._temp_path and os.path.exists(self._temp_path) and not keep_capture:
            try:
                os.remove(self._temp_path)
            except OSError:
                pass
        if self._encoded_temp_path and os.path.exists(self._encoded_temp_path):
            try:
                os.remove(self._encoded_temp_path)
            except OSError:
                pass
        self._temp_path = None
        self._encoded_temp_path = None
        self._pending_convert = False

    def _emit_completed(self, path: str, format_name: str) -> None:
        self._pending_convert = False
        self._converting = False
        self.recording_completed.emit(path, format_name)

    # ------------------------------------------------------------------ #
    # Output directory (used by the control window when building the path)
    # ------------------------------------------------------------------ #
    def _get_recording_output_dir(self) -> Path:
        """Get the configured recording output directory or default."""
        if self._settings_store is not None:
            custom_dir = self._settings_store.get("recordingOutputDir", "")
            if custom_dir:
                return Path(custom_dir)
        from app.persistence.paths import RECORDINGS_DIR
        return RECORDINGS_DIR
