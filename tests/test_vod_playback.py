from __future__ import annotations

import unittest
from pathlib import Path

from app.safari_hls_fix import _duration_from_item, _play_response


class VodDurationTests(unittest.TestCase):
    def test_duration_uses_seconds_from_portal_metadata(self) -> None:
        self.assertEqual(_duration_from_item({"duration": 5_400}), 5_400)

    def test_duration_parses_hour_timecode(self) -> None:
        self.assertEqual(_duration_from_item({"time": "01:32:15"}), 5_535)

    def test_duration_converts_portal_minutes(self) -> None:
        self.assertEqual(_duration_from_item({"time": 135}), 8_100)

    def test_duration_ignores_portal_boolean_time_field(self) -> None:
        self.assertIsNone(_duration_from_item({"time": 1}))

    def test_play_response_matches_registered_string_response_model(self) -> None:
        response = _play_response("/hls/ticket/index.m3u8", 7_260, True)

        self.assertEqual(response["duration"], "7260.000")
        self.assertEqual(response["seekable"], "true")
        self.assertTrue(all(isinstance(value, str) for value in response.values()))

    def test_play_response_marks_unknown_duration_as_not_seekable(self) -> None:
        response = _play_response("/hls/ticket/index.m3u8", None, False)

        self.assertEqual(response["duration"], "")
        self.assertEqual(response["seekable"], "false")

    def test_browser_removes_native_controls_for_seekable_vod(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app/static/vod-controls.js"
        ).read_text(encoding="utf-8")

        self.assertIn("video.toggleAttribute('controls', !customControls)", source)
        self.assertIn("duration > 0 && seekable", source)


if __name__ == "__main__":
    unittest.main()
