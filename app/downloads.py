from __future__ import annotations

import asyncio
import re
import unicodedata
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from . import main, safari_hls_fix
from .config import Settings
from .stalker import StalkerClient

router = APIRouter()
_DOWNLOAD_SLOTS = asyncio.Semaphore(2)
_DOWNLOAD_SLOT_TIMEOUT_SECONDS = 0.1
_PROCESS_STOP_TIMEOUT_SECONDS = 5.0


def _safe_download_name(value: str) -> str:
    name = unicodedata.normalize("NFKC", value or "Download")
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        name = "Download"
    return name[:120]


def _download_filename(title: str) -> str:
    base = _safe_download_name(title)
    if Path(base).suffix.lower() == ".mkv":
        return base
    return f"{base}.mkv"


def _content_disposition(filename: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", errors="ignore")
        .decode("ascii")
    )
    ascii_name = _safe_download_name(ascii_name) or "Download.mkv"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _ffmpeg_download_command(url: str, portal: StalkerClient) -> list[str]:
    headers = portal.portal_headers_for_stream()
    headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in portal.cookies.items())
    ffmpeg_headers = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    return [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-rw_timeout",
        "30000000",
        "-headers",
        ffmpeg_headers,
        "-i",
        url,
        "-map",
        "0:v:0?",
        "-map",
        "0:a?",
        "-map",
        "0:s?",
        "-dn",
        "-c",
        "copy",
        "-f",
        "matroska",
        "pipe:1",
    ]


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=_PROCESS_STOP_TIMEOUT_SECONDS)
    except TimeoutError:
        if process.returncode is None:
            process.kill()
        await process.wait()


async def _collect_stderr(process: asyncio.subprocess.Process) -> list[str]:
    lines: list[str] = []
    if process.stderr is None:
        return lines
    while True:
        line = await process.stderr.readline()
        if not line:
            return lines
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            lines.append(text)
            if len(lines) > 12:
                lines.pop(0)


@router.post("/api/download")
async def prepare_download(
    payload: dict[str, Any],
    settings: Settings = Depends(main.settings_dependency),
    portal: StalkerClient = Depends(main.client),
) -> dict[str, str]:
    media_type = str(payload.get("type", ""))
    command = str(payload.get("cmd", ""))
    series = payload.get("series")
    item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
    title = str(payload.get("title") or item.get("name") or item.get("title") or "Download")

    if media_type not in {"vod", "series"}:
        raise HTTPException(status_code=400, detail="Downloads sind nur für Filme und Serien verfügbar")
    if not command:
        raise HTTPException(status_code=400, detail="Für diesen Inhalt fehlt ein Download-Link")

    url = await portal.create_link(
        media_type,
        command,
        str(series) if series is not None else None,
        item,
    )
    ticket = safari_hls_fix._create_ticket(url, settings, media_type)
    filename = _download_filename(title)
    query = urlencode({"name": filename})
    main.logger.info("Download vorbereitet: Typ=%s, Datei=%s", media_type, filename)
    return {"url": f"/download/{ticket}?{query}", "filename": filename}


@router.get("/download/{ticket}")
async def download_media(
    ticket: str,
    name: str = Query(default="Download.mkv"),
    settings: Settings = Depends(main.settings_dependency),
    portal: StalkerClient = Depends(main.client),
) -> StreamingResponse:
    data = safari_hls_fix._read_ticket(ticket, settings)
    if data.get("media_type") not in {"vod", "series"}:
        raise HTTPException(status_code=403, detail="Dieses Ticket erlaubt keinen Download")

    try:
        await asyncio.wait_for(_DOWNLOAD_SLOTS.acquire(), timeout=_DOWNLOAD_SLOT_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=429,
            detail="Es laufen bereits zwei Downloads. Bitte später erneut versuchen.",
        ) from exc

    filename = _download_filename(name.removesuffix(".mkv"))
    try:
        process = await asyncio.create_subprocess_exec(
            *_ffmpeg_download_command(str(data["url"]), portal),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        _DOWNLOAD_SLOTS.release()
        raise HTTPException(status_code=500, detail="FFmpeg ist nicht verfügbar") from exc

    stderr_task = asyncio.create_task(_collect_stderr(process))

    async def stream() -> AsyncIterator[bytes]:
        try:
            if process.stdout is None:
                raise RuntimeError("FFmpeg hat keinen Ausgabestrom geöffnet")
            while True:
                chunk = await process.stdout.read(256 * 1024)
                if not chunk:
                    break
                yield chunk
            code = await process.wait()
            stderr_lines = await stderr_task
            if code != 0:
                main.logger.error(
                    "Download-FFmpeg beendet (%s): %s",
                    code,
                    " | ".join(stderr_lines[-6:]),
                )
            else:
                main.logger.info("Download abgeschlossen: Datei=%s", filename)
        except asyncio.CancelledError:
            raise
        finally:
            await _stop_process(process)
            if not stderr_task.done():
                stderr_task.cancel()
                try:
                    await stderr_task
                except asyncio.CancelledError:
                    pass
            _DOWNLOAD_SLOTS.release()

    return StreamingResponse(
        stream(),
        media_type="video/x-matroska",
        headers={
            "Content-Disposition": _content_disposition(filename),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
