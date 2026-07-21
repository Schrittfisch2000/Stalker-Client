from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .config import PortalConfig, Settings, get_settings, load_portal_config, save_portal_config
from .logging_config import configure_logging, masked_mac
from .stalker import PortalError, StalkerClient

BASE_DIR = Path(__file__).resolve().parent
HLS_ROOT = Path("/tmp/stalker-client-hls")
HLS_ROOT.mkdir(parents=True, exist_ok=True)
logger = configure_logging()
app = FastAPI(title="Stalker Client", version="0.5.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
_hls_sessions: dict[str, dict[str, Any]] = {}
_hls_lock = asyncio.Lock()
_cleanup_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup_event() -> None:
    global _cleanup_task
    logger.info("Stalker Client gestartet")
    _cleanup_task = asyncio.create_task(cleanup_hls_sessions())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if _cleanup_task:
        _cleanup_task.cancel()
    for session in list(_hls_sessions.values()):
        process = session.get("process")
        if process and process.returncode is None:
            process.terminate()
    logger.info("Stalker Client beendet")


@app.middleware("http")
async def request_logging(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unbehandelter Fehler bei %s %s", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    if request.url.path.startswith("/api/") and request.url.path != "/api/config":
        logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


def settings_dependency() -> Settings:
    try:
        return get_settings()
    except (RuntimeError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def client(settings: Settings = Depends(settings_dependency)) -> StalkerClient:
    return StalkerClient(settings)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_ticket(url: str, settings: Settings, media_type: str = "") -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=502, detail="Portal returned an unsupported stream URL")
    data = {"u": url, "m": media_type, "e": int(time.time()) + 7200}
    payload = _b64encode(json.dumps(data, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(settings.app_secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_ticket(ticket: str, settings: Settings) -> dict[str, str]:
    try:
        payload, signature = ticket.split(".", 1)
        expected = _b64encode(hmac.new(settings.app_secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        data = json.loads(_b64decode(payload))
        if int(data["e"]) < int(time.time()):
            raise ValueError("expired")
        url = str(data["u"])
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url")
        return {"url": url, "media_type": str(data.get("m", ""))}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Ungültiges oder abgelaufenes Stream-Ticket")
        raise HTTPException(status_code=403, detail="Invalid or expired stream ticket") from exc


def unwrap_listing(value: Any) -> Any:
    while isinstance(value, dict):
        if "data" in value:
            value = value["data"]
            continue
        if "js" in value:
            value = value["js"]
            continue
        break
    if isinstance(value, dict):
        return list(value.values())
    return value


def is_hls(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".m3u8") or "m3u8" in url.lower()


def rewrite_hls_line(line: str, source_url: str, settings: Settings) -> str:
    stripped = line.strip()
    if stripped and not stripped.startswith("#"):
        return f"/stream/{create_ticket(urljoin(source_url, stripped), settings)}"

    def replace_uri(match: re.Match[str]) -> str:
        absolute = urljoin(source_url, match.group(1))
        return f'URI="/stream/{create_ticket(absolute, settings)}"'

    return re.sub(r'URI="([^"]+)"', replace_uri, line)


@app.exception_handler(PortalError)
async def portal_error_handler(_: Request, exc: PortalError):
    logger.error("Portalfehler: %s", exc)
    return JSONResponse({"detail": str(exc)}, status_code=502)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
async def read_config() -> dict[str, Any]:
    config = load_portal_config()
    return {
        "configured": config is not None,
        "portal_url": config.portal_url if config else "",
        "portal_mac": config.portal_mac if config else "",
    }


@app.put("/api/config")
async def write_config(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        config = PortalConfig(
            portal_url=str(payload.get("portal_url", "")),
            portal_mac=str(payload.get("portal_mac", "")),
        )
        save_portal_config(config)
    except (ValidationError, OSError) as exc:
        logger.warning("Portal-Konfiguration konnte nicht gespeichert werden: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("Portal-Konfiguration gespeichert: Host=%s, MAC=%s", urlparse(config.portal_url).netloc, masked_mac(config.portal_mac))
    return {"saved": True, "portal_url": config.portal_url, "portal_mac": config.portal_mac}


@app.get("/api/status")
async def status(portal: StalkerClient = Depends(client)) -> dict[str, Any]:
    token = await portal.handshake()
    profile = await portal.profile()
    logger.info("Portal-Verbindung erfolgreich")
    return {"connected": bool(token), "profile": profile}


@app.get("/api/categories/{media_type}")
async def categories(media_type: str, portal: StalkerClient = Depends(client)) -> Any:
    if media_type not in {"itv", "vod", "series"}:
        raise HTTPException(status_code=400, detail="Unsupported media type")
    return unwrap_listing(await portal.categories(media_type))


@app.get("/api/content/{media_type}")
async def content(
    media_type: str,
    category: str = "*",
    page: int = Query(default=1, ge=1),
    search: str = "",
    portal: StalkerClient = Depends(client),
) -> Any:
    if media_type not in {"itv", "vod", "series"}:
        raise HTTPException(status_code=400, detail="Unsupported media type")
    return unwrap_listing(await portal.listing(media_type, category, page, search))


@app.get("/api/epg")
async def epg(
    channel_id: str | None = None,
    period: int = Query(default=6, ge=1, le=168),
    portal: StalkerClient = Depends(client),
) -> Any:
    return unwrap_listing(await portal.epg(channel_id, period))


@app.get("/api/episodes/{series_id}")
async def episodes(series_id: str, season: str | None = None, portal: StalkerClient = Depends(client)) -> Any:
    clean_id = series_id.split(":", 1)[0].strip()
    return unwrap_listing(await portal.episodes(clean_id, season))


@app.post("/api/play")
async def play(
    payload: dict[str, Any],
    settings: Settings = Depends(settings_dependency),
    portal: StalkerClient = Depends(client),
) -> dict[str, str]:
    media_type = str(payload.get("type", ""))
    command = str(payload.get("cmd", ""))
    series = payload.get("series")
    item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
    if media_type not in {"itv", "vod", "series"} or not command:
        raise HTTPException(status_code=400, detail="type and cmd are required")
    url = await portal.create_link(media_type, command, str(series) if series is not None else None, item)
    ticket = create_ticket(url, settings, media_type)
    if is_hls(url):
        playback_url = f"/stream/{ticket}"
        stream_type = "hls"
    else:
        playback_url = f"/hls/{ticket}/index.m3u8"
        stream_type = "hls"
    logger.info("Wiedergabe vorbereitet: Typ=%s, Format=%s", media_type, "direct-hls" if is_hls(url) else "ffmpeg-hls")
    return {"url": playback_url, "stream_type": stream_type}


async def iter_response(response: httpx.Response, client_instance: httpx.AsyncClient) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_bytes(64 * 1024):
            yield chunk
    finally:
        await response.aclose()
        await client_instance.aclose()


def session_id_for(ticket: str) -> str:
    return hashlib.sha256(ticket.encode()).hexdigest()[:24]


async def log_ffmpeg(session_id: str, process: asyncio.subprocess.Process) -> None:
    if process.stderr is None:
        return
    lines: list[str] = []
    while True:
        line = await process.stderr.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            lines.append(text)
            if len(lines) > 20:
                lines.pop(0)
    code = await process.wait()
    if code != 0:
        logger.error("FFmpeg-HLS %s beendet (%s): %s", session_id, code, " | ".join(lines[-8:]))
    else:
        logger.info("FFmpeg-HLS %s beendet", session_id)


async def ensure_hls_session(ticket: str, settings: Settings, portal: StalkerClient) -> tuple[str, Path]:
    session_id = session_id_for(ticket)
    directory = HLS_ROOT / session_id
    playlist = directory / "index.m3u8"
    async with _hls_lock:
        current = _hls_sessions.get(session_id)
        if current and current["process"].returncode is None:
            current["last_access"] = time.time()
            return session_id, playlist

        data = read_ticket(ticket, settings)
        media_type = data["media_type"]
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)
        headers = portal.portal_headers_for_stream()
        headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in portal.cookies.items())
        ffmpeg_headers = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
        live = media_type == "itv"
        command = [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "warning",
            "-rw_timeout", "20000000", "-headers", ffmpeg_headers,
            "-i", data["url"],
            "-map", "0:v:0?", "-map", "0:a:0?", "-sn", "-dn",
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            "-profile:v", "main", "-pix_fmt", "yuv420p",
            "-g", "48", "-keyint_min", "48", "-sc_threshold", "0",
            "-c:a", "aac", "-profile:a", "aac_low", "-ar", "48000", "-ac", "2", "-b:a", "160k",
            "-max_muxing_queue_size", "2048",
            "-f", "hls", "-hls_time", "4",
            "-hls_segment_filename", str(directory / "segment-%06d.ts"),
        ]
        if live:
            command += ["-hls_list_size", "8", "-hls_flags", "delete_segments+append_list+omit_endlist+independent_segments"]
        else:
            command += ["-hls_playlist_type", "event", "-hls_list_size", "0", "-hls_flags", "independent_segments+temp_file"]
        command.append(str(playlist))
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise HTTPException(status_code=500, detail="FFmpeg is not available") from exc
        _hls_sessions[session_id] = {
            "process": process,
            "directory": directory,
            "last_access": time.time(),
            "media_type": media_type,
        }
        asyncio.create_task(log_ffmpeg(session_id, process))
        logger.info("FFmpeg-HLS gestartet: Session=%s, Typ=%s", session_id, media_type)
    return session_id, playlist


async def wait_for_file(path: Path, session_id: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > 0:
            return
        session = _hls_sessions.get(session_id)
        if session and session["process"].returncode is not None:
            break
        await asyncio.sleep(0.2)
    raise HTTPException(status_code=502, detail="FFmpeg could not prepare the stream")


@app.get("/hls/{ticket}/index.m3u8")
async def hls_playlist(ticket: str, settings: Settings = Depends(settings_dependency), portal: StalkerClient = Depends(client)):
    session_id, playlist = await ensure_hls_session(ticket, settings, portal)
    await wait_for_file(playlist, session_id)
    _hls_sessions[session_id]["last_access"] = time.time()
    return FileResponse(playlist, media_type="application/vnd.apple.mpegurl", headers={"Cache-Control": "no-store"})


@app.get("/hls/{ticket}/{filename}")
async def hls_segment(ticket: str, filename: str, settings: Settings = Depends(settings_dependency)):
    if not re.fullmatch(r"segment-\d{6}\.ts", filename):
        raise HTTPException(status_code=404, detail="Segment not found")
    read_ticket(ticket, settings)
    session_id = session_id_for(ticket)
    session = _hls_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Stream session not found")
    path = Path(session["directory"]) / filename
    await wait_for_file(path, session_id, 10.0)
    session["last_access"] = time.time()
    return FileResponse(path, media_type="video/mp2t", headers={"Cache-Control": "no-store"})


async def cleanup_hls_sessions() -> None:
    while True:
        await asyncio.sleep(30)
        now = time.time()
        for session_id, session in list(_hls_sessions.items()):
            max_idle = 60 if session.get("media_type") == "itv" else 300
            if now - session["last_access"] <= max_idle:
                continue
            process = session["process"]
            if process.returncode is None:
                process.terminate()
            shutil.rmtree(session["directory"], ignore_errors=True)
            _hls_sessions.pop(session_id, None)
            logger.info("HLS-Session bereinigt: %s", session_id)


@app.get("/stream/{ticket}")
async def stream(ticket: str, request: Request, settings: Settings = Depends(settings_dependency), portal: StalkerClient = Depends(client)):
    data = read_ticket(ticket, settings)
    url = data["url"]
    http = httpx.AsyncClient(timeout=None, verify=settings.verify_tls, follow_redirects=True)
    headers = portal.portal_headers_for_stream()
    if request.headers.get("range"):
        headers["Range"] = request.headers["range"]
    try:
        upstream_request = http.build_request("GET", url, headers=headers, cookies=portal.cookies)
        response = await http.send(upstream_request, stream=True)
        response.raise_for_status()
    except Exception as exc:
        await http.aclose()
        logger.exception("Stream konnte nicht geöffnet werden: %s", exc)
        raise HTTPException(status_code=502, detail="Stream could not be opened") from exc

    content_type = response.headers.get("content-type", "application/octet-stream")
    logger.info("Stream geöffnet: Status=%s, Content-Type=%s", response.status_code, content_type)
    if "mpegurl" in content_type.lower() or urlparse(url).path.lower().endswith(".m3u8"):
        body = (await response.aread()).decode("utf-8", errors="replace")
        await response.aclose()
        await http.aclose()
        rewritten = [rewrite_hls_line(line, url, settings) for line in body.splitlines()]
        return StreamingResponse(iter([("\n".join(rewritten) + "\n").encode()]), media_type="application/vnd.apple.mpegurl")

    response_headers = {}
    for name in ("content-length", "accept-ranges", "content-range", "cache-control"):
        if name in response.headers:
            response_headers[name] = response.headers[name]
    return StreamingResponse(iter_response(response, http), status_code=response.status_code, media_type=content_type, headers=response_headers)
