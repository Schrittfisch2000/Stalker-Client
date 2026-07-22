from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from . import live_ts_proxy as legacy
from . import main, safari_hls_fix
from .config import Settings
from .stalker import StalkerClient

PREPARE_REPLACEMENT_AFTER_SECONDS = 26.0
MAX_CONNECTION_AGE_SECONDS = 42.0
CURRENT_READ_TIMEOUT_SECONDS = 6.0
CATCH_UP_TIMEOUT_SECONDS = 4.0
MAX_CATCH_UP_PACKETS = 24000


@dataclass
class PreparedReplacementV2:
    connection: legacy.UpstreamConnection
    packets: list[bytes]
    source_anchor: int | None
    source_pts_by_pid: dict[int, int]
    source_pcr_anchor: int | None
    keyframe_found: bool


class MultiClockTimelineNormalizer(legacy.TsTimelineNormalizer):
    """Normalisiert Video, Audio und PCR beim Verbindungswechsel getrennt."""

    def __init__(self) -> None:
        super().__init__()
        self.timestamp_offsets_by_pid: dict[int, int] = {}
        self.last_output_pts_by_pid: dict[int, int] = {}
        self.last_source_video_pts: int | None = None
        self.pcr_offset: int = 0

    def begin_multi_clock_switch(
        self,
        source_anchor: int | None,
        source_pts_by_pid: dict[int, int],
        source_pcr_anchor: int | None,
    ) -> None:
        output_anchor = self.output_anchor()
        if output_anchor is not None and source_anchor is None:
            raise ValueError("replacement stream has no video PTS anchor")

        if source_anchor is None or output_anchor is None:
            self.timestamp_offset = 0
        else:
            target = (output_anchor + legacy.TIMELINE_GAP_90KHZ) % legacy.PTS_WRAP
            self.timestamp_offset = (target - source_anchor) % legacy.PTS_WRAP

        self.timestamp_offsets_by_pid = {}
        for pid, source_pts in source_pts_by_pid.items():
            previous_pts = self.last_output_pts_by_pid.get(pid)
            if previous_pts is None:
                continue
            target = (previous_pts + legacy.TIMELINE_GAP_90KHZ) % legacy.PTS_WRAP
            self.timestamp_offsets_by_pid[pid] = (target - source_pts) % legacy.PTS_WRAP

        if self.last_output_pcr is not None and source_pcr_anchor is not None:
            target_pcr = (
                self.last_output_pcr + legacy.TIMELINE_GAP_90KHZ * 300
            ) % legacy.PCR_WRAP
            self.pcr_offset = (target_pcr - source_pcr_anchor) % legacy.PCR_WRAP
        else:
            self.pcr_offset = (self.timestamp_offset * 300) % legacy.PCR_WRAP

        self.switch_pending = True

    def _rewrite_pcr(self, packet: bytearray, adaptation_control: int) -> None:
        if adaptation_control not in (2, 3) or packet[4] < 7:
            return
        flags = packet[5]
        if not (flags & 0x10):
            return
        pos = 6
        base = (
            (packet[pos] << 25)
            | (packet[pos + 1] << 17)
            | (packet[pos + 2] << 9)
            | (packet[pos + 3] << 1)
            | (packet[pos + 4] >> 7)
        )
        extension = ((packet[pos + 4] & 0x01) << 8) | packet[pos + 5]
        source_pcr = base * 300 + extension
        pcr = (source_pcr + self.pcr_offset) % legacy.PCR_WRAP
        new_base, new_extension = divmod(pcr, 300)
        packet[pos] = (new_base >> 25) & 0xFF
        packet[pos + 1] = (new_base >> 17) & 0xFF
        packet[pos + 2] = (new_base >> 9) & 0xFF
        packet[pos + 3] = (new_base >> 1) & 0xFF
        packet[pos + 4] = ((new_base & 0x01) << 7) | 0x7E | ((new_extension >> 8) & 0x01)
        packet[pos + 5] = new_extension & 0xFF
        self.last_output_pcr = pcr

    def _rewrite_pes_timestamps(
        self,
        packet: bytearray,
        pid: int,
        payload_start: bool,
        payload_offset: int | None,
    ) -> None:
        if not payload_start or payload_offset is None or payload_offset + 14 > legacy.TS_PACKET_SIZE:
            return
        if packet[payload_offset:payload_offset + 3] != b"\x00\x00\x01":
            return
        flags = (packet[payload_offset + 7] >> 6) & 0x03
        pos = payload_offset + 9
        if flags in (2, 3) and pos + 5 <= legacy.TS_PACKET_SIZE:
            source_pts = legacy._decode_timestamp(packet, pos)
            offset = self.timestamp_offsets_by_pid.get(pid, self.timestamp_offset)
            rewritten = (source_pts + offset) % legacy.PTS_WRAP
            legacy._encode_timestamp(packet, pos, rewritten, packet[pos] >> 4)
            self.last_output_pts = rewritten
            self.last_output_pts_by_pid[pid] = rewritten
            if not self.video_pids or pid in self.video_pids:
                self.last_output_video_pts = rewritten
                self.last_source_video_pts = source_pts
            if flags == 3 and pos + 10 <= legacy.TS_PACKET_SIZE:
                source_dts = legacy._decode_timestamp(packet, pos + 5)
                legacy._encode_timestamp(
                    packet,
                    pos + 5,
                    (source_dts + offset) % legacy.PTS_WRAP,
                    packet[pos + 5] >> 4,
                )
        if self.switch_pending and pid in self.video_pids:
            self.switch_pending = False


def _packet_source_pcr(packet: bytes) -> int | None:
    if len(packet) != legacy.TS_PACKET_SIZE or packet[0] != 0x47:
        return None
    adaptation_control = (packet[3] >> 4) & 0x03
    if adaptation_control not in (2, 3) or packet[4] < 7 or not (packet[5] & 0x10):
        return None
    pos = 6
    base = (
        (packet[pos] << 25)
        | (packet[pos + 1] << 17)
        | (packet[pos + 2] << 9)
        | (packet[pos + 3] << 1)
        | (packet[pos + 4] >> 7)
    )
    extension = ((packet[pos + 4] & 0x01) << 8) | packet[pos + 5]
    return base * 300 + extension


def _source_pts_by_pid(packets: list[bytes]) -> dict[int, int]:
    anchors: dict[int, int] = {}
    for packet in packets:
        pid = legacy._packet_pid(packet)
        if pid in anchors:
            continue
        pts = legacy._packet_source_pts(packet)
        if pts is not None:
            anchors[pid] = pts
    return anchors


def _source_pcr_anchor(packets: list[bytes]) -> int | None:
    for packet in packets:
        pcr = _packet_source_pcr(packet)
        if pcr is not None:
            return pcr
    return None


def _pts_at_or_after(value: int, target: int) -> bool:
    return ((value - target) % legacy.PTS_WRAP) < (legacy.PTS_WRAP // 2)


def _replacement_from_packets(
    connection: legacy.UpstreamConnection,
    packets: list[bytes],
    normalizer: MultiClockTimelineNormalizer,
) -> PreparedReplacementV2:
    source_anchor = legacy._select_switch_anchor(packets, normalizer.video_pids)
    return PreparedReplacementV2(
        connection=connection,
        packets=packets,
        source_anchor=source_anchor,
        source_pts_by_pid=_source_pts_by_pid(packets),
        source_pcr_anchor=_source_pcr_anchor(packets),
        keyframe_found=True,
    )


async def _warm_replacement(
    data: dict[str, Any],
    settings: Settings,
    portal: StalkerClient,
    normalizer: MultiClockTimelineNormalizer,
) -> PreparedReplacementV2:
    connection = await legacy._open_upstream(await legacy._fresh_url(data, portal), settings, portal)
    packets: list[bytes] = []
    keyframe_index: int | None = None
    source_anchor: int | None = None
    deadline = time.monotonic() + legacy.REPLACEMENT_WARMUP_TIMEOUT_SECONDS
    try:
        while time.monotonic() < deadline and len(packets) < legacy.MAX_WARMUP_PACKETS:
            chunk = await asyncio.wait_for(connection.iterator.__anext__(), timeout=2.0)
            for packet in legacy._split_packets(legacy._aligned_ts_payload(connection, chunk)):
                packets.append(packet)
                if keyframe_index is None and legacy._contains_random_access(packet, normalizer.video_pids):
                    keyframe_index = len(packets) - 1
                if keyframe_index is not None:
                    switch_packets = packets[keyframe_index:]
                    source_anchor = legacy._select_switch_anchor(switch_packets, normalizer.video_pids)
                    if source_anchor is not None and len(switch_packets) >= legacy.MIN_PACKETS_AFTER_KEYFRAME:
                        break
            if keyframe_index is not None and source_anchor is not None:
                if len(packets) - keyframe_index >= legacy.MIN_PACKETS_AFTER_KEYFRAME:
                    break
    except (StopAsyncIteration, asyncio.TimeoutError):
        pass
    except Exception:
        await connection.close()
        raise

    if keyframe_index is None:
        await connection.close()
        raise RuntimeError("replacement stream contained no random-access point")

    start = keyframe_index
    while start > 0 and legacy._packet_pid(packets[start - 1]) in {0, normalizer.pmt_pid}:
        start -= 1
    packets = packets[start:]
    replacement = _replacement_from_packets(connection, packets, normalizer)
    if normalizer.output_anchor() is not None and replacement.source_anchor is None:
        await connection.close()
        raise RuntimeError("replacement stream contained no video PTS after random-access point")
    return replacement


async def _catch_up_replacement(
    replacement: PreparedReplacementV2,
    normalizer: MultiClockTimelineNormalizer,
) -> PreparedReplacementV2:
    target = normalizer.last_source_video_pts
    anchor = replacement.source_anchor
    if target is None or anchor is None or _pts_at_or_after(anchor, target):
        return replacement

    candidate: list[bytes] = []
    candidate_anchor: int | None = None
    deadline = time.monotonic() + CATCH_UP_TIMEOUT_SECONDS
    read_packets = 0
    try:
        while time.monotonic() < deadline and read_packets < MAX_CATCH_UP_PACKETS:
            chunk = await asyncio.wait_for(replacement.connection.iterator.__anext__(), timeout=1.5)
            for packet in legacy._split_packets(legacy._aligned_ts_payload(replacement.connection, chunk)):
                read_packets += 1
                if legacy._contains_random_access(packet, normalizer.video_pids):
                    candidate = [packet]
                    candidate_anchor = legacy._select_switch_anchor(candidate, normalizer.video_pids)
                elif candidate:
                    candidate.append(packet)
                    if candidate_anchor is None:
                        candidate_anchor = legacy._select_switch_anchor(candidate, normalizer.video_pids)

                if candidate_anchor is not None and not _pts_at_or_after(candidate_anchor, target):
                    continue
                if candidate_anchor is not None and len(candidate) >= legacy.MIN_PACKETS_AFTER_KEYFRAME:
                    return _replacement_from_packets(replacement.connection, candidate, normalizer)
    except (StopAsyncIteration, asyncio.TimeoutError):
        pass

    main.logger.warning(
        "TS-Proxy-Ersatzstrom konnte nicht bis zum aktuellen Bild nachgeführt werden; vorbereiteter Keyframe wird verwendet"
    )
    return replacement


async def run_live_ts_proxy_v2(
    session_id: str,
    data: dict[str, Any],
    settings: Settings,
    portal: StalkerClient,
    process: asyncio.subprocess.Process,
) -> None:
    if process.stdin is None:
        main.logger.error("TS-Proxy ohne FFmpeg-stdin gestartet: Session=%s", session_id)
        return

    current: legacy.UpstreamConnection | None = None
    prepared: asyncio.Task[PreparedReplacementV2] | None = None
    reconnects = 0
    normalizer = MultiClockTimelineNormalizer()

    async def switch_to(replacement: PreparedReplacementV2) -> None:
        nonlocal current, reconnects
        replacement = await _catch_up_replacement(replacement, normalizer)
        normalizer.begin_multi_clock_switch(
            replacement.source_anchor,
            replacement.source_pts_by_pid,
            replacement.source_pcr_anchor,
        )
        previous = current
        current = replacement.connection
        prefix = normalizer.reinjected_psi()
        payload = prefix + b"".join(
            filter(None, (normalizer.normalize(packet) for packet in replacement.packets))
        )
        if payload:
            process.stdin.write(payload)
            await process.stdin.drain()
        if previous is not None:
            await previous.close()
        reconnects += 1
        main.logger.info(
            "TS-Proxy mit getrennten Medienuhren gewechselt: Session=%s, Wechsel=%s, Pufferpakete=%s, Videoanker=%s, PCR-Anker=%s",
            session_id,
            reconnects,
            len(replacement.packets),
            replacement.source_anchor,
            replacement.source_pcr_anchor,
        )

    async def obtain_replacement() -> PreparedReplacementV2:
        nonlocal prepared
        if prepared is None:
            prepared = asyncio.create_task(_warm_replacement(data, settings, portal, normalizer))
        try:
            return await asyncio.wait_for(
                asyncio.shield(prepared),
                timeout=legacy.REPLACEMENT_WARMUP_TIMEOUT_SECONDS,
            )
        finally:
            prepared = None

    try:
        current = await legacy._open_upstream(str(data["url"]), settings, portal)
        main.logger.info(
            "Dauerhafter TS-Proxy mit Mehrfach-Zeitachsen verbunden: Session=%s",
            session_id,
        )

        while process.returncode is None:
            age = time.monotonic() - current.opened_at
            if prepared is None and age >= PREPARE_REPLACEMENT_AFTER_SECONDS:
                prepared = asyncio.create_task(_warm_replacement(data, settings, portal, normalizer))

            if age >= MAX_CONNECTION_AGE_SECONDS:
                try:
                    replacement = await obtain_replacement()
                except Exception as exc:
                    main.logger.warning(
                        "TS-Proxy-Zwangswechsel fehlgeschlagen: Session=%s, Fehler=%s",
                        session_id,
                        exc,
                    )
                    await asyncio.sleep(legacy.RECONNECT_DELAY_SECONDS)
                else:
                    await switch_to(replacement)
                    continue

            try:
                chunk = await asyncio.wait_for(
                    current.iterator.__anext__(),
                    timeout=CURRENT_READ_TIMEOUT_SECONDS,
                )
            except asyncio.CancelledError:
                raise
            except (StopAsyncIteration, asyncio.TimeoutError, Exception) as exc:
                main.logger.warning(
                    "TS-Proxy-Upstream wird erneuert: Session=%s, Fehler=%s",
                    session_id,
                    exc,
                )
                try:
                    replacement = await obtain_replacement()
                except Exception as reconnect_exc:
                    main.logger.warning(
                        "TS-Proxy-Neuverbindung fehlgeschlagen: Session=%s, Fehler=%s",
                        session_id,
                        reconnect_exc,
                    )
                    await asyncio.sleep(legacy.RECONNECT_DELAY_SECONDS)
                    continue
                await switch_to(replacement)
                continue

            payload = legacy._aligned_ts_payload(current, chunk)
            if not payload:
                continue
            normalized = b"".join(
                filter(None, (normalizer.normalize(packet) for packet in legacy._split_packets(payload)))
            )
            if normalized:
                process.stdin.write(normalized)
                await process.stdin.drain()

    except (BrokenPipeError, ConnectionResetError):
        main.logger.info("TS-Proxy beendet, weil FFmpeg geschlossen wurde: Session=%s", session_id)
    except asyncio.CancelledError:
        raise
    except Exception:
        main.logger.exception("Dauerhafter TS-Proxy unerwartet beendet: Session=%s", session_id)
    finally:
        if prepared is not None:
            prepared.cancel()
            try:
                replacement = await prepared
                await replacement.connection.close()
            except (asyncio.CancelledError, Exception):
                pass
        if current is not None:
            await current.close()
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()
        main.logger.info("Dauerhafter TS-Proxy geschlossen: Session=%s", session_id)


def install() -> None:
    safari_hls_fix.run_live_ts_proxy = run_live_ts_proxy_v2
