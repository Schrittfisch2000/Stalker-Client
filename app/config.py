from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    portal_url: str = Field(alias="PORTAL_URL")
    portal_mac: str = Field(alias="PORTAL_MAC")
    app_secret: str = Field(alias="APP_SECRET", min_length=16)
    port: int = Field(default=8080, alias="PORT")
    verify_tls: bool = Field(default=True, alias="VERIFY_TLS")
    request_timeout: float = Field(default=20.0, alias="REQUEST_TIMEOUT")

    @field_validator("portal_url")
    @classmethod
    def normalize_portal_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        for suffix in ("/portal.php", "/server/load.php", "/c"):
            if value.endswith(suffix):
                value = value[: -len(suffix)]
        if not value.startswith(("http://", "https://")):
            raise ValueError("PORTAL_URL must start with http:// or https://")
        return value

    @field_validator("portal_mac")
    @classmethod
    def normalize_mac(cls, value: str) -> str:
        value = value.strip().upper()
        parts = value.split(":")
        if len(parts) != 6 or any(len(part) != 2 for part in parts):
            raise ValueError("PORTAL_MAC must use format 00:1A:79:XX:XX:XX")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
