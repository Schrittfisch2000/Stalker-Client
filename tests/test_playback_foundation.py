from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PlaybackFoundationTests(unittest.TestCase):
    def test_vod_uses_one_combined_media_probe(self) -> None:
        source = (ROOT / "app/safari_hls_fix.py").read_text(encoding="utf-8")

        self.assertIn("async def _probe_media(", source)
        self.assertNotIn("async def _probe_duration(", source)
        self.assertNotIn("async def _probe_video_codec(", source)
        self.assertIn('playback["probe"] = probe.to_ticket()', source)

    def test_hls_session_records_selected_playback_mode(self) -> None:
        source = (ROOT / "app/safari_hls_fix.py").read_text(encoding="utf-8")
        diagnostics = (ROOT / "app/diagnostics.py").read_text(encoding="utf-8")

        self.assertIn('"playback_mode": playback_plan.mode', source)
        self.assertIn('"playback_remux"', diagnostics)
        self.assertIn('"playback_audio_transcode"', diagnostics)
        self.assertIn('"playback_full_transcode"', diagnostics)


if __name__ == "__main__":
    unittest.main()
