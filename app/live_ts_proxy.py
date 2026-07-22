from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from . import main
from .config import Settings
from .stalker import StalkerClient

TS_PACKET_SIZE = 188
PREPARE_REPLACEMENT_AFTER_SECONDS = 32.0
MAX_CONNECTION_AGE_SECONDS = 42.0
RECONNECT_DELAY_SECONDS = 0.5


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
        str(data.get("media_type", "itv")),
        command,
        str(series) if series is not None else None,
        item,
    )


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
    prepared: asyncio.Task[UpstreamConnection] | None = None
    reconnects = 0

    async def prepare_replacement() -> UpstreamConnection:
        fresh_url = await _fresh_url(data, portal)
        return await _open_upstream(fresh_url, settings, portal)

    try:
        current = await _open_upstream(str(data["url"]), settings, portal)
        main.logger.info("Dauerhafter TS-Proxy verbunden: Session=%s", session_id)

        while process.returncode is None:
            age = time.monotonic() - current.opened_at
            if prepared is None and age >= PREPARE_REPLACEMENT_AFTER_SECONDS:
                prepared = asyncio.create_task(prepare_replacement())

            if prepared is not None and prepared.done():
                try:
                    replacement = prepared.result()
                except Exception as exc:
                    main.logger.warning("TS-Proxy-Ersatzverbindung fehlgeschlagen: Session=%s, Fehler=%s", session_id, exc)
                    prepared = None
                else:
                    await current.close()
                    current = replacement
                    prepared = None
                    reconnects += 1
                    main.logger.info(
                        "TS-Proxy nahtlos auf frischen Portal-Token gewechselt: Session=%s, Wechsel=%s",
                        session_id,
                        reconnects,
                    )
                    continue

            if age >= MAX_CONNECTION_AGE_SECONDS and prepared is not None:
                try:
                    replacement = await asyncio.wait_for(prepared, timeout=8.0)
                except Exception as exc:
                    main.logger.warning("TS-Proxy-Zwangswechsel fehlgeschlagen: Session=%s, Fehler=%s", session_id, exc)
                    prepared = None
                else:
                    await current.close()
                    current = replacement
                    prepared = None
                    reconnects += 1
                    main.logger.info(
                        "TS-Proxy auf frischen Portal-Token gewechselt: Session=%s, Wechsel=%s",
                        session_id,
                        reconnects,
                    )
                    continue

            try:
                chunk = await current.iterator.__anext__()
            except StopAsyncIteration:
                main.logger.info("TS-Proxy-Upstream beendet; Verbindung wird erneuert: Session=%s", session_id)
                if prepared is None:
                    prepared = asyncio.create_task(prepare_replacement())
                try:
                    replacement = await prepared
                except Exception as exc:
                    main.logger.warning("TS-Proxy-Neuverbindung fehlgeschlagen: Session=%s, Fehler=%s", session_id, exc)
                    prepared = None
                    await asyncio.sleep(RECONNECT_DELAY_SECONDS)
                    continue
                await current.close()
                current = replacement
                prepared = None
                reconnects += 1
                continue
            except Exception as exc:
                main.logger.warning("TS-Proxy-Lesefehler: Session=%s, Fehler=%s", session_id, exc)
                if prepared is None:
                    prepared = asyncio.create_task(prepare_replacement())
                try:
                    replacement = await prepared
                except Exception:
                    prepared = None
                    await asyncio.sleep(RECONNECT_DELAY_SECONDS)
                    continue
                await current.close()
                current = replacement
                prepared = None
                reconnects += 1
                continue

            payload = _aligned_ts_payload(current, chunk)
            if not payload:
                continue
            process.stdin.write(payload)
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
                await prepared
            except (asyncio.CancelledError, Exception):
                pass
        if current is not None:
            await current.close()
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()
        main.logger.info("Dauerhafter TS-Proxy geschlossen: Session=%s", session_id)
