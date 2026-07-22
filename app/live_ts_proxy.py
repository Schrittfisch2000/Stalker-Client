from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import main
from .config import Settings
from .stalker import StalkerClient

TS_PACKET_SIZE = 188
PTS_WRAP = 1 << 33
PCR_WRAP = PTS_WRAP * 300
PREPARE_REPLACEMENT_AFTER_SECONDS = 32.0
MAX_CONNECTION_AGE_SECONDS = 42.0
RECONNECT_DELAY_SECONDS = 0.5
REPLACEMENT_WARMUP_TIMEOUT_SECONDS = 8.0
MAX_WARMUP_PACKETS = 12000
TIMELINE_GAP_90KHZ = 9000
MIN_PACKETS_AFTER_KEYFRAME = 32


@dataclass
class UpstreamConnection:
    client: httpx.AsyncClient
    response: httpx.Response
    iterator: Any
    opened_at: float
    url: str
    pending: bytearray

    async def close(self) -> None:
        await self.response.aclose()
        await self.client.aclose()


@dataclass
class PreparedReplacement:
    connection: UpstreamConnection
    packets: list[bytes]
    source_anchor: int | None
    keyframe_found: bool


@dataclass
class TsTimelineNormalizer:
    continuity: dict[int, int] = field(default_factory=dict)
    pmt_pid: int | None = None
    video_pids: set[int] = field(default_factory=set)
    psi_packets: dict[int, bytes] = field(default_factory=dict)
    timestamp_offset: int = 0
    last_output_pts: int | None = None
    last_output_pcr: int | None = None
    switch_pending: bool = False

    def begin_switch(self, source_anchor: int | None) -> None:
        if self.last_output_pts is not None and source_anchor is None:
            raise ValueError("replacement stream has no video PTS anchor")
        if source_anchor is None or self.last_output_pts is None:
            self.timestamp_offset = 0
        else:
            target = (self.last_output_pts + TIMELINE_GAP_90KHZ) % PTS_WRAP
            self.timestamp_offset = (target - source_anchor) % PTS_WRAP
        self.switch_pending = True

    def normalize(self, packet: bytes) -> bytes:
        if len(packet) != TS_PACKET_SIZE or packet[0] != 0x47:
            return b""
        data = bytearray(packet)
        pid = ((data[1] & 0x1F) << 8) | data[2]
        payload_start = bool(data[1] & 0x40)
        adaptation_control = (data[3] >> 4) & 0x03
        has_payload = adaptation_control in (1, 3)

        if has_payload:
            next_cc = (self.continuity.get(pid, -1) + 1) & 0x0F
            data[3] = (data[3] & 0xF0) | next_cc
            self.continuity[pid] = next_cc

        payload_offset = self._payload_offset(data)
        self._track_program_tables(data, pid, payload_start, payload_offset)
        self._rewrite_pcr(data, adaptation_control)
        self._rewrite_pes_timestamps(data, pid, payload_start, payload_offset)

        if pid == 0 or pid == self.pmt_pid:
            self.psi_packets[pid] = bytes(data)
        return bytes(data)

    def reinjected_psi(self) -> bytes:
        packets: list[bytes] = []
        for pid in (0, self.pmt_pid):
            if pid is None or pid not in self.psi_packets:
                continue
            packet = bytearray(self.psi_packets[pid])
            adaptation_control = (packet[3] >> 4) & 0x03
            if adaptation_control in (1, 3):
                next_cc = (self.continuity.get(pid, -1) + 1) & 0x0F
                packet[3] = (packet[3] & 0xF0) | next_cc
                self.continuity[pid] = next_cc
            packets.append(bytes(packet))
        return b"".join(packets)

    @staticmethod
    def _payload_offset(packet: bytearray | bytes) -> int | None:
        adaptation_control = (packet[3] >> 4) & 0x03
        if adaptation_control not in (1, 3):
            return None
        offset = 4
        if adaptation_control == 3:
            adaptation_length = packet[4]
            offset = 5 + adaptation_length
        return offset if offset < TS_PACKET_SIZE else None

    def _track_program_tables(
        self,
        packet: bytearray,
        pid: int,
        payload_start: bool,
        payload_offset: int | None,
    ) -> None:
        if not payload_start or payload_offset is None or payload_offset >= TS_PACKET_SIZE:
            return
        pointer = packet[payload_offset]
        section_start = payload_offset + 1 + pointer
        if section_start + 3 >= TS_PACKET_SIZE:
            return
        table_id = packet[section_start]
        if pid == 0 and table_id == 0x00:
            section_length = ((packet[section_start + 1] & 0x0F) << 8) | packet[section_start + 2]
            end = min(section_start + 3 + section_length - 4, TS_PACKET_SIZE)
            pos = section_start + 8
            while pos + 4 <= end:
                program = (packet[pos] << 8) | packet[pos + 1]
                mapped_pid = ((packet[pos + 2] & 0x1F) << 8) | packet[pos + 3]
                if program != 0:
                    self.pmt_pid = mapped_pid
                    break
                pos += 4
        elif self.pmt_pid is not None and pid == self.pmt_pid and table_id == 0x02:
            section_length = ((packet[section_start + 1] & 0x0F) << 8) | packet[section_start + 2]
            section_end = min(section_start + 3 + section_length - 4, TS_PACKET_SIZE)
            program_info_length = ((packet[section_start + 10] & 0x0F) << 8) | packet[section_start + 11]
            pos = section_start + 12 + program_info_length
            video_pids: set[int] = set()
            while pos + 5 <= section_end:
                stream_type = packet[pos]
                elementary_pid = ((packet[pos + 1] & 0x1F) << 8) | packet[pos + 2]
                es_info_length = ((packet[pos + 3] & 0x0F) << 8) | packet[pos + 4]
                if stream_type in {0x01, 0x02, 0x1B, 0x24, 0x10}:
                    video_pids.add(elementary_pid)
                pos += 5 + es_info_length
            if video_pids:
                self.video_pids = video_pids

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
        pcr = (base * 300 + extension + self.timestamp_offset * 300) % PCR_WRAP
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
        if not payload_start or payload_offset is None or payload_offset + 14 > TS_PACKET_SIZE:
            return
        if packet[payload_offset:payload_offset + 3] != b"\x00\x00\x01":
            return
        flags = (packet[payload_offset + 7] >> 6) & 0x03
        pos = payload_offset + 9
        if flags in (2, 3) and pos + 5 <= TS_PACKET_SIZE:
            pts = _decode_timestamp(packet, pos)
            rewritten = (pts + self.timestamp_offset) % PTS_WRAP
            _encode_timestamp(packet, pos, rewritten, packet[pos] >> 4)
            self.last_output_pts = rewritten
            if flags == 3 and pos + 10 <= TS_PACKET_SIZE:
                dts = _decode_timestamp(packet, pos + 5)
                _encode_timestamp(packet, pos + 5, (dts + self.timestamp_offset) % PTS_WRAP, packet[pos + 5] >> 4)
        if self.switch_pending and pid in self.video_pids:
            self.switch_pending = False


def _decode_timestamp(packet: bytearray | bytes, pos: int) -> int:
    return (
        ((packet[pos] >> 1) & 0x07) << 30
        | packet[pos + 1] << 22
        | ((packet[pos + 2] >> 1) & 0x7F) << 15
        | packet[pos + 3] << 7
        | ((packet[pos + 4] >> 1) & 0x7F)
    )


def _encode_timestamp(packet: bytearray, pos: int, value: int, prefix: int) -> None:
    value %= PTS_WRAP
    packet[pos] = ((prefix & 0x0F) << 4) | (((value >> 30) & 0x07) << 1) | 1
    packet[pos + 1] = (value >> 22) & 0xFF
    packet[pos + 2] = (((value >> 15) & 0x7F) << 1) | 1
    packet[pos + 3] = (value >> 7) & 0xFF
    packet[pos + 4] = ((value & 0x7F) << 1) | 1


def _packet_pid(packet: bytes) -> int:
    return ((packet[1] & 0x1F) << 8) | packet[2]


def _packet_source_pts(packet: bytes) -> int | None:
    if len(packet) != TS_PACKET_SIZE or packet[0] != 0x47 or not (packet[1] & 0x40):
        return None
    offset = TsTimelineNormalizer._payload_offset(packet)
    if offset is None or offset + 14 > TS_PACKET_SIZE or packet[offset:offset + 3] != b"\x00\x00\x01":
        return None
    flags = (packet[offset + 7] >> 6) & 0x03
    if flags not in (2, 3):
        return None
    return _decode_timestamp(packet, offset + 9)


def _select_switch_anchor(packets: list[bytes], video_pids: set[int]) -> int | None:
    if video_pids:
        for packet in packets:
            if _packet_pid(packet) in video_pids:
                pts = _packet_source_pts(packet)
                if pts is not None:
                    return pts
    return next((_packet_source_pts(packet) for packet in packets if _packet_source_pts(packet) is not None), None)


def _contains_random_access(packet: bytes, video_pids: set[int]) -> bool:
    if len(packet) != TS_PACKET_SIZE or packet[0] != 0x47:
        return False
    pid = _packet_pid(packet)
    if video_pids and pid not in video_pids:
        return False
    adaptation_control = (packet[3] >> 4) & 0x03
    if adaptation_control in (2, 3) and packet[4] >= 1 and packet[5] & 0x40:
        return True
    if not (packet[1] & 0x40):
        return False
    offset = TsTimelineNormalizer._payload_offset(packet)
    if offset is None or offset + 9 >= TS_PACKET_SIZE:
        return False
    if packet[offset:offset + 3] != b"\x00\x00\x01":
        return False
    header_length = packet[offset + 8]
    payload = packet[offset + 9 + header_length:]
    for marker in (b"\x00\x00\x01\x65", b"\x00\x00\x00\x01\x65"):
        if marker in payload:
            return True
    return False


async def _open_upstream(url: str, settings: Settings, portal: StalkerClient) -> UpstreamConnection:
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=15.0, read=None, write=15.0, pool=15.0),
        verify=settings.verify_tls,
        follow_redirects=True,
    )
    headers = portal.portal_headers_for_stream()
    request = client.build_request("GET", url, headers=headers, cookies=portal.cookies)
    try:
        response = await client.send(request, stream=True)
        response.raise_for_status()
    except Exception:
        await client.aclose()
        raise
    return UpstreamConnection(
        client=client,
        response=response,
        iterator=response.aiter_raw(64 * 1024),
        opened_at=time.monotonic(),
        url=url,
        pending=bytearray(),
    )


def _aligned_ts_payload(connection: UpstreamConnection, chunk: bytes) -> bytes:
    connection.pending.extend(chunk)
    data = connection.pending
    if not data:
        return b""
    if data[0] != 0x47:
        sync = data.find(b"\x47")
        while sync >= 0 and len(data) >= sync + (TS_PACKET_SIZE * 2):
            if data[sync + TS_PACKET_SIZE] == 0x47:
                del data[:sync]
                break
            sync = data.find(b"\x47", sync + 1)
        else:
            if len(data) > TS_PACKET_SIZE * 3:
                del data[:-TS_PACKET_SIZE * 2]
            return b""
    packet_bytes = (len(data) // TS_PACKET_SIZE) * TS_PACKET_SIZE
    if packet_bytes <= 0:
        return b""
    payload = bytes(data[:packet_bytes])
    del data[:packet_bytes]
    return payload


def _split_packets(payload: bytes) -> list[bytes]:
    return [payload[pos:pos + TS_PACKET_SIZE] for pos in range(0, len(payload), TS_PACKET_SIZE)]


async def _fresh_url(data: dict[str, Any], portal: StalkerClient) -> str:
    playback = data.get("playback")
    if not playback:
        return str(data["url"])
    command = str(playback.get("cmd", ""))
    series = playback.get("series")
    item = playback.get("item") if isinstance(playback.get("item"), dict) else {}
    if not command:
        return str(data["url"])
    return await portal.create_link(
        str(data.get("media_type", "itv")), command,
        str(series) if series is not None else None, item,
    )


async def _warm_replacement(
    data: dict[str, Any], settings: Settings, portal: StalkerClient, normalizer: TsTimelineNormalizer,
) -> PreparedReplacement:
    connection = await _open_upstream(await _fresh_url(data, portal), settings, portal)
    packets: list[bytes] = []
    keyframe_index: int | None = None
    source_anchor: int | None = None
    deadline = time.monotonic() + REPLACEMENT_WARMUP_TIMEOUT_SECONDS
    try:
        while time.monotonic() < deadline and len(packets) < MAX_WARMUP_PACKETS:
            chunk = await asyncio.wait_for(connection.iterator.__anext__(), timeout=2.0)
            for packet in _split_packets(_aligned_ts_payload(connection, chunk)):
                packets.append(packet)
                if keyframe_index is None and _contains_random_access(packet, normalizer.video_pids):
                    keyframe_index = len(packets) - 1
                if keyframe_index is not None:
                    switch_packets = packets[keyframe_index:]
                    source_anchor = _select_switch_anchor(switch_packets, normalizer.video_pids)
                    enough_context = len(switch_packets) >= MIN_PACKETS_AFTER_KEYFRAME
                    if source_anchor is not None and enough_context:
                        break
            if keyframe_index is not None and source_anchor is not None and len(packets) - keyframe_index >= MIN_PACKETS_AFTER_KEYFRAME:
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
    while start > 0 and _packet_pid(packets[start - 1]) in {0, normalizer.pmt_pid}:
        start -= 1
    packets = packets[start:]
    source_anchor = _select_switch_anchor(packets, normalizer.video_pids)
    if normalizer.last_output_pts is not None and source_anchor is None:
        await connection.close()
        raise RuntimeError("replacement stream contained no video PTS after random-access point")
    return PreparedReplacement(connection, packets, source_anchor, True)


async def run_live_ts_proxy(
    session_id: str,
    data: dict[str, Any],
    settings: Settings,
    portal: StalkerClient,
    process: asyncio.subprocess.Process,
) -> None:
    if process.stdin is None:
        main.logger.error("TS-Proxy ohne FFmpeg-stdin gestartet: Session=%s", session_id)
        return

    current: UpstreamConnection | None = None
    prepared: asyncio.Task[PreparedReplacement] | None = None
    reconnects = 0
    normalizer = TsTimelineNormalizer()

    async def switch_to(replacement: PreparedReplacement) -> None:
        nonlocal current, reconnects
        normalizer.begin_switch(replacement.source_anchor)
        previous = current
        current = replacement.connection
        prefix = normalizer.reinjected_psi()
        payload = prefix + b"".join(filter(None, (normalizer.normalize(packet) for packet in replacement.packets)))
        if payload:
            process.stdin.write(payload)
            await process.stdin.drain()
        if previous is not None:
            await previous.close()
        reconnects += 1
        main.logger.info(
            "TS-Proxy auf normalisierter Zeitachse gewechselt: Session=%s, Wechsel=%s, Keyframe=%s, Pufferpakete=%s, Anker=%s",
            session_id, reconnects, replacement.keyframe_found, len(replacement.packets), replacement.source_anchor,
        )

    try:
        current = await _open_upstream(str(data["url"]), settings, portal)
        main.logger.info("Dauerhafter TS-Proxy mit Zeitachsen-Normalisierung verbunden: Session=%s", session_id)

        while process.returncode is None:
            age = time.monotonic() - current.opened_at
            if prepared is None and age >= PREPARE_REPLACEMENT_AFTER_SECONDS:
                prepared = asyncio.create_task(_warm_replacement(data, settings, portal, normalizer))

            if prepared is not None and prepared.done():
                try:
                    replacement = prepared.result()
                except Exception as exc:
                    main.logger.warning("TS-Proxy-Ersatzverbindung fehlgeschlagen: Session=%s, Fehler=%s", session_id, exc)
                    prepared = None
                else:
                    prepared = None
                    await switch_to(replacement)
                    continue

            if age >= MAX_CONNECTION_AGE_SECONDS and prepared is not None:
                try:
                    replacement = await asyncio.wait_for(prepared, timeout=REPLACEMENT_WARMUP_TIMEOUT_SECONDS)
                except Exception as exc:
                    main.logger.warning("TS-Proxy-Zwangswechsel fehlgeschlagen: Session=%s, Fehler=%s", session_id, exc)
                    prepared = None
                else:
                    prepared = None
                    await switch_to(replacement)
                    continue

            try:
                chunk = await current.iterator.__anext__()
            except (StopAsyncIteration, Exception) as exc:
                if isinstance(exc, asyncio.CancelledError):
                    raise
                main.logger.warning("TS-Proxy-Upstream wird erneuert: Session=%s, Fehler=%s", session_id, exc)
                if prepared is None:
                    prepared = asyncio.create_task(_warm_replacement(data, settings, portal, normalizer))
                try:
                    replacement = await prepared
                except Exception as reconnect_exc:
                    main.logger.warning("TS-Proxy-Neuverbindung fehlgeschlagen: Session=%s, Fehler=%s", session_id, reconnect_exc)
                    prepared = None
                    await asyncio.sleep(RECONNECT_DELAY_SECONDS)
                    continue
                prepared = None
                await switch_to(replacement)
                continue

            payload = _aligned_ts_payload(current, chunk)
            if not payload:
                continue
            normalized = b"".join(filter(None, (normalizer.normalize(packet) for packet in _split_packets(payload))))
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
