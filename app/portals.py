from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from .auth import require_admin, require_user
from .config import PortalConfig
from .storage import data_file

PORTALS_FILE = Path(os.getenv("PORTALS_FILE", str(data_file("portal-einstellungen.json"))))
ASSIGNMENTS_FILE = Path(os.getenv("PORTAL_ASSIGNMENTS_FILE", str(data_file("portal-zuweisungen.json"))))
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


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or f"portal-{int(time.time())}"


def _empty_store() -> dict[str, Any]:
    return {"default_portal_id": "", "portals": []}


def load_portal_store() -> dict[str, Any]:
    raw = _read(PORTALS_FILE, {})
    if not isinstance(raw, dict):
        return _empty_store()

    # Automatische Migration der bisherigen Einzelportal-Struktur.
    if "portal_url" in raw and "portal_mac" in raw:
        try:
            config = PortalConfig.model_validate(raw)
        except ValidationError:
            return _empty_store()
        portal = {
            "id": "standard",
            "name": "Standardportal",
            "portal_url": config.portal_url,
            "portal_mac": config.portal_mac,
            "active": True,
            "created_at": int(time.time()),
        }
        migrated = {"default_portal_id": "standard", "portals": [portal]}
        _write(PORTALS_FILE, migrated)
        return migrated

    portals = raw.get("portals", [])
    if not isinstance(portals, list):
        portals = []
    default_id = str(raw.get("default_portal_id", ""))
    if not default_id and portals:
        default_id = str(portals[0].get("id", ""))
    return {"default_portal_id": default_id, "portals": portals}


def public_portal(portal: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(portal.get("id", "")),
        "name": str(portal.get("name", "Portal")),
        "portal_url": str(portal.get("portal_url", "")),
        "portal_mac": str(portal.get("portal_mac", "")),
        "active": bool(portal.get("active", True)),
        "created_at": int(portal.get("created_at", 0) or 0),
    }


def assigned_portal_ids(username: str, role: str) -> list[str]:
    store = load_portal_store()
    active = [str(p.get("id")) for p in store["portals"] if p.get("active", True)]
    if role == "admin":
        return active
    assignments = _read(ASSIGNMENTS_FILE, {})
    values = assignments.get(username, []) if isinstance(assignments, dict) else []
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value) in active]


@router.get("/portals")
async def list_portals(request: Request) -> dict[str, Any]:
    user = require_user(request)
    store = load_portal_store()
    allowed = set(assigned_portal_ids(user["username"], user["role"]))
    portals = [public_portal(portal) for portal in store["portals"] if str(portal.get("id")) in allowed]
    return {"default_portal_id": store["default_portal_id"], "portals": portals}


@router.post("/portals")
async def create_portal(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    require_admin(request)
    try:
        config = PortalConfig(
            portal_url=str(payload.get("portal_url", "")),
            portal_mac=str(payload.get("portal_mac", "")),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store = load_portal_store()
    name = str(payload.get("name", "")).strip() or "Neues Portal"
    base_id = _slug(str(payload.get("id", "")).strip() or name)
    used = {str(portal.get("id")) for portal in store["portals"]}
    portal_id = base_id
    suffix = 2
    while portal_id in used:
        portal_id = f"{base_id}-{suffix}"
        suffix += 1

    portal = {
        "id": portal_id,
        "name": name,
        "portal_url": config.portal_url,
        "portal_mac": config.portal_mac,
        "active": bool(payload.get("active", True)),
        "created_at": int(time.time()),
    }
    store["portals"].append(portal)
    if not store["default_portal_id"]:
        store["default_portal_id"] = portal_id
    _write(PORTALS_FILE, store)
    return {"created": True, "portal": public_portal(portal)}


@router.put("/portals/{portal_id}")
async def update_portal(portal_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    require_admin(request)
    store = load_portal_store()
    portal = next((item for item in store["portals"] if str(item.get("id")) == portal_id), None)
    if portal is None:
        raise HTTPException(status_code=404, detail="Portal nicht gefunden")

    try:
        config = PortalConfig(
            portal_url=str(payload.get("portal_url", portal.get("portal_url", ""))),
            portal_mac=str(payload.get("portal_mac", portal.get("portal_mac", ""))),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    portal.update({
        "name": str(payload.get("name", portal.get("name", "Portal"))).strip() or "Portal",
        "portal_url": config.portal_url,
        "portal_mac": config.portal_mac,
        "active": bool(payload.get("active", portal.get("active", True))),
    })
    _write(PORTALS_FILE, store)
    return {"updated": True, "portal": public_portal(portal)}


@router.delete("/portals/{portal_id}")
async def delete_portal(portal_id: str, request: Request) -> dict[str, bool]:
    require_admin(request)
    store = load_portal_store()
    remaining = [portal for portal in store["portals"] if str(portal.get("id")) != portal_id]
    if len(remaining) == len(store["portals"]):
        raise HTTPException(status_code=404, detail="Portal nicht gefunden")
    store["portals"] = remaining
    if store["default_portal_id"] == portal_id:
        store["default_portal_id"] = str(remaining[0].get("id", "")) if remaining else ""
    _write(PORTALS_FILE, store)

    assignments = _read(ASSIGNMENTS_FILE, {})
    if isinstance(assignments, dict):
        for username, values in list(assignments.items()):
            if isinstance(values, list):
                assignments[username] = [value for value in values if str(value) != portal_id]
        _write(ASSIGNMENTS_FILE, assignments)
    return {"deleted": True}


@router.put("/portals/{portal_id}/default")
async def set_default_portal(portal_id: str, request: Request) -> dict[str, Any]:
    require_admin(request)
    store = load_portal_store()
    if not any(str(portal.get("id")) == portal_id for portal in store["portals"]):
        raise HTTPException(status_code=404, detail="Portal nicht gefunden")
    store["default_portal_id"] = portal_id
    _write(PORTALS_FILE, store)
    return {"saved": True, "default_portal_id": portal_id}


@router.get("/users/{username}/portals")
async def read_user_portals(username: str, request: Request) -> dict[str, Any]:
    require_admin(request)
    assignments = _read(ASSIGNMENTS_FILE, {})
    values = assignments.get(username, []) if isinstance(assignments, dict) else []
    return {"username": username, "portal_ids": values if isinstance(values, list) else []}


@router.put("/users/{username}/portals")
async def write_user_portals(username: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    require_admin(request)
    values = payload.get("portal_ids", [])
    if not isinstance(values, list):
        raise HTTPException(status_code=400, detail="portal_ids muss eine Liste sein")
    known = {str(portal.get("id")) for portal in load_portal_store()["portals"]}
    normalized = list(dict.fromkeys(str(value) for value in values if str(value) in known))
    assignments = _read(ASSIGNMENTS_FILE, {})
    if not isinstance(assignments, dict):
        assignments = {}
    assignments[username] = normalized
    _write(ASSIGNMENTS_FILE, assignments)
    return {"saved": True, "username": username, "portal_ids": normalized}
