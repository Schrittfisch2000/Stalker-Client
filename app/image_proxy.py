from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import inspect
import ipaddress
import json
import socket
import time
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response

from .config import Settings, get_settings
from .stalker import PortalError, StalkerClient

IMAGE_FIELDS = ("image", "logo", "screenshot_uri", "cover", "poster")
IMAGE_TICKET_TTL = 24 * 60 * 60
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
ALLOWED_IMAGE_TYPES = {
    "image/avif",
    "image/bmp",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/x-icon",
    "image/vnd.microsoft.icon",
}
PATCHED_PATHS = {
    "/api/content/{media_type}",
    "/api/episodes/{series_id}",
    "/api/favorites",
    "/api/progress",
}


def settings_dependency() -> Settings:
    try:
        return get_settings()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _portal_identity(settings: Settings) -> str:
    return settings.portal_url.rstrip("/")


def _absolute_image_url(value: Any, settings: Settings) -> str | None:
    source = str(value or "").strip()
    if not source or len(source) > 4096:
        return None
    if source.startswith("/api/image/"):
        return source
    absolute = urljoin(f"{settings.portal_url.rstrip('/')}/", source)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    return urlunparse(parsed._replace(fragment=""))


def create_image_ticket(url: str, settings: Settings, *, now: int | None = None) -> str:
    current = int(time.time()) if now is None else int(now)
    expires = ((current // IMAGE_TICKET_TTL) + 1) * IMAGE_TICKET_TTL
    data = {"u": url, "p": _portal_identity(settings), "e": expires}
    payload = _b64encode(json.dumps(data, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(settings.app_secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_image_ticket(ticket: str, settings: Settings, *, now: int | None = None) -> str:
    try:
        payload, signature = ticket.split(".", 1)
        expected = _b64encode(hmac.new(settings.app_secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        data = json.loads(_b64decode(payload))
        current = int(time.time()) if now is None else int(now)
        if int(data["e"]) < current:
            raise ValueError("expired")
        if str(data["p"]) != _portal_identity(settings):
            raise ValueError("portal")
        url = _absolute_image_url(data["u"], settings)
        if not url or url.startswith("/api/image/"):
            raise ValueError("url")
        return url
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=403, detail="Ungültiges oder abgelaufenes Bild-Ticket") from exc


def attach_image_proxies(value: Any, settings: Settings) -> Any:
    if isinstance(value, list):
        return [attach_image_proxies(item, settings) for item in value]
    if not isinstance(value, dict):
        return value

    result = {key: attach_image_proxies(item, settings) for key, item in value.items()}
    source = next((value.get(field) for field in IMAGE_FIELDS if str(value.get(field) or "").strip()), None)
    absolute = _absolute_image_url(source, settings)
    if absolute:
        if absolute.startswith("/api/image/"):
            result["image_proxy"] = absolute
        else:
            result["image_proxy"] = f"/api/image/{create_image_ticket(absolute, settings)}"
    return result


def _portal_host(settings: Settings) -> str:
    return (urlparse(settings.portal_url).hostname or "").casefold()


def _same_portal_host(url: str, settings: Settings) -> bool:
    return (urlparse(url).hostname or "").casefold() == _portal_host(settings)


def _address_is_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


async def _validate_target(url: str, settings: Settings) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=403, detail="Bildziel ist nicht erlaubt")
    if parsed.username or parsed.password or "%" in parsed.hostname:
        raise HTTPException(status_code=403, detail="Bildziel ist nicht erlaubt")

    hostname = parsed.hostname.casefold()
    if hostname == _portal_host(settings):
        return
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise HTTPException(status_code=403, detail="Lokale Bildziele sind nicht erlaubt")

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        records = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, port, 0, socket.SOCK_STREAM)
        addresses = {
            ipaddress.ip_address(record[4][0].split("%", 1)[0])
            for record in records
        }
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Bildhost konnte nicht aufgelöst werden") from exc

    if not addresses or any(not _address_is_public(address) for address in addresses):
        raise HTTPException(status_code=403, detail="Private oder lokale Bildziele sind nicht erlaubt")


def _request_headers(url: str, settings: Settings, portal: StalkerClient, authenticated: bool) -> tuple[dict[str, str], dict[str, str]]:
    if _same_portal_host(url, settings):
        headers = dict(portal.headers)
        headers["Accept"] = "image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.5"
        return headers, portal.cookies
    return {
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.5",
        "User-Agent": "Mozilla/5.0 Stalker-Client-Image-Proxy",
        "Referer": f"{settings.portal_url.rstrip('/')}/c/",
    }, {}


def _detected_media_type(declared: str, content: bytes) -> str | None:
    media_type = declared.split(";", 1)[0].strip().casefold()
    if media_type in ALLOWED_IMAGE_TYPES:
        return media_type
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content.startswith(b"BM"):
        return "image/bmp"
    if content.startswith(b"\x00\x00\x01\x00"):
        return "image/x-icon"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if len(content) >= 12 and content[4:8] == b"ftyp" and content[8:12] in {b"avif", b"avis"}:
        return "image/avif"
    return None


async def _download_image(url: str, settings: Settings) -> tuple[bytes, str]:
    current = url
    portal = StalkerClient(settings)
    authenticated = False

    for redirect_count in range(MAX_REDIRECTS + 1):
        await _validate_target(current, settings)
        headers, cookies = _request_headers(current, settings, portal, authenticated)
        verify_tls = settings.verify_tls if _same_portal_host(current, settings) else True
        timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                verify=verify_tls,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream("GET", current, headers=headers, cookies=cookies) as response:
                    if response.status_code in {401, 403} and _same_portal_host(current, settings) and not authenticated:
                        await portal.handshake()
                        authenticated = True
                        continue
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location", "")
                        if not location or redirect_count >= MAX_REDIRECTS:
                            raise HTTPException(status_code=502, detail="Zu viele oder ungültige Bildweiterleitungen")
                        current = urljoin(current, location)
                        authenticated = False
                        continue
                    if response.status_code < 200 or response.status_code >= 300:
                        raise HTTPException(status_code=502, detail=f"Bildserver antwortete mit HTTP {response.status_code}")

                    try:
                        declared_length = int(response.headers.get("content-length", "0") or 0)
                    except ValueError:
                        declared_length = 0
                    if declared_length > MAX_IMAGE_BYTES:
                        raise HTTPException(status_code=413, detail="Bild ist zu groß")

                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes(64 * 1024):
                        size += len(chunk)
                        if size > MAX_IMAGE_BYTES:
                            raise HTTPException(status_code=413, detail="Bild ist zu groß")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    media_type = _detected_media_type(response.headers.get("content-type", ""), content)
                    if not media_type:
                        raise HTTPException(status_code=415, detail="Antwort ist kein unterstütztes Bild")
                    return content, media_type
        except HTTPException:
            raise
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Zeitüberschreitung beim Laden des Bildes") from exc
        except (httpx.HTTPError, PortalError) as exc:
            raise HTTPException(status_code=502, detail="Bild konnte nicht geladen werden") from exc

    raise HTTPException(status_code=502, detail="Bild konnte nicht geladen werden")


async def image_response(
    ticket: str,
    request: Request,
    settings: Settings = Depends(settings_dependency),
) -> Response:
    url = read_image_ticket(ticket, settings)
    content, media_type = await _download_image(url, settings)
    etag = f'"{hashlib.sha256(content).hexdigest()}"'
    headers = {
        "Cache-Control": "private, max-age=21600, stale-while-revalidate=86400",
        "Cross-Origin-Resource-Policy": "same-origin",
        "ETag": etag,
        "Vary": "Cookie",
        "X-Content-Type-Options": "nosniff",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=content, media_type=media_type, headers=headers)


def _patch_json_routes(app: FastAPI) -> None:
    for route in app.routes:
        if getattr(route, "path", None) not in PATCHED_PATHS:
            continue
        dependant = getattr(route, "dependant", None)
        original = getattr(dependant, "call", None)
        if not original or getattr(route, "_image_proxy_patched", False):
            continue

        async def wrapped(*args: Any, __original=original, **kwargs: Any) -> Any:
            result = __original(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            try:
                settings = get_settings()
            except (RuntimeError, ValueError):
                return result
            return attach_image_proxies(result, settings)

        route.endpoint = wrapped
        route.dependant.call = wrapped
        route._image_proxy_patched = True


def install(app: FastAPI) -> None:
    if not any(getattr(route, "path", None) == "/api/image/{ticket}" for route in app.routes):
        app.add_api_route("/api/image/{ticket}", image_response, methods=["GET"])
    _patch_json_routes(app)
