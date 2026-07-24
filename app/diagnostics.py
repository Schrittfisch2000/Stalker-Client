from __future__ import annotations

import asyncio
import os
import platform
import shutil
import socket
import time
from pathlib import Path
from typing import Any

from fastapi import Request

from . import main

_DIAGNOSTICS_TASK: asyncio.Task | None = None


def _read_first(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return "unavailable"


def _memory_info() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, raw = line.split(":", 1)
            value = raw.strip().split()[0]
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                values[key] = int(value) * 1024
    except (OSError, ValueError):
        pass
    return values


def _network_totals() -> dict[str, int]:
    received = 0
    transmitted = 0
    try:
        for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
            _, raw = line.split(":", 1)
            fields = raw.split()
            received += int(fields[0])
            transmitted += int(fields[8])
    except (OSError, ValueError, IndexError):
        pass
    return {"rx_bytes": received, "tx_bytes": transmitted}


def _cpu_usage() -> dict[str, Any]:
    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        load1 = load5 = load15 = 0.0
    return {
        "logical_cpus": os.cpu_count() or 0,
        "load_1m": round(load1, 2),
        "load_5m": round(load5, 2),
        "load_15m": round(load15, 2),
    }


def _session_info() -> dict[str, Any]:
    sessions = list(main._hls_sessions.values())
    running = sum(1 for session in sessions if session.get("process") and session["process"].returncode is None)
    mode_counts = {
        "playback_live": 0,
        "playback_remux": 0,
        "playback_audio_transcode": 0,
        "playback_full_transcode": 0,
    }
    mode_keys = {
        "live-transcode": "playback_live",
        "remux": "playback_remux",
        "audio-transcode": "playback_audio_transcode",
        "full-transcode": "playback_full_transcode",
    }
    for session in sessions:
        key = mode_keys.get(str(session.get("playback_mode", "")))
        if key:
            mode_counts[key] += 1
    return {"hls_sessions": len(sessions), "ffmpeg_running": running, **mode_counts}


def system_snapshot() -> dict[str, Any]:
    memory = _memory_info()
    disk = shutil.disk_usage("/")
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "container_id": _read_first("/etc/hostname"),
        "uptime_seconds": float(_read_first("/proc/uptime").split()[0]) if _read_first("/proc/uptime") != "unavailable" else 0,
        **_cpu_usage(),
        "memory_total": memory.get("MemTotal", 0),
        "memory_available": memory.get("MemAvailable", 0),
        "swap_total": memory.get("SwapTotal", 0),
        "swap_free": memory.get("SwapFree", 0),
        "disk_total": disk.total,
        "disk_used": disk.used,
        "disk_free": disk.free,
        **_network_totals(),
        **_session_info(),
    }


def log_system_snapshot(reason: str) -> None:
    snapshot = system_snapshot()
    main.logger.info("SYSTEM | reason=%s | %s", reason, " | ".join(f"{key}={value}" for key, value in snapshot.items()))


async def _diagnostics_loop() -> None:
    while True:
        await asyncio.sleep(30)
        log_system_snapshot("interval")


async def _client_log(request: Request, payload: dict[str, Any]) -> dict[str, bool]:
    event = str(payload.get("event", "unknown"))[:80]
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    safe_details = {str(key)[:60]: str(value)[:500] for key, value in details.items()}
    main.logger.info(
        "PLAYER | client=%s | user_agent=%s | event=%s | details=%s",
        request.client.host if request.client else "unknown",
        request.headers.get("user-agent", "unknown")[:500],
        event,
        safe_details,
    )
    return {"logged": True}


def install() -> None:
    global _DIAGNOSTICS_TASK

    if not any(getattr(route, "path", None) == "/api/client-log" for route in main.app.routes):
        main.app.add_api_route("/api/client-log", _client_log, methods=["POST"])

    @main.app.on_event("startup")
    async def start_diagnostics() -> None:
        global _DIAGNOSTICS_TASK
        log_system_snapshot("startup")
        _DIAGNOSTICS_TASK = asyncio.create_task(_diagnostics_loop())

    @main.app.on_event("shutdown")
    async def stop_diagnostics() -> None:
        if _DIAGNOSTICS_TASK:
            _DIAGNOSTICS_TASK.cancel()
        log_system_snapshot("shutdown")
