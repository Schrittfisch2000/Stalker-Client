from __future__ import annotations

import unittest
from pathlib import Path

from app.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


class PlaybackSessionAssetTests(unittest.TestCase):
    def test_session_release_script_is_loaded_with_current_version(self) -> None:
        template = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
        self.assertIn(
            f'/static/playback-session.js?v={APP_VERSION}',
            template,
        )

    def test_session_release_endpoint_is_present(self) -> None:
        source = (ROOT / "app/playback_runtime_fix.py").read_text(encoding="utf-8")
        self.assertIn('/api/session-release/{ticket}', source)
        self.assertIn('Frischen Portal-Link für Medienwiedergabe erstellt', source)


if __name__ == "__main__":
    unittest.main()
