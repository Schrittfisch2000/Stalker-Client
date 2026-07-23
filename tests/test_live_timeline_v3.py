from __future__ import annotations

import unittest

from app import live_timeline_v2
from app.live_timeline_v3 import (
    MAX_COMPARABLE_LAG_SECONDS,
    _catch_up_replacement_v3,
    _comparable_lag_seconds,
    install,
)


class LiveTimelineV3Tests(unittest.TestCase):
    def test_install_replaces_v2_catch_up_strategy(self) -> None:
        install()
        self.assertIs(live_timeline_v2._catch_up_replacement, _catch_up_replacement_v3)

    def test_normal_live_lag_is_compared(self) -> None:
        self.assertEqual(_comparable_lag_seconds(2_000_000, 1_100_000), 10.0)

    def test_different_pts_epoch_is_not_treated_as_hours_of_lag(self) -> None:
        anchor = 1_000_000
        target = anchor + int((MAX_COMPARABLE_LAG_SECONDS + 1) * 90_000)
        self.assertIsNone(_comparable_lag_seconds(target, anchor))


if __name__ == "__main__":
    unittest.main()
