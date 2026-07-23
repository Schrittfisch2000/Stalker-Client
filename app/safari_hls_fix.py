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
from .live_ts_proxy import run_live_ts_proxy
from .stalker import StalkerClient

_vod_seek_offsets: dict[str, float] = {}


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


def _ffmpeg_command(
    media_type: str,
    directory: Path,
    playlist: Path,
    start_number: int,
) -> list[str]:
    live = media_type == "itv"
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "warning"]

    if live:
        command += [
            "-thread_queue_size", "8192",
            "-fflags", "+genpts+discardcorrupt+igndts",
            "-use_wallclock_as_timestamps", "1",
            "-probesize", "2000000",
            "-analyzeduration", "2000000",
            "-f", "mpegts",
            "-i", "pipe:0",
        ]
    else:
        raise RuntimeError("Non-live command requires a direct URL")

    command += [
        "-map", "0:v:0?", "-map", "0:a:0?", "-sn", "-dn",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-profile:v", "main", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-sc_threshold", "0", "-force_key_frames", "expr:gte(t,n_forced*1)",
        "-c:a", "aac", "-profile:a", "aac_low", "-ar", "48000", "-ac", "2", "-b:a", "128k",
        "-max_muxing_queue_size", "2048",
        "-avoid_negative_ts", "make_zero",
        "-f", "hls", "-hls_time", "1",
        "-start_number", str(start_number),
        "-hls_segment_filename", str(directory / "segment-%06d.ts"),
        "-hls_list_size", "24",
        "-hls_delete_threshold", "8",
        "-hls_flags", "append_list+omit_endlist+independent_segments+temp_file+program_date_time",
        str(playlist),
    ]
    return command


async def _start_live_ffmpeg(
    session_id: str,
    data: dict[str, Any],
    settings: Settings,
    portal: StalkerClient,
    directory: Path,
    playlist: Path,
) -> tuple[asyncio.subprocess.Process, asyncio.Task[None]]:
    start_number = _next_segment_number(directory)
    command = _ffmpeg_command("itv", directory, playlist, start_number)
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail="FFmpeg is not available") from exc

    proxy_task = asyncio.create_task(run_live_ts_proxy(session_id, data, settings, portal, process))
    asyncio.create_task(main.log_ffmpeg(session_id, process))
    main.logger.info(
        "FFmpeg-HLS mit dauerhaftem TS-Proxy gestartet: Session=%s, Typ=itv, Startsegment=%s",
        session_id,
        start_number,
    )
    return process, proxy_task


async def _start_direct_ffmpeg(
    session_id: str,
    data: dict[str, Any],
    portal: StalkerClient,
    directory: Path,
    playlist: Path,
) -> asyncio.subprocess.Process:
    start_number = _next_segment_number(directory)
    headers = portal.portal_headers_for_stream()
    headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in portal.cookies.items())
    ffmpeg_headers = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    seek_offset = max(0.0, _vod_seek_offsets.get(session_id, 0.0))
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-rw_timeout", "20000000", "-headers", ffmpeg_headers,
        "-probesize", "1000000", "-analyzeduration", "1000000",
    ]
    if seek_offset:
        command += ["-ss", f"{seek_offset:.3f}"]
    command += [
        "-i", str(data["url"]),
        "-af", "aresample=async=1000:first_pts=0",
        "-map", "0:v:0?", "-map", "0:a:0?", "-sn", "-dn",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-profile:v", "main", "-level", "4.0", "-pix_fmt", "yuv420p",
        "-sc_threshold", "0", "-force_key_frames", "expr:gte(t,n_forced*1)",
        "-c:a", "aac", "-profile:a", "aac_low", "-ar", "48000", "-ac", "2", "-b:a", "128k",
        "-max_muxing_queue_size", "2048",
        "-avoid_negative_ts", "make_zero",
        "-f", "hls", "-hls_time", "1",
        "-start_number", str(start_number),
        "-hls_segment_filename", str(directory / "segment-%06d.ts"),
        "-hls_playlist_type", "event",
        "-hls_list_size", "0",
        "-hls_flags", "append_list+independent_segments+temp_file",
        str(playlist),
    ]
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
        "FFmpeg-HLS gestartet: Session=%s, Typ=%s, Start=%.3fs",
        session_id,
        data["media_type"],
        seek_offset,
    )
    return process


def _duration_from_item(item: dict[str, Any]) -> float | None:
    for key in ("duration", "video_duration", "movie_length", "length"):
        try:
            duration = float(item.get(key))
        except (TypeError, ValueError):
            continue
        if duration >= 60:
            return duration

    for key in ("time", "runtime"):
        raw_value = item.get(key)
        try:
            minutes = float(raw_value)
        except (TypeError, ValueError):
            minutes = 0
        if 10 <= minutes <= 600:
            return minutes * 60

        value = str(raw_value or "").strip()
        if ":" not in value:
            continue
        try:
            parts = [float(part) for part in value.split(":")]
        except ValueError:
            continue
        if len(parts) == 2:
            duration = parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            duration = parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            continue
        if duration >= 60:
            return duration
    return None


def _play_response(playback_url: str, duration: float | None, seekable: bool) -> dict[str, str]:
    return {
        "url": playback_url,
        "stream_type": "hls",
        "duration": f"{duration:.3f}" if duration else "",
        "seekable": "true" if seekable else "false",
    }


async def _probe_duration(url: str, portal: StalkerClient) -> float | None:
    headers = portal.portal_headers_for_stream()
    headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in portal.cookies.items())
    ffmpeg_headers = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    command = [
        "ffprobe", "-v", "error", "-rw_timeout", "10000000",
        "-headers", ffmpeg_headers,
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        url,
    ]
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=12)
        duration = float(stdout.decode("utf-8", errors="replace").strip())
    except (OSError, ValueError, asyncio.TimeoutError):
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        return None
    return duration if duration >= 60 else None


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
        main.shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)

        if media_type == "itv":
            process, proxy_task = await _start_live_ffmpeg(
                session_id, data, settings, portal, directory, playlist
            )
        else:
            process = await _start_direct_ffmpeg(session_id, data, portal, directory, playlist)
            proxy_task = None

        main._hls_sessions[session_id] = {
            "process": process,
            "proxy_task": proxy_task,
            "directory": directory,
            "last_access": time.time(),
            "started_at": time.time(),
            "media_type": media_type,
        }
    return session_id, playlist


async def _refresh_live_ticket(
    ticket: str,
    settings: Settings = Depends(main.settings_dependency),
    portal: StalkerClient = Depends(main.client),
) -> dict[str, str]:
    data = _read_ticket(ticket, settings)
    if data.get("media_type") != "itv":
        raise HTTPException(status_code=400, detail="Live-TV ticket required")
    session_id, _ = await _ensure_hls_session(ticket, settings, portal)
    main.logger.info("Live-Refresh ignoriert; dauerhafter TS-Proxy ist aktiv: Session=%s", session_id)
    return {"url": f"/hls/{ticket}/index.m3u8", "ready": "true", "persistent_proxy": "true"}


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
    duration = None
    if media_type in {"vod", "series"}:
        duration = _duration_from_item(item) or await _probe_duration(url, portal)
    main.logger.info(
        "Wiedergabe vorbereitet: Typ=%s, Format=%s",
        media_type,
        "direct-hls" if main.is_hls(url) else ("ts-proxy-hls" if media_type == "itv" else "ffmpeg-hls"),
    )
    return _play_response(
        playback_url,
        round(duration, 3) if duration else None,
        bool(duration and not main.is_hls(url)),
    )


async def _seek_vod(
    ticket: str,
    payload: dict[str, Any],
    settings: Settings = Depends(main.settings_dependency),
) -> dict[str, Any]:
    data = _read_ticket(ticket, settings)
    if data.get("media_type") not in {"vod", "series"}:
        raise HTTPException(status_code=400, detail="Film- oder Serien-Ticket erforderlich")
    try:
        position = max(0.0, float(payload.get("position", 0)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Ungültige Wiedergabeposition") from exc

    session_id = main.session_id_for(ticket)
    session = main._hls_sessions.get(session_id)
    if session is not None:
        from .live_runtime_fix import stop_hls_session
        await stop_hls_session(session_id, session)
    _vod_seek_offsets[session_id] = position
    main.logger.info("VOD-Sprung vorbereitet: Session=%s, Position=%.3fs", session_id, position)
    return {
        "url": f"/hls/{ticket}/index.m3u8?_seek={int(time.time() * 1000)}",
        "position": position,
    }


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
    if not any(getattr(route, "path", None) == "/api/vod-seek/{ticket}" for route in main.app.routes):
        main.app.add_api_route("/api/vod-seek/{ticket}", _seek_vod, methods=["POST"])

    for route in main.app.routes:
        if getattr(route, "path", None) == "/api/play" and "POST" in getattr(route, "methods", set()):
            route.endpoint = _play
            if getattr(route, "dependant", None) is not None:
                route.dependant.call = _play
            break
