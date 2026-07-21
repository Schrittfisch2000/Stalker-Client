from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .config import PortalConfig, Settings, get_settings, load_portal_config, save_portal_config
from .logging_config import configure_logging, masked_mac
from .stalker import PortalError, StalkerClient

BASE_DIR = Path(__file__).resolve().parent
logger = configure_logging()
app = FastAPI(title="Stalker Client", version="0.3.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Stalker Client gestartet")


@app.on_event("shutdown")
async def shutdown_event() -> None:
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


def create_ticket(url: str, settings: Settings, ttl: int = 7200) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=502, detail="Portal returned an unsupported stream URL")
    payload = _b64encode(json.dumps({"u": url, "e": int(time.time()) + ttl}, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(settings.app_secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_ticket(ticket: str, settings: Settings) -> str:
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
        return url
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Ungültiges oder abgelaufenes Stream-Ticket")
        raise HTTPException(status_code=403, detail="Invalid or expired stream ticket") from exc


def unwrap_listing(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("data", value)
    return value


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
    return unwrap_listing(await portal.episodes(series_id, season))


@app.post("/api/play")
async def play(payload: dict[str, Any], settings: Settings = Depends(settings_dependency), portal: StalkerClient = Depends(client)) -> dict[str, str]:
    media_type = str(payload.get("type", ""))
    command = str(payload.get("cmd", ""))
    series = payload.get("series")
    if media_type not in {"itv", "vod", "series"} or not command:
        raise HTTPException(status_code=400, detail="type and cmd are required")
    url = await portal.create_link(media_type, command, str(series) if series is not None else None)
    logger.info("Wiedergabe vorbereitet: Typ=%s", media_type)
    return {"url": f"/stream/{create_ticket(url, settings)}"}


async def iter_response(response: httpx.Response, client_instance: httpx.AsyncClient) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_bytes(64 * 1024):
            yield chunk
    finally:
        await response.aclose()
        await client_instance.aclose()


@app.get("/stream/{ticket}")
async def stream(ticket: str, settings: Settings = Depends(settings_dependency), portal: StalkerClient = Depends(client)):
    url = read_ticket(ticket, settings)
    http = httpx.AsyncClient(timeout=None, verify=settings.verify_tls, follow_redirects=True)
    try:
        request = http.build_request("GET", url, headers=portal.portal_headers_for_stream(), cookies=portal.cookies)
        response = await http.send(request, stream=True)
        response.raise_for_status()
    except Exception as exc:
        await http.aclose()
        logger.exception("Stream konnte nicht geöffnet werden: %s", exc)
        raise HTTPException(status_code=502, detail="Stream could not be opened") from exc

    content_type = response.headers.get("content-type", "application/octet-stream")
    if "mpegurl" in content_type.lower() or urlparse(url).path.lower().endswith(".m3u8"):
        body = (await response.aread()).decode("utf-8", errors="replace")
        await response.aclose()
        await http.aclose()
        rewritten: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                absolute = urljoin(url, stripped)
                rewritten.append(f"/stream/{create_ticket(absolute, settings)}")
            else:
                rewritten.append(line)
        return StreamingResponse(iter([("\n".join(rewritten) + "\n").encode()]), media_type="application/vnd.apple.mpegurl")

    headers = {}
    for name in ("content-length", "accept-ranges", "content-range"):
        if name in response.headers:
            headers[name] = response.headers[name]
    return StreamingResponse(iter_response(response, http), status_code=response.status_code, media_type=content_type, headers=headers)
