from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.windows.control_window import ControlWindow


class MediaScrubbingTests(unittest.TestCase):
    def _window_stub(self, *, playing: bool, position: int = 2500):
        media_store = Mock()
        media_store.is_playing.return_value = playing
        slider = Mock()
        slider.value.return_value = position
        slider.isSliderDown.return_value = True
        return SimpleNamespace(
            _media_store=media_store,
            _media_seek_slider=slider,
            _resume_media_after_scrub=False,
        )

    def test_scrubbing_pauses_seeks_continuously_and_resumes_playback(self) -> None:
        window = self._window_stub(playing=True)

        ControlWindow._on_media_scrub_started(window)
        ControlWindow._on_media_scrubbed(window, 4000)
        window._media_seek_slider.value.return_value = 4500
        ControlWindow._on_media_scrub_finished(window)

        window._media_store.pause.assert_called_once_with()
        self.assertEqual(
            window._media_store.seek.call_args_list,
            [unittest.mock.call(2500), unittest.mock.call(4000), unittest.mock.call(4500)],
        )
        window._media_store.play.assert_called_once_with()

    def test_scrubbing_paused_video_does_not_start_playback(self) -> None:
        window = self._window_stub(playing=False)

        ControlWindow._on_media_scrub_started(window)
        ControlWindow._on_media_scrub_finished(window)

        window._media_store.pause.assert_not_called()
        window._media_store.play.assert_not_called()

    def test_recording_pause_shortcut_toggles_pause_and_resume(self) -> None:
        recording_store = Mock()
        recording_store.state = "recording"
        window = SimpleNamespace(_recording_store=recording_store)

        ControlWindow._toggle_recording_pause(window)
        recording_store.pause.assert_called_once_with()

        recording_store.state = "paused"
        ControlWindow._toggle_recording_pause(window)
        recording_store.resume.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()