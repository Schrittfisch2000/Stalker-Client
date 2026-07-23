from __future__ import annotations

import unittest

from app.safari_hls_fix import _duration_from_item


class VodDurationTests(unittest.TestCase):
    def test_duration_uses_seconds_from_portal_metadata(self) -> None:
        self.assertEqual(_duration_from_item({"duration": 5_400}), 5_400)

    def test_duration_parses_hour_timecode(self) -> None:
        self.assertEqual(_duration_from_item({"time": "01:32:15"}), 5_535)

    def test_duration_converts_portal_minutes(self) -> None:
        self.assertEqual(_duration_from_item({"time": 135}), 8_100)

    def test_duration_ignores_portal_boolean_time_field(self) -> None:
        self.assertIsNone(_duration_from_item({"time": 1}))


if __name__ == "__main__":
    unittest.main()
