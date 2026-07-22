from __future__ import annotations

import unittest

from app import live_timeline_v2
from app.live_timeline_v3 import _catch_up_replacement_v3, install


class LiveTimelineV3Tests(unittest.TestCase):
    def test_install_replaces_v2_catch_up_strategy(self) -> None:
        install()
        self.assertIs(live_timeline_v2._catch_up_replacement, _catch_up_replacement_v3)


if __name__ == "__main__":
    unittest.main()
