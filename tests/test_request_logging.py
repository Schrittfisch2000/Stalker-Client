from __future__ import annotations

import unittest

from app.main import safe_log_path


class RequestLoggingTests(unittest.TestCase):
    def test_stream_tickets_are_redacted(self) -> None:
        self.assertEqual(
            safe_log_path("/api/session-release/secret-ticket"),
            "/api/session-release/<ticket>",
        )
        self.assertEqual(
            safe_log_path("/api/vod-seek/secret-ticket"),
            "/api/vod-seek/<ticket>",
        )
        self.assertEqual(
            safe_log_path("/hls/secret-ticket/index.m3u8"),
            "/hls/<ticket>/index.m3u8",
        )

    def test_regular_api_path_is_unchanged(self) -> None:
        self.assertEqual(safe_log_path("/api/categories/vod"), "/api/categories/vod")


if __name__ == "__main__":
    unittest.main()
