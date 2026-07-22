from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException

from . import main
from .config import Settings
from .stalker import StalkerClient


PREWARM_SEGMENTS = 3
PREWARM_TIMEOUT_SECONDS = 18


def _create_ticket(
    url: str,
    settings: Settings,
    media_type: str = "",
    playback: dict[str, Any] | None = None,
) -> str:
    parsed = main.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=502, detail="Portal returned an unsupported stream URL")
    data: dict[str, Any] = {"u": url, "m": media_type, "e": int(time.time()) + 7200}
    if playback:
        data["p"] = playback
    payload = main._b64encode(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode())
    signature = main._b64encode(
        main.hmac.new(settings.app_secret.encode(), payload.encode(), hashlib.sha256).digest()
    )
    return f"{payload}.{signature}"


def _read_ticket(ticket: str, settings: Settings) -> dict[str, Any]:
    try:
        payload, signature = ticket.split(".", 1)
        expected = main._b64encode(
            main.hmac.new(settings.app_secret.encode(), payload.encode(), hashlib.sha256).digest()
        )
        if not main.hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        data = json.loads(main._b64decode(payload))
        if int(data["e"]) < int(time.time()):
            raise ValueError("expired")
        url = str(data["u"])
        parsed = main.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url")
        playback = data.get("p") if isinstance(data.get("p"), dict) else None
        return {"url": url, "media_type": str(data.get("m", "")), "playback": playback}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        main.logger.warning("Ungültiges oder abgelaufenes Stream-Ticket")
        raise HTTPException(status_code=403, detail="Invalid or expired stream ticket") from exc


def _next_segment_number(directory: Path) -> int:
    highest = -1
    for path in directory.glob("segment-*.ts"):
        match = re.fullmatch(r"segment-(\d{6})\.ts", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


async def _renew_stream_url(data: dict[str, Any], portal: StalkerClient) -> str:
    playback = data.get("playback")
    if not playback:
        return str(data["url"])
    command_value = str(playback.get("cmd", ""))
    series = playback.get("series")
    item = playback.get("item") if isinstance(playback.get("item"), dict) else {}
    if not command_value:
        return str(data["url"])
    return await portal.create_link(
        str(data["media_type"]),
        command_value,
        str(series) if series is not None else None,
        item,
    )


def _ffmpeg_command(
    url: str,
    media_type: str,
    directory: Path,
    playlist: Path,
    portal: StalkerClient,
    start_number: int,
    restarting: bool,
) -> list[str]:
    live = media_type == "itv"
    headers = portal.portal_headers_for_stream()
    headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in portal.cookies.items())
    ffmpeg_headers = "".join(f"{key}: {value}\r\n" for key, value in headers.items())

    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-rw_timeout", "20000000", "-headers", ffmpeg_headers,
        "-probesize", "1000000", "-analyzeduration", "1000000",
    ]
    if live:
        command += ["-re", "-fflags", "+genpts+discardcorrupt"]
    command += [
        "-i", url,
        "-map", "0:v:0?", "-map", "0:a:0?", "-sn", "-dn",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-profile:v", "main", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-sc_threshold", "0", "-force_key_frames", "expr:gte(t,n_forced*1)",
        "-c:a", "aac", "-profile:a", "aac_low", "-ar", "48000", "-ac", "2", "-b:a", "128k",
        "-max_muxing_queue_size", "2048",
        "-avoid_negative_ts", "make_zero",
        "-f", "hls", "-hls_init_time", "1", "-hls_time", "1",
        "-start_number", str(start_number),
        "-hls_segment_filename", str(directory / "segment-%06d.ts"),
    ]
    if live:
        flags = "append_list+omit_endlist+independent_segments+temp_file+program_date_time"
        if restarting:
            flags += "+discont_start"
        command += [
            "-hls_list_size", "24",
            "-hls_delete_threshold", "8",
            "-hls_flags", flags,
        ]
    else:
        command += [
            "-hls_playlist_type", "event",
            "-hls_list_size", "0",
            "-hls_flags", "append_list+independent_segments+temp_file",
        ]
    command.append(str(playlist))
    return command


async def _start_ffmpeg(
    session_id: str,
    data: dict[str, Any],
    portal: StalkerClient,
    directory: Path,
    playlist: Path,
    restarting: bool,
) -> asyncio.subprocess.Process:
    start_number = _next_segment_number(directory)
    command = _ffmpeg_command(
        str(data["url"]), str(data["media_type"]), directory, playlist,
        portal, start_number, restarting,
    )
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail="FFmpeg is not available") from exc

    asyncio.create_task(main.log_ffmpeg(session_id, process))
    main.logger.info(
        "FFmpeg-HLS %s: Session=%s, Typ=%s, Startsegment=%s",
        "neu gestartet" if restarting else "gestartet",
        session_id,
        data["media_type"],
        start_number,
    )
    return process


async def _wait_until_ready(
    session_id: str,
    directory: Path,
    playlist: Path,
    process: asyncio.subprocess.Process,
) -> None:
    deadline = time.monotonic() + PREWARM_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.returncode is not None:
            raise HTTPException(status_code=502, detail="Replacement stream stopped during startup")
        segments = list(directory.glob("segment-*.ts"))
        if playlist.exists() and len(segments) >= PREWARM_SEGMENTS:
            main.logger.info(
                "Safari-HLS-Ersatzsession bereit: Session=%s, Segmente=%s",
                session_id,
                len(segments),
            )
            return
        await asyncio.sleep(0.25)
    raise HTTPException(status_code=504, detail="Replacement stream did not become ready in time")


async def _refresh_live_ticket(
    ticket: str,
    settings: Settings = Depends(main.settings_dependency),
    portal: StalkerClient = Depends(main.client),
) -> dict[str, str]:
    data = _read_ticket(ticket, settings)
    if data.get("media_type") != "itv" or not data.get("playback"):
        raise HTTPException(status_code=400, detail="Live-TV ticket required")

    fresh_url = await _renew_stream_url(data, portal)
    fresh_ticket = _create_ticket(fresh_url, settings, "itv", data["playback"])
    session_id, playlist = await _ensure_hls_session(fresh_ticket, settings, portal)
    session = main._hls_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=502, detail="Replacement session was not created")

    await _wait_until_ready(
        session_id,
        Path(session["directory"]),
        playlist,
        session["process"],
    )
    session["last_access"] = time.time()
    main.logger.info("Vorgewärmte Safari-HLS-Session ausgeliefert: Session=%s", session_id)
    return {"url": f"/hls/{fresh_ticket}/index.m3u8", "ready": "true"}


async def _ensure_hls_session(
    ticket: str,
    settings: Settings,
    portal: StalkerClient,
) -> tuple[str, Path]:
    session_id = main.session_id_for(ticket)
    directory = main.HLS_ROOT / session_id
    playlist = directory / "index.m3u8"

    async with main._hls_lock:
        current = main._hls_sessions.get(session_id)
        if current and current["process"].returncode is None:
            current["last_access"] = time.time()
            return session_id, playlist

        data = _read_ticket(ticket, settings)
        media_type = data["media_type"]
        restarting = current is not None

        if restarting:
            data["url"] = await _renew_stream_url(data, portal)
            main.logger.info("HLS-Link mit frischem Portal-Token erneuert: Session=%s", session_id)
        else:
            main.shutil.rmtree(directory, ignore_errors=True)

        directory.mkdir(parents=True, exist_ok=True)
        process = await _start_ffmpeg(session_id, data, portal, directory, playlist, restarting)
        main._hls_sessions[session_id] = {
            "process": process,
            "directory": directory,
            "last_access": time.time(),
            "started_at": time.time(),
            "media_type": media_type,
        }
    return session_id, playlist


async def _play(payload: dict[str, Any], settings: Settings, portal: StalkerClient) -> dict[str, str]:
    media_type = str(payload.get("type", ""))
    command = str(payload.get("cmd", ""))
    series = payload.get("series")
    item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
    if media_type not in {"itv", "vod", "series"} or not command:
        raise HTTPException(status_code=400, detail="type and cmd are required")

    url = await portal.create_link(media_type, command, str(series) if series is not None else None, item)
    playback = {"cmd": command, "series": series, "item": item}
    ticket = _create_ticket(url, settings, media_type, playback)
    if main.is_hls(url):
        playback_url = f"/stream/{ticket}"
    else:
        playback_url = f"/hls/{ticket}/index.m3u8"
    main.logger.info(
        "Wiedergabe vorbereitet: Typ=%s, Format=%s",
        media_type,
        "direct-hls" if main.is_hls(url) else "ffmpeg-hls",
    )
    return {"url": playback_url, "stream_type": "hls"}


def install() -> None:
    main.create_ticket = _create_ticket
    main.read_ticket = _read_ticket
    main.ensure_hls_session = _ensure_hls_session

    if not any(getattr(route, "path", None) == "/api/live-refresh/{ticket}" for route in main.app.routes):
        main.app.add_api_route(
            "/api/live-refresh/{ticket}",
            _refresh_live_ticket,
            methods=["POST"],
        )

    for route in main.app.routes:
        if getattr(route, "path", None) == "/api/play" and "POST" in getattr(route, "methods", set()):
            route.endpoint = _play
            if getattr(route, "dependant", None) is not None:
                route.dependant.call = _play
            break
