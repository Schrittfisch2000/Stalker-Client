from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .auth import require_admin, require_user

ACCESS_FILE = Path(os.getenv("ACCESS_FILE", "/konfiguration/benutzer-freigaben.json"))
HISTORY_FILE = Path(os.getenv("HISTORY_FILE", "/konfiguration/wiedergabeverlauf.json"))
MEDIA_TYPES = {"itv", "vod", "series"}
router = APIRouter(prefix="/api")


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write(path: Path, value: Any) -> None:
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


def access_for(username: str, role: str = "user") -> dict[str, list[str]]:
    if role == "admin":
        return {kind: ["*"] for kind in MEDIA_TYPES}
    data = _read(ACCESS_FILE, {})
    raw = data.get(username, {}) if isinstance(data, dict) else {}
    return {
        kind: [str(value) for value in raw.get(kind, ["*"]) if str(value).strip()]
        for kind in MEDIA_TYPES
    }


def category_allowed(username: str, role: str, media_type: str, category: str) -> bool:
    allowed = access_for(username, role).get(media_type, [])
    return "*" in allowed or category in allowed


@router.get("/access/me")
async def my_access(request: Request) -> dict[str, Any]:
    user = require_user(request)
    return {"username": user["username"], "role": user["role"], "categories": access_for(user["username"], user["role"])}


@router.get("/users/{username}/access")
async def read_user_access(username: str, request: Request) -> dict[str, Any]:
    require_admin(request)
    return {"username": username, "categories": access_for(username)}


@router.put("/users/{username}/access")
async def write_user_access(username: str, payload: dict[str, Any], request: Request) -> dict[str, bool]:
    require_admin(request)
    categories = payload.get("categories", {})
    if not isinstance(categories, dict):
        raise HTTPException(status_code=400, detail="Ungültige Kategorienfreigabe")
    normalized: dict[str, list[str]] = {}
    for kind in MEDIA_TYPES:
        values = categories.get(kind, [])
        if not isinstance(values, list):
            raise HTTPException(status_code=400, detail=f"Ungültige Freigabe für {kind}")
        normalized[kind] = list(dict.fromkeys(str(value) for value in values if str(value).strip()))
    data = _read(ACCESS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    data[username] = normalized
    _write(ACCESS_FILE, data)
    return {"saved": True}


@router.get("/history")
async def read_history(request: Request) -> list[dict[str, Any]]:
    user = require_user(request)
    data = _read(HISTORY_FILE, {})
    values = data.get(user["username"], []) if isinstance(data, dict) else []
    return values if isinstance(values, list) else []


@router.post("/history")
async def add_history(payload: dict[str, Any], request: Request) -> dict[str, bool]:
    user = require_user(request)
    media_type = str(payload.get("type", ""))
    if media_type not in {"vod", "series"}:
        return {"saved": False}
    item_id = str(payload.get("id") or payload.get("movie_id") or payload.get("episode_id") or "").strip()
    title = str(payload.get("title") or "Ohne Titel").strip()
    if not item_id:
        item_id = f"{media_type}:{title}"
    entry = {"type": media_type, "id": item_id, "title": title, "watched_at": int(time.time())}
    data = _read(HISTORY_FILE, {})
    if not isinstance(data, dict):
        data = {}
    values = data.get(user["username"], [])
    if not isinstance(values, list):
        values = []
    values = [value for value in values if not (str(value.get("type")) == media_type and str(value.get("id")) == item_id)]
    values.insert(0, entry)
    data[user["username"]] = values[:1000]
    _write(HISTORY_FILE, data)
    return {"saved": True}
