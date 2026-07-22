from __future__ import annotations

import unittest

from app.live_ts_proxy import (
    PCR_WRAP,
    PTS_WRAP,
    TIMELINE_GAP_90KHZ,
    TsTimelineNormalizer,
    _decode_timestamp,
    _encode_timestamp,
    _select_switch_anchor,
)

TS_PACKET_SIZE = 188


def make_pes_packet(pid: int, pts: int, dts: int | None = None, continuity: int = 0) -> bytes:
    packet = bytearray([0xFF] * TS_PACKET_SIZE)
    packet[0] = 0x47
    packet[1] = 0x40 | ((pid >> 8) & 0x1F)
    packet[2] = pid & 0xFF
    packet[3] = 0x10 | (continuity & 0x0F)
    pos = 4
    packet[pos:pos + 3] = b"\x00\x00\x01"
    packet[pos + 3] = 0xE0
    packet[pos + 4:pos + 6] = b"\x00\x00"
    packet[pos + 6] = 0x80
    packet[pos + 7] = 0xC0 if dts is not None else 0x80
    packet[pos + 8] = 10 if dts is not None else 5
    _encode_timestamp(packet, pos + 9, pts, 0x03 if dts is not None else 0x02)
    if dts is not None:
        _encode_timestamp(packet, pos + 14, dts, 0x01)
    return bytes(packet)


def make_pcr_packet(pid: int, pcr: int, continuity: int = 0) -> bytes:
    packet = bytearray([0xFF] * TS_PACKET_SIZE)
    packet[0] = 0x47
    packet[1] = (pid >> 8) & 0x1F
    packet[2] = pid & 0xFF
    packet[3] = 0x20 | (continuity & 0x0F)
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


def read_pcr(packet: bytes) -> int:
    base = (
        (packet[6] << 25)
        | (packet[7] << 17)
        | (packet[8] << 9)
        | (packet[9] << 1)
        | (packet[10] >> 7)
    )
    extension = ((packet[10] & 1) << 8) | packet[11]
    return base * 300 + extension


class TimestampCodecTests(unittest.TestCase):
    def test_round_trip_near_wrap(self) -> None:
        packet = bytearray(16)
        value = PTS_WRAP - 123
        _encode_timestamp(packet, 3, value, 0x02)
        self.assertEqual(_decode_timestamp(packet, 3), value)
        self.assertEqual(packet[3] >> 4, 0x02)


class TimelineNormalizerTests(unittest.TestCase):
    def test_switch_moves_pts_and_dts_forward(self) -> None:
        normalizer = TsTimelineNormalizer(video_pids={0x101})
        first = normalizer.normalize(make_pes_packet(0x101, 900_000, 891_000))
        self.assertEqual(_decode_timestamp(first, 13), 900_000)
        self.assertEqual(_decode_timestamp(first, 18), 891_000)

        normalizer.begin_switch(45_000)
        switched = normalizer.normalize(make_pes_packet(0x101, 45_000, 36_000))
        expected_pts = 900_000 + TIMELINE_GAP_90KHZ
        self.assertEqual(_decode_timestamp(switched, 13), expected_pts)
        self.assertEqual(_decode_timestamp(switched, 18), expected_pts - 9_000)

    def test_timestamp_offset_wraps_cleanly(self) -> None:
        normalizer = TsTimelineNormalizer(video_pids={0x101}, last_output_pts=PTS_WRAP - 4_000)
        normalizer.begin_switch(20_000)
        switched = normalizer.normalize(make_pes_packet(0x101, 20_000))
        self.assertEqual(_decode_timestamp(switched, 13), (PTS_WRAP - 4_000 + TIMELINE_GAP_90KHZ) % PTS_WRAP)

    def test_pcr_uses_same_offset_as_pts(self) -> None:
        normalizer = TsTimelineNormalizer(last_output_pts=900_000)
        normalizer.begin_switch(45_000)
        source_pcr = 45_000 * 300 + 17
        rewritten = normalizer.normalize(make_pcr_packet(0x100, source_pcr))
        self.assertEqual(read_pcr(rewritten), ((900_000 + TIMELINE_GAP_90KHZ) * 300 + 17) % PCR_WRAP)

    def test_continuity_counter_is_reassigned_per_pid(self) -> None:
        normalizer = TsTimelineNormalizer()
        first = normalizer.normalize(make_pes_packet(0x101, 100_000, continuity=12))
        second = normalizer.normalize(make_pes_packet(0x101, 109_000, continuity=3))
        other = normalizer.normalize(make_pes_packet(0x102, 100_000, continuity=9))
        self.assertEqual(first[3] & 0x0F, 0)
        self.assertEqual(second[3] & 0x0F, 1)
        self.assertEqual(other[3] & 0x0F, 0)

    def test_switch_rejects_missing_anchor_on_active_timeline(self) -> None:
        normalizer = TsTimelineNormalizer(last_output_pts=900_000, timestamp_offset=123_000)
        with self.assertRaisesRegex(ValueError, "no video PTS anchor"):
            normalizer.begin_switch(None)
        self.assertEqual(normalizer.timestamp_offset, 123_000)


class SwitchAnchorTests(unittest.TestCase):
    def test_video_pts_is_preferred_over_earlier_audio_pts(self) -> None:
        packets = [
            make_pes_packet(0x102, 2_700_000),
            make_pes_packet(0x101, 180_000),
        ]
        self.assertEqual(_select_switch_anchor(packets, {0x101}), 180_000)

    def test_fallback_anchor_is_used_when_video_pid_is_unknown(self) -> None:
        packets = [make_pes_packet(0x102, 270_000)]
        self.assertEqual(_select_switch_anchor(packets, set()), 270_000)

    def test_missing_pts_returns_no_anchor(self) -> None:
        packet = bytearray([0xFF] * TS_PACKET_SIZE)
        packet[0] = 0x47
        packet[1] = 0x40
        packet[3] = 0x10
        self.assertIsNone(_select_switch_anchor([bytes(packet)], {0x101}))


if __name__ == "__main__":
    unittest.main()
