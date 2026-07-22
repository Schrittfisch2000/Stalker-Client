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
MAX_CATCH_UP_PACKETS = 60_000
MIN_SWITCH_CONTEXT_PACKETS = 1_024
DEFAULT_VIDEO_STEP_90KHZ = 3_600
DEFAULT_AUDIO_STEP_90KHZ = 1_920
DEFAULT_PCR_STEP = legacy.TIMELINE_GAP_90KHZ * 300
MAX_REASONABLE_PTS_STEP = 90_000
MAX_REASONABLE_PCR_STEP = MAX_REASONABLE_PTS_STEP * 300


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
        self.last_pts_step_by_pid: dict[int, int] = {}
        self.last_output_video_pid: int | None = None
        self.last_source_video_pts: int | None = None
        self.last_pcr_step: int | None = None
        self.pcr_offset: int = 0

    def _default_step_for_pid(self, pid: int) -> int:
        if pid in self.video_pids:
            return DEFAULT_VIDEO_STEP_90KHZ
        return DEFAULT_AUDIO_STEP_90KHZ

    def _next_pts_target(self, pid: int, previous_pts: int) -> int:
        step = self.last_pts_step_by_pid.get(pid, self._default_step_for_pid(pid))
        return (previous_pts + step) % legacy.PTS_WRAP

    def begin_multi_clock_switch(
        self,
        source_anchor: int | None,
        source_pts_by_pid: dict[int, int],
        source_pcr_anchor: int | None,
    ) -> None:
        output_anchor = self.output_anchor()
        if output_anchor is not None and source_anchor is None:
            raise ValueError("replacement stream has no video PTS anchor")

        source_video_pid = next(
            (pid for pid in self.video_pids if pid in source_pts_by_pid),
            None,
        )
        output_video_pid = self.last_output_video_pid or source_video_pid
        if source_anchor is None or output_anchor is None:
            self.timestamp_offset = 0
        elif output_video_pid is not None:
            target = self._next_pts_target(output_video_pid, output_anchor)
            self.timestamp_offset = (target - source_anchor) % legacy.PTS_WRAP
        else:
            target = (output_anchor + DEFAULT_VIDEO_STEP_90KHZ) % legacy.PTS_WRAP
            self.timestamp_offset = (target - source_anchor) % legacy.PTS_WRAP

        self.timestamp_offsets_by_pid = {}
        for pid, source_pts in source_pts_by_pid.items():
            previous_pts = self.last_output_pts_by_pid.get(pid)
            if previous_pts is None:
                continue
            target = self._next_pts_target(pid, previous_pts)
            self.timestamp_offsets_by_pid[pid] = (target - source_pts) % legacy.PTS_WRAP

        if self.last_output_pcr is not None and source_pcr_anchor is not None:
            pcr_step = self.last_pcr_step or DEFAULT_PCR_STEP
            target_pcr = (self.last_output_pcr + pcr_step) % legacy.PCR_WRAP
            self.pcr_offset = (target_pcr - source_pcr_anchor) % legacy.PCR_WRAP
        else:
            self.pcr_offset = (self.timestamp_offset * 300) % legacy.PCR_WRAP

        self.switch_pending = True

    def _rewrite_pcr(self, packet: bytearray, adaptation_control: int) -> None:
        if adaptation_control not in (2, 3) or packet[4] < 7:
            return
        if not (packet[5] & 0x10):
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

        previous_pcr = self.last_output_pcr
        if previous_pcr is not None:
            step = (pcr - previous_pcr) % legacy.PCR_WRAP
            if 0 < step <= MAX_REASONABLE_PCR_STEP:
                self.last_pcr_step = step

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

            previous_pts = self.last_output_pts_by_pid.get(pid)
            if previous_pts is not None:
                step = (rewritten - previous_pts) % legacy.PTS_WRAP
                if 0 < step <= MAX_REASONABLE_PTS_STEP:
                    self.last_pts_step_by_pid[pid] = step

            self.last_output_pts = rewritten
            self.last_output_pts_by_pid[pid] = rewritten
            if not self.video_pids or pid in self.video_pids:
                self.last_output_video_pts = rewritten
                self.last_output_video_pid = pid
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

                if keyframe_index is None:
                    continue

                switch_packets = packets[keyframe_index:]
                if source_anchor is None:
                    source_anchor = legacy._select_switch_anchor(switch_packets, normalizer.video_pids)
                if source_anchor is not None and len(switch_packets) >= MIN_SWITCH_CONTEXT_PACKETS:
                    break

            if keyframe_index is not None and source_anchor is not None:
                if len(packets) - keyframe_index >= MIN_SWITCH_CONTEXT_PACKETS:
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
    session_id: str,
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

                if candidate_anchor is None or not _pts_at_or_after(candidate_anchor, target):
                    continue
                if len(candidate) >= MIN_SWITCH_CONTEXT_PACKETS:
                    main.logger.info(
                        "TS-Proxy-Ersatzstrom bis zum aktuellen Bild nachgeführt: Session=%s, ÜbersprungenePakete=%s, Ziel=%s, Anker=%s",
                        session_id,
                        read_packets - len(candidate),
                        target,
                        candidate_anchor,
                    )
                    return _replacement_from_packets(replacement.connection, candidate, normalizer)
    except (StopAsyncIteration, asyncio.TimeoutError):
        pass

    main.logger.warning(
        "TS-Proxy-Ersatzstrom konnte nicht bis zum aktuellen Bild nachgeführt werden: Session=%s, Ziel=%s, Ursprungsanker=%s",
        session_id,
        target,
        anchor,
    )
    return replacement


async def _discard_prepared_task(task: asyncio.Task[PreparedReplacementV2]) -> None:
    if not task.done():
        task.cancel()
    try:
        replacement = await task
    except (asyncio.CancelledError, Exception):
        return
    await replacement.connection.close()


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
        replacement = await _catch_up_replacement(replacement, normalizer, session_id)
        normalizer.begin_multi_clock_switch(
            replacement.source_anchor,
            replacement.source_pts_by_pid,
            replacement.source_pcr_anchor,
        )

        prefix = normalizer.reinjected_psi()
        payload = prefix + b"".join(
            filter(None, (normalizer.normalize(packet) for packet in replacement.packets))
        )
        if payload:
            process.stdin.write(payload)
            await process.stdin.drain()

        previous = current
        current = replacement.connection
        if previous is not None:
            await previous.close()

        reconnects += 1
        main.logger.info(
            "TS-Proxy mit getrennten Medienuhren gewechselt: Session=%s, Wechsel=%s, Pufferpakete=%s, Videoanker=%s, Medienanker=%s, PCR-Anker=%s",
            session_id,
            reconnects,
            len(replacement.packets),
            replacement.source_anchor,
            len(replacement.source_pts_by_pid),
            replacement.source_pcr_anchor,
        )

    async def obtain_replacement() -> PreparedReplacementV2:
        nonlocal prepared
        task = prepared
        if task is None:
            task = asyncio.create_task(_warm_replacement(data, settings, portal, normalizer))
            prepared = task

        try:
            return await asyncio.wait_for(
                asyncio.shield(task),
                timeout=legacy.REPLACEMENT_WARMUP_TIMEOUT_SECONDS,
            )
        except BaseException:
            await _discard_prepared_task(task)
            raise
        finally:
            if prepared is task:
                prepared = None

    async def replace_after_error(error: BaseException) -> bool:
        main.logger.warning(
            "TS-Proxy-Upstream wird erneuert: Session=%s, Fehler=%s",
            session_id,
            error,
        )
        try:
            replacement = await obtain_replacement()
            await switch_to(replacement)
        except asyncio.CancelledError:
            raise
        except Exception as reconnect_error:
            main.logger.warning(
                "TS-Proxy-Neuverbindung fehlgeschlagen: Session=%s, Fehler=%s",
                session_id,
                reconnect_error,
            )
            await asyncio.sleep(legacy.RECONNECT_DELAY_SECONDS)
            return False
        return True

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

            if age >= MAX_CONNECTION_AGE_SECONDS and prepared is not None and prepared.done():
                try:
                    replacement = await obtain_replacement()
                    await switch_to(replacement)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    main.logger.warning(
                        "TS-Proxy-Zwangswechsel fehlgeschlagen: Session=%s, Fehler=%s",
                        session_id,
                        exc,
                    )
                else:
                    continue

            try:
                chunk = await asyncio.wait_for(
                    current.iterator.__anext__(),
                    timeout=CURRENT_READ_TIMEOUT_SECONDS,
                )
            except asyncio.CancelledError:
                raise
            except StopAsyncIteration as exc:
                await replace_after_error(exc)
                continue
            except asyncio.TimeoutError as exc:
                await replace_after_error(exc)
                continue
            except Exception as exc:
                await replace_after_error(exc)
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
            await _discard_prepared_task(prepared)
        if current is not None:
            await current.close()
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()
        main.logger.info("Dauerhafter TS-Proxy geschlossen: Session=%s", session_id)


def install() -> None:
    safari_hls_fix.run_live_ts_proxy = run_live_ts_proxy_v2
