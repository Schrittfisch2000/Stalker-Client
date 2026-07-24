from __future__ import annotations

import unittest

from app.playback_policy import MediaProbe, choose_playback_plan


class PlaybackPolicyTests(unittest.TestCase):
    def test_h264_aac_uses_remux_without_encoding(self) -> None:
        plan = choose_playback_plan(MediaProbe(video_codec="h264", audio_codec="aac"))

        self.assertEqual(plan.mode, "remux")
        self.assertEqual(plan.video_args(), ["-c:v", "copy"])
        self.assertEqual(plan.audio_args(), ["-c:a", "copy"])

    def test_h264_ac3_only_transcodes_audio(self) -> None:
        plan = choose_playback_plan(MediaProbe(video_codec="h264", audio_codec="ac3"))

        self.assertEqual(plan.mode, "audio-transcode")
        self.assertTrue(plan.video_copy)
        self.assertFalse(plan.audio_copy)
        self.assertIn("aresample=async=1000:first_pts=0", plan.audio_args())
        self.assertIn("aac", plan.audio_args())

    def test_hevc_aac_transcodes_only_video(self) -> None:
        plan = choose_playback_plan(MediaProbe(video_codec="hevc", audio_codec="aac"))

        self.assertEqual(plan.mode, "full-transcode")
        self.assertIn("libx264", plan.video_args())
        self.assertEqual(plan.audio_args(), ["-c:a", "copy"])

    def test_unknown_codecs_use_compatible_fallback(self) -> None:
        plan = choose_playback_plan(MediaProbe())

        self.assertEqual(plan.mode, "full-transcode")
        self.assertIn("libx264", plan.video_args())
        self.assertIn("aac", plan.audio_args())

    def test_ffprobe_result_normalizes_codec_aliases_and_duration(self) -> None:
        probe = MediaProbe.from_ffprobe(
            {
                "streams": [
                    {"codec_type": "video", "codec_name": "avc1"},
                    {"codec_type": "audio", "codec_name": "mp4a"},
                ],
                "format": {"duration": "5420.25", "format_name": "mpegts"},
            }
        )

        self.assertEqual(probe.video_codec, "h264")
        self.assertEqual(probe.audio_codec, "aac")
        self.assertEqual(probe.duration, 5420.25)
        self.assertEqual(probe.container, "mpegts")

    def test_probe_ticket_round_trip_preserves_analysis(self) -> None:
        expected = MediaProbe(3600.0, "h264", "aac", "mpegts")

        self.assertEqual(MediaProbe.from_ticket(expected.to_ticket()), expected)


if __name__ == "__main__":
    unittest.main()
