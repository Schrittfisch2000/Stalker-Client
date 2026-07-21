from __future__ import annotations

import json
import os
import secrets
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


CONFIG_FILE = Path(os.getenv("CONFIG_FILE", "/config/portal-settings.json"))
SECRET_FILE = Path(os.getenv("SECRET_FILE", "/config/.stalker-secret"))


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
    if CONFIG_FILE.exists():
        try:
            return PortalConfig.model_validate_json(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    url = os.getenv("PORTAL_URL", "").strip()
    mac = os.getenv("PORTAL_MAC", "").strip()
    if url and mac:
        return PortalConfig(portal_url=url, portal_mac=mac)
    return None


def save_portal_config(config: PortalConfig) -> None:
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
