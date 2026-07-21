from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .storage import data_file

CONFIG_FILE = Path(os.getenv("CONFIG_FILE", str(data_file("portal-einstellungen.json"))))
SECRET_FILE = Path(os.getenv("SECRET_FILE", str(data_file(".stalker-geheimnis"))))


class PortalConfig(BaseModel):
    portal_url: str
    portal_mac: str

    @field_validator("portal_url")
    @classmethod
    def normalize_portal_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        for suffix in ("/portal.php", "/server/load.php", "/c"):
            if value.endswith(suffix):
                value = value[: -len(suffix)]
        if not value.startswith(("http://", "https://")):
            raise ValueError("Portal-URL muss mit http:// oder https:// beginnen")
        return value

    @field_validator("portal_mac")
    @classmethod
    def normalize_mac(cls, value: str) -> str:
        value = value.strip().upper()
        parts = value.split(":")
        if len(parts) != 6 or any(len(part) != 2 for part in parts):
            raise ValueError("MAC-Adresse muss das Format 00:1A:79:XX:XX:XX verwenden")
        try:
            for part in parts:
                int(part, 16)
        except ValueError as exc:
            raise ValueError("MAC-Adresse enthält ungültige Zeichen") from exc
        return value


class Settings(PortalConfig):
    app_secret: str = Field(min_length=16)
    port: int = 8080
    verify_tls: bool = True
    request_timeout: float = 20.0


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


def _read_config_data() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        value = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_or_create_app_secret() -> str:
    configured = os.getenv("APP_SECRET", "").strip()
    if len(configured) >= 16:
        return configured

    if SECRET_FILE.exists():
        try:
            stored = SECRET_FILE.read_text(encoding="utf-8").strip()
            if len(stored) >= 16:
                return stored
        except OSError:
            pass

    generated = secrets.token_urlsafe(48)
    _atomic_write(SECRET_FILE, generated + "\n")
    return generated


def load_portal_config() -> PortalConfig | None:
    raw = _read_config_data()
    if raw:
        try:
            if "portal_url" in raw and "portal_mac" in raw:
                return PortalConfig.model_validate(raw)

            portals = raw.get("portals", [])
            if isinstance(portals, list) and portals:
                default_id = str(raw.get("default_portal_id", ""))
                selected = next(
                    (portal for portal in portals if str(portal.get("id", "")) == default_id and portal.get("active", True)),
                    None,
                )
                if selected is None:
                    selected = next((portal for portal in portals if portal.get("active", True)), None)
                if isinstance(selected, dict):
                    return PortalConfig.model_validate(selected)
        except (ValueError, TypeError):
            return None

    url = os.getenv("PORTAL_URL", "").strip()
    mac = os.getenv("PORTAL_MAC", "").strip()
    if url and mac:
        return PortalConfig(portal_url=url, portal_mac=mac)
    return None


def save_portal_config(config: PortalConfig) -> None:
    raw = _read_config_data()
    if isinstance(raw.get("portals"), list):
        portals = raw["portals"]
        default_id = str(raw.get("default_portal_id", ""))
        selected = next((portal for portal in portals if str(portal.get("id", "")) == default_id), None)
        if selected is None:
            selected = {
                "id": "standard",
                "name": "Standardportal",
                "active": True,
                "created_at": int(time.time()),
            }
            portals.append(selected)
            raw["default_portal_id"] = "standard"
        selected.update(config.model_dump())
        _atomic_write(CONFIG_FILE, json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
        return

    _atomic_write(CONFIG_FILE, config.model_dump_json(indent=2) + "\n")


def get_settings() -> Settings:
    portal = load_portal_config()
    if portal is None:
        raise RuntimeError("Portal ist noch nicht konfiguriert")
    return Settings(
        **portal.model_dump(),
        app_secret=load_or_create_app_secret(),
        port=int(os.getenv("PORT", "8080")),
        verify_tls=os.getenv("VERIFY_TLS", "true").lower() not in {"0", "false", "no"},
        request_timeout=float(os.getenv("REQUEST_TIMEOUT", "20")),
    )
