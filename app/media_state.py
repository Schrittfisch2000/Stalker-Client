from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .auth import require_user
from .storage import data_file

FAVORITES_FILE = Path(os.getenv("FAVORITES_FILE", str(data_file("favoriten.json"))))
PROGRESS_FILE = Path(os.getenv("PROGRESS_FILE", str(data_file("fortschritt.json"))))
MEDIA_TYPES = {"itv", "vod", "series"}
router = APIRouter(prefix="/api")


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _text(payload: dict[str, Any], *names: str, default: str = "") -> str:
    for name in names:
        value = payload.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _identity(payload: dict[str, Any]) -> tuple[str, str]:
    media_type = _text(payload, "type")
    if media_type not in MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Ungültiger Medientyp")
    item_id = _text(payload, "id", "movie_id", "series_id", "episode_id", "ch_id")
    title = _text(payload, "title", "name", "episode_name", default="Ohne Titel")
    if not item_id:
        item_id = f"{media_type}:{title}"
    return media_type, item_id


def _entry(payload: dict[str, Any]) -> dict[str, Any]:
    media_type, item_id = _identity(payload)
    return {
        "type": media_type,
        "id": item_id,
        "title": _text(payload, "title", "name", "episode_name", default="Ohne Titel"),
        "image": _text(payload, "image", "logo", "cover", "poster", "screenshot_uri"),
        "description": _text(payload, "description", "plot", "descr"),
        "category": _text(payload, "category", "category_id", "genre_id"),
        "series_id": _text(payload, "series_id", "movie_id"),
        "season": _text(payload, "season", "season_id", "season_number"),
        "episode": _text(payload, "episode", "episode_number"),
        "updated_at": int(time.time()),
    }


@router.get("/favorites")
async def list_favorites(request: Request, media_type: str | None = None) -> list[dict[str, Any]]:
    user = require_user(request)
    values = _read(FAVORITES_FILE).get(user["username"], [])
    if not isinstance(values, list):
        return []
    if media_type:
        values = [value for value in values if value.get("type") == media_type]
    return values


@router.put("/favorites")
async def add_favorite(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = require_user(request)
    entry = _entry(payload)
    data = _read(FAVORITES_FILE)
    values = data.get(user["username"], [])
    if not isinstance(values, list):
        values = []
    values = [value for value in values if not (value.get("type") == entry["type"] and str(value.get("id")) == entry["id"])]
    values.insert(0, entry)
    data[user["username"]] = values[:2000]
    _write(FAVORITES_FILE, data)
    return {"favorite": True, "item": entry}


@router.delete("/favorites/{media_type}/{item_id}")
async def remove_favorite(media_type: str, item_id: str, request: Request) -> dict[str, bool]:
    user = require_user(request)
    if media_type not in MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Ungültiger Medientyp")
    data = _read(FAVORITES_FILE)
    values = data.get(user["username"], [])
    if not isinstance(values, list):
        values = []
    data[user["username"]] = [
        value for value in values
        if not (value.get("type") == media_type and str(value.get("id")) == item_id)
    ]
    _write(FAVORITES_FILE, data)
    return {"favorite": False}


@router.get("/progress")
async def list_progress(request: Request) -> list[dict[str, Any]]:
    user = require_user(request)
    values = _read(PROGRESS_FILE).get(user["username"], [])
    return values if isinstance(values, list) else []


@router.put("/progress")
async def save_progress(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = require_user(request)
    entry = _entry(payload)
    try:
        position = max(0.0, float(payload.get("position", 0)))
        duration = max(0.0, float(payload.get("duration", 0)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Ungültiger Wiedergabefortschritt") from exc

    finished = bool(payload.get("finished")) or (duration > 0 and position / duration >= 0.9)
    entry.update({
        "position": 0 if finished else round(position, 2),
        "duration": round(duration, 2),
        "finished": finished,
        "percent": 100 if finished else round((position / duration) * 100, 1) if duration > 0 else 0,
    })

    data = _read(PROGRESS_FILE)
    values = data.get(user["username"], [])
    if not isinstance(values, list):
        values = []
    values = [value for value in values if not (value.get("type") == entry["type"] and str(value.get("id")) == entry["id"])]
    values.insert(0, entry)
    data[user["username"]] = values[:2000]
    _write(PROGRESS_FILE, data)
    return {"saved": True, "item": entry}


@router.delete("/progress/{media_type}/{item_id}")
async def delete_progress(media_type: str, item_id: str, request: Request) -> dict[str, bool]:
    user = require_user(request)
    data = _read(PROGRESS_FILE)
    values = data.get(user["username"], [])
    if not isinstance(values, list):
        values = []
    data[user["username"]] = [
        value for value in values
        if not (value.get("type") == media_type and str(value.get("id")) == item_id)
    ]
    _write(PROGRESS_FILE, data)
    return {"deleted": True}
