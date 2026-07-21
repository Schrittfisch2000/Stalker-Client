from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

USERS_FILE = Path(os.getenv("USERS_FILE", "/konfiguration/benutzer.json"))
SESSION_COOKIE = "stalker_sitzung"
SESSION_TTL = 60 * 60 * 24 * 7
router = APIRouter(prefix="/api")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _secret() -> bytes:
    value = os.getenv("APP_SECRET", "").strip()
    if not value:
        secret_file = Path(os.getenv("SECRET_FILE", "/konfiguration/.stalker-geheimnis"))
        if secret_file.exists():
            value = secret_file.read_text(encoding="utf-8").strip()
    if not value:
        value = "stalker-client-lokale-sitzung"
    return value.encode()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_text, digest_text = stored.split("$", 2)
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _load_users() -> list[dict[str, Any]]:
    if not USERS_FILE.exists():
        return []
    try:
        value = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_users(users: list[dict[str, Any]]) -> None:
    _atomic_write(USERS_FILE, json.dumps(users, ensure_ascii=False, indent=2) + "\n")


def _encode_session(username: str, role: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"u": username, "r": role, "e": int(time.time()) + SESSION_TTL}, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def current_user(request: Request) -> dict[str, str] | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    try:
        payload, signature = token.split(".", 1)
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(data["e"]) < int(time.time()):
            return None
        user = next((item for item in _load_users() if item.get("username") == data.get("u") and item.get("active", True)), None)
        if not user:
            return None
        return {"username": str(user["username"]), "role": str(user.get("role", "user"))}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def require_user(request: Request) -> dict[str, str]:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Bitte anmelden")
    return user


def require_admin(request: Request) -> dict[str, str]:
    user = require_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen Benutzer verwalten")
    return user


@router.get("/auth/status")
async def auth_status(request: Request) -> dict[str, Any]:
    users = _load_users()
    user = current_user(request)
    return {"initialized": bool(users), "authenticated": user is not None, "user": user}


@router.post("/auth/setup")
async def setup(payload: dict[str, Any], response: Response) -> dict[str, Any]:
    if _load_users():
        raise HTTPException(status_code=409, detail="Benutzerverwaltung ist bereits eingerichtet")
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if len(username) < 3 or len(password) < 8:
        raise HTTPException(status_code=400, detail="Benutzername mindestens 3 Zeichen, Passwort mindestens 8 Zeichen")
    _save_users([{"username": username, "password": _hash_password(password), "role": "admin", "active": True}])
    response.set_cookie(SESSION_COOKIE, _encode_session(username, "admin"), httponly=True, samesite="lax", max_age=SESSION_TTL)
    return {"created": True, "user": {"username": username, "role": "admin"}}


@router.post("/auth/login")
async def login(payload: dict[str, Any], response: Response) -> dict[str, Any]:
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    user = next((item for item in _load_users() if item.get("username") == username and item.get("active", True)), None)
    if not user or not _verify_password(password, str(user.get("password", ""))):
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort ist falsch")
    role = str(user.get("role", "user"))
    response.set_cookie(SESSION_COOKIE, _encode_session(username, role), httponly=True, samesite="lax", max_age=SESSION_TTL)
    return {"authenticated": True, "user": {"username": username, "role": role}}


@router.post("/auth/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE)
    return {"authenticated": False}


@router.get("/users")
async def list_users(request: Request) -> list[dict[str, Any]]:
    require_admin(request)
    return [{"username": item.get("username"), "role": item.get("role", "user"), "active": item.get("active", True)} for item in _load_users()]


@router.post("/users")
async def create_user(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    require_admin(request)
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "user"))
    if role not in {"admin", "user"} or len(username) < 3 or len(password) < 8:
        raise HTTPException(status_code=400, detail="Ungültige Benutzerdaten")
    users = _load_users()
    if any(item.get("username") == username for item in users):
        raise HTTPException(status_code=409, detail="Benutzername existiert bereits")
    users.append({"username": username, "password": _hash_password(password), "role": role, "active": True})
    _save_users(users)
    return {"created": True}


@router.put("/users/{username}")
async def update_user(username: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    actor = require_admin(request)
    users = _load_users()
    user = next((item for item in users if item.get("username") == username), None)
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    role = str(payload.get("role", user.get("role", "user")))
    active = bool(payload.get("active", user.get("active", True)))
    if role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="Ungültige Rolle")
    if username == actor["username"] and (role != "admin" or not active):
        raise HTTPException(status_code=400, detail="Das eigene Administratorkonto darf nicht deaktiviert oder herabgestuft werden")
    user["role"] = role
    user["active"] = active
    password = str(payload.get("password", ""))
    if password:
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Passwort muss mindestens 8 Zeichen lang sein")
        user["password"] = _hash_password(password)
    _save_users(users)
    return {"updated": True}


@router.delete("/users/{username}")
async def delete_user(username: str, request: Request) -> dict[str, Any]:
    actor = require_admin(request)
    if username == actor["username"]:
        raise HTTPException(status_code=400, detail="Das eigene Konto kann nicht gelöscht werden")
    users = _load_users()
    remaining = [item for item in users if item.get("username") != username]
    if len(remaining) == len(users):
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    _save_users(remaining)
    return {"deleted": True}
