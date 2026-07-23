from __future__ import annotations

import unittest

from app.live_timeline_v2 import MultiClockTimelineNormalizer, _packet_source_pcr, _pts_at_or_after
from app.live_ts_proxy import PCR_WRAP, PTS_WRAP, _decode_timestamp, _encode_timestamp

TS_PACKET_SIZE = 188
VIDEO_PID = 0x101
AUDIO_PID = 0x102
REPLACEMENT_AUDIO_PID = 0x202
PCR_PID = 0x100
VIDEO_STEP = 3_600
AUDIO_STEP = 1_920
PCR_STEP = 3_600 * 300


def make_pes_packet(pid: int, pts: int, dts: int | None = None) -> bytes:
    packet = bytearray([0xFF] * TS_PACKET_SIZE)
    packet[0] = 0x47
    packet[1] = 0x40 | ((pid >> 8) & 0x1F)
    packet[2] = pid & 0xFF
    packet[3] = 0x10
    pos = 4
    packet[pos:pos + 3] = b"\x00\x00\x01"
    packet[pos + 3] = 0xE0 if pid == VIDEO_PID else 0xC0
    packet[pos + 4:pos + 6] = b"\x00\x00"
    packet[pos + 6] = 0x80
    packet[pos + 7] = 0xC0 if dts is not None else 0x80
    packet[pos + 8] = 10 if dts is not None else 5
    _encode_timestamp(packet, pos + 9, pts, 0x03 if dts is not None else 0x02)
    if dts is not None:
        _encode_timestamp(packet, pos + 14, dts, 0x01)
    return bytes(packet)


def make_pcr_packet(pcr: int) -> bytes:
    packet = bytearray([0xFF] * TS_PACKET_SIZE)
    packet[0] = 0x47
    packet[1] = (PCR_PID >> 8) & 0x1F
    packet[2] = PCR_PID & 0xFF
    packet[3] = 0x20
    packet[4] = 7
    packet[5] = 0x10
    base, extension = divmod(pcr % PCR_WRAP, 300)
    packet[6] = (base >> 25) & 0xFF
    packet[7] = (base >> 17) & 0xFF
    packet[8] = (base >> 9) & 0xFF
    packet[9] = (base >> 1) & 0xFF
    packet[10] = ((base & 1) << 7) | 0x7E | ((extension >> 8) & 1)
    packet[11] = extension & 0xFF
    return bytes(packet)


class MultiClockTimelineTests(unittest.TestCase):
    def test_video_audio_and_pcr_continue_at_measured_cadence(self) -> None:
        normalizer = MultiClockTimelineNormalizer()
        normalizer.video_pids = {VIDEO_PID}

        normalizer.normalize(make_pes_packet(VIDEO_PID, 900_000, 891_000))
        normalizer.normalize(make_pes_packet(VIDEO_PID, 900_000 + VIDEO_STEP, 891_000 + VIDEO_STEP))
        normalizer.normalize(make_pes_packet(AUDIO_PID, 1_800_000))
        normalizer.normalize(make_pes_packet(AUDIO_PID, 1_800_000 + AUDIO_STEP))
        initial_pcr = 750_000 * 300 + 17
        current_pcr = initial_pcr + PCR_STEP
        normalizer.normalize(make_pcr_packet(initial_pcr))
        normalizer.normalize(make_pcr_packet(current_pcr))

        source_video = 45_000
        source_audio = 360_000
        source_pcr = 120_000 * 300 + 29
        normalizer.begin_multi_clock_switch(
            source_video,
            {VIDEO_PID: source_video, AUDIO_PID: source_audio},
            source_pcr,
        )

        video = normalizer.normalize(make_pes_packet(VIDEO_PID, source_video, 36_000))
        audio = normalizer.normalize(make_pes_packet(AUDIO_PID, source_audio))
        pcr = normalizer.normalize(make_pcr_packet(source_pcr))

        expected_video_pts = 900_000 + (2 * VIDEO_STEP)
        self.assertEqual(_decode_timestamp(video, 13), expected_video_pts)
        self.assertEqual(_decode_timestamp(video, 18), expected_video_pts - 9_000)
        self.assertEqual(_decode_timestamp(audio, 13), 1_800_000 + (2 * AUDIO_STEP))
        self.assertEqual(_packet_source_pcr(pcr), (current_pcr + PCR_STEP) % PCR_WRAP)

    def test_last_source_video_pts_is_recorded_before_rewrite(self) -> None:
        normalizer = MultiClockTimelineNormalizer()
        normalizer.video_pids = {VIDEO_PID}
        normalizer.timestamp_offset = 500_000
        normalizer.normalize(make_pes_packet(VIDEO_PID, 123_000))
        self.assertEqual(normalizer.last_source_video_pts, 123_000)
        self.assertEqual(normalizer.last_output_video_pts, 623_000)

    def test_audio_continues_when_replacement_changes_audio_pid(self) -> None:
        normalizer = MultiClockTimelineNormalizer()
        normalizer.video_pids = {VIDEO_PID}
        normalizer.normalize(make_pes_packet(VIDEO_PID, 900_000))
        normalizer.normalize(make_pes_packet(AUDIO_PID, 1_800_000))
        normalizer.normalize(make_pes_packet(AUDIO_PID, 1_800_000 + AUDIO_STEP))

        source_video = 45_000
        source_audio = 360_000
        normalizer.begin_multi_clock_switch(
            source_video,
            {VIDEO_PID: source_video, REPLACEMENT_AUDIO_PID: source_audio},
            None,
        )

        audio = normalizer.normalize(make_pes_packet(REPLACEMENT_AUDIO_PID, source_audio))
        self.assertEqual(_decode_timestamp(audio, 13), 1_800_000 + (2 * AUDIO_STEP))

    def test_pts_comparison_handles_wrap(self) -> None:
        target = PTS_WRAP - 1_000
        self.assertTrue(_pts_at_or_after(500, target))
        self.assertFalse(_pts_at_or_after(PTS_WRAP - 2_000, target))


if __name__ == "__main__":
    unittest.main()
