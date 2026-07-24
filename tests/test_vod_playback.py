from __future__ import annotations

import unittest
from pathlib import Path

from app.playback_policy import MediaProbe, choose_playback_plan
from app.safari_hls_fix import _duration_from_item, _play_response


class VodDurationTests(unittest.TestCase):
    def test_h264_vod_is_remuxed_without_video_reencoding(self) -> None:
        args = choose_playback_plan(MediaProbe(video_codec="h264")).video_args()

        self.assertEqual(args, ["-c:v", "copy"])
        self.assertNotIn("libx264", args)

    def test_incompatible_vod_keeps_h264_fallback(self) -> None:
        args = choose_playback_plan(MediaProbe(video_codec="hevc")).video_args()

        self.assertIn("libx264", args)
        self.assertIn("ultrafast", args)

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

    def test_play_response_can_select_browser_mpegts_for_live_tv(self) -> None:
        response = _play_response(
            "/stream/ticket",
            None,
            False,
            "mpegts",
            "/hls/ticket/index.m3u8",
        )

        self.assertEqual(response["url"], "/stream/ticket")
        self.assertEqual(response["stream_type"], "mpegts")
        self.assertEqual(response["fallback_url"], "/hls/ticket/index.m3u8")

    def test_browser_removes_native_controls_for_seekable_vod(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app/static/vod-controls.js"
        ).read_text(encoding="utf-8")

        self.assertIn("video.toggleAttribute('controls', !customControls)", source)
        self.assertIn("duration > 0 && seekable", source)

    def test_browser_live_player_uses_mpegts_and_cleans_it_up(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/static/app.js").read_text(encoding="utf-8")
        template = (root / "app/templates/index.html").read_text(encoding="utf-8")
        sessions = (root / "app/static/playback-session.js").read_text(encoding="utf-8")

        self.assertIn("mpegts.js@1.8.0", template)
        self.assertIn("playback.stream_type === 'mpegts'", source)
        self.assertIn("mpegts.createPlayer", source)
        self.assertNotIn("liveBufferLatencyChasing", source)
        self.assertIn("state.mpegts.unload()", source)
        self.assertIn("state.mpegts.destroy()", source)
        self.assertIn("playback.fallback_url", source)
        self.assertIn("originalAttachPlayer(url, isLive, playback)", sessions)

    def test_apple_devices_use_native_hls_instead_of_mpegts(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/static/app.js").read_text(encoding="utf-8")
        controls = (root / "app/static/vod-controls.js").read_text(encoding="utf-8")
        recovery = (root / "app/static/safari-hls-recovery.js").read_text(encoding="utf-8")
        template = (root / "app/templates/index.html").read_text(encoding="utf-8")

        self.assertIn("/iPad|iPhone|iPod/", source)
        self.assertIn("navigator.maxTouchPoints > 1", source)
        self.assertIn("prefersNativeHlsPlayback()", source)
        self.assertIn("useAppleHlsFallback", source)
        self.assertIn("selectedUrl = useAppleHlsFallback ? playback.fallback_url : url", source)
        self.assertIn("window.prefersNativeHlsPlayback?.()", controls)
        self.assertIn("window.prefersNativeHlsPlayback?.()", recovery)
        self.assertIn('webkit-playsinline preload="auto"', template)

    def test_vod_mpegts_uses_browser_timeline_for_seeking(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app/static/vod-controls.js"
        ).read_text(encoding="utf-8")

        self.assertIn("directSeek = playback.stream_type === 'mpegts'", source)
        self.assertIn("video.currentTime = position", source)
        self.assertIn("path.match(/^\\/stream\\/", source)

    def test_hls_seek_waits_for_manifest_and_blocks_duplicate_requests(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app/static/vod-controls.js"
        ).read_text(encoding="utf-8")

        self.assertIn("seekPending", source)
        self.assertIn("if (!ticket || !duration || seekPending) return", source)
        self.assertIn("Hls.Events.MANIFEST_PARSED", source)
        self.assertIn("'vodSeek').disabled = true", source)

    def test_saved_progress_is_applied_only_once_per_playback(self) -> None:
        source = (
            Path(__file__).resolve().parents[1] / "app/static/media-ui.js"
        ).read_text(encoding="utf-8")

        self.assertIn("resumeApplied: false", source)
        self.assertIn("mediaState.resumeApplied = false", source)
        self.assertIn("if (!item || mediaState.resumeApplied) return", source)
        self.assertIn("mediaState.resumeApplied = true", source)

    def test_watched_badge_is_not_created_when_playback_only_started(self) -> None:
        root = Path(__file__).resolve().parents[1]
        access = (root / "app/static/access-ui.js").read_text(encoding="utf-8")
        media = (root / "app/static/media-ui.js").read_text(encoding="utf-8")

        self.assertNotIn("watched-badge", access)
        self.assertNotIn("markWatchedCards", access)
        self.assertIn("if (progress?.finished)", media)


if __name__ == "__main__":
    unittest.main()
