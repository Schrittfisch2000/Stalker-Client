from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException

from . import main, safari_hls_fix
from .config import Settings
from .stalker import StalkerClient

PREWARM_SEGMENTS = 8
PREWARM_TIMEOUT_SECONDS = 20

_original_ensure = safari_hls_fix._ensure_hls_session


async def _ensure_hls_session(
    ticket: str,
    settings: Settings,
    portal: StalkerClient,
) -> tuple[str, Path]:
    session_id = main.session_id_for(ticket)
    current = main._hls_sessions.get(session_id)

    if current and current["process"].returncode is not None:
        data = safari_hls_fix._read_ticket(ticket, settings)
        playback = data.get("playback") or {}
        if data.get("media_type") == "itv" and playback.get("handover_managed"):
            current["last_access"] = time.time()
            main.logger.warning(
                "Beendete Handover-Session wird nicht innerhalb derselben Playlist neu gestartet: Session=%s",
                session_id,
            )
            raise HTTPException(status_code=410, detail="Live session ended; use a prepared replacement session")

    return await _original_ensure(ticket, settings, portal)


async def _wait_until_ready(
    session_id: str,
    directory: Path,
    playlist: Path,
    process,
) -> None:
    deadline = time.monotonic() + PREWARM_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.returncode is not None:
            raise HTTPException(status_code=502, detail="Replacement stream stopped during startup")
        segments = list(directory.glob("segment-*.ts"))
        if playlist.exists() and len(segments) >= PREWARM_SEGMENTS:
            main.logger.info(
                "Live-Handover-Ersatzsession bereit: Session=%s, Segmente=%s",
                session_id,
                len(segments),
            )
            return
        await main.asyncio.sleep(0.25)
    raise HTTPException(status_code=504, detail="Replacement stream did not become ready in time")


async def _refresh_live_ticket(
    ticket: str,
    settings: Settings = Depends(main.settings_dependency),
    portal: StalkerClient = Depends(main.client),
) -> dict[str, str]:
    data = safari_hls_fix._read_ticket(ticket, settings)
    if data.get("media_type") != "itv" or not data.get("playback"):
        raise HTTPException(status_code=400, detail="Live-TV ticket required")

    fresh_url = await safari_hls_fix._renew_stream_url(data, portal)
    playback: dict[str, Any] = dict(data["playback"])
    playback["handover_managed"] = True
    fresh_ticket = safari_hls_fix._create_ticket(fresh_url, settings, "itv", playback)
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
    main.logger.info("Vorgewärmte Live-Handover-Session ausgeliefert: Session=%s", session_id)
    return {"url": f"/hls/{fresh_ticket}/index.m3u8", "ready": "true"}


async def _release_live_ticket(
    ticket: str,
    settings: Settings = Depends(main.settings_dependency),
) -> dict[str, bool]:
    safari_hls_fix._read_ticket(ticket, settings)
    session_id = main.session_id_for(ticket)
    session = main._hls_sessions.get(session_id)
    if not session:
        return {"released": False}

    process = session.get("process")
    if process and process.returncode is None:
        process.terminate()
    session["last_access"] = 0
    main.logger.info("Alte Live-Handover-Session freigegeben: Session=%s", session_id)
    return {"released": True}


def install() -> None:
    safari_hls_fix.PREWARM_SEGMENTS = PREWARM_SEGMENTS
    safari_hls_fix.PREWARM_TIMEOUT_SECONDS = PREWARM_TIMEOUT_SECONDS
    safari_hls_fix._ensure_hls_session = _ensure_hls_session
    safari_hls_fix._wait_until_ready = _wait_until_ready
    main.ensure_hls_session = _ensure_hls_session

    for route in main.app.routes:
        if getattr(route, "path", None) == "/api/live-refresh/{ticket}":
            route.endpoint = _refresh_live_ticket
            if getattr(route, "dependant", None) is not None:
                route.dependant.call = _refresh_live_ticket
            break

    if not any(getattr(route, "path", None) == "/api/live-release/{ticket}" for route in main.app.routes):
        main.app.add_api_route(
            "/api/live-release/{ticket}",
            _release_live_ticket,
            methods=["POST"],
        )
