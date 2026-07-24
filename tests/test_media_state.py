from __future__ import annotations

import unittest

from app.media_state import WATCHED_THRESHOLD, _is_finished


class MediaProgressTests(unittest.TestCase):
    def test_watched_threshold_is_ninety_percent(self) -> None:
        self.assertEqual(WATCHED_THRESHOLD, 0.9)
        self.assertFalse(_is_finished(899, 1000))
        self.assertTrue(_is_finished(900, 1000))

    def test_unknown_duration_is_not_marked_watched(self) -> None:
        self.assertFalse(_is_finished(900, 0))

    def test_natural_media_end_is_marked_watched(self) -> None:
        self.assertTrue(_is_finished(1000, 1000, explicit=True))


if __name__ == "__main__":
    unittest.main()
