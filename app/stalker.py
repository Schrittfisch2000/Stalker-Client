from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings


class PortalError(RuntimeError):
    pass


class StalkerClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token: str | None = None
        self._token_time = 0.0
        self._lock = asyncio.Lock()

    @property
    def endpoint(self) -> str:
        return f"{self.settings.portal_url}/portal.php"

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 MAG250 stbapp",
            "X-User-Agent": "Model: MAG250; Link: Ethernet",
            "Referer": f"{self.settings.portal_url}/c/",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @property
    def cookies(self) -> dict[str, str]:
        return {"mac": self.settings.portal_mac, "stb_lang": "de", "timezone": "Europe/Berlin"}

    async def _request(self, params: dict[str, Any], *, retry_auth: bool = True) -> Any:
        async with httpx.AsyncClient(
            timeout=self.settings.request_timeout,
            verify=self.settings.verify_tls,
            follow_redirects=True,
        ) as client:
            response = await client.get(self.endpoint, params=params, headers=self.headers, cookies=self.cookies)
        if response.status_code in (401, 403) and retry_auth:
            await self.handshake(force=True)
            return await self._request(params, retry_auth=False)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise PortalError("Portal returned invalid JSON") from exc
        if isinstance(payload, dict) and payload.get("js") is not None:
            return payload["js"]
        return payload

    async def handshake(self, *, force: bool = False) -> str:
        async with self._lock:
            if self._token and not force and time.time() - self._token_time < 900:
                return self._token
            result = await self._request(
                {
                    "type": "stb",
                    "action": "handshake",
                    "token": "",
                    "JsHttpRequest": "1-xml",
                },
                retry_auth=False,
            )
            token = result.get("token") if isinstance(result, dict) else None
            if not token:
                raise PortalError("Handshake failed: portal did not return a token")
            self._token = str(token)
            self._token_time = time.time()
            return self._token

    async def call(self, media_type: str, action: str, **params: Any) -> Any:
        await self.handshake()
        query = {
            "type": media_type,
            "action": action,
            "JsHttpRequest": "1-xml",
            **{key: value for key, value in params.items() if value is not None},
        }
        return await self._request(query)

    async def profile(self) -> Any:
        return await self.call(
            "stb",
            "get_profile",
            hd="1",
            ver="ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.6.1; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c",
            num_banks="2",
            sn="0000000000000",
            stb_type="MAG250",
            client_type="STB",
            image_version="218",
            video_out="hdmi",
            device_id="",
            device_id2="",
            signature="",
            auth_second_step="1",
            hw_version="1.7-BD-00",
            not_valid_token="0",
            metrics='{"mac":"%s","sn":"0000000000000","model":"MAG250","type":"STB","uid":""}' % self.settings.portal_mac,
        )

    async def categories(self, media_type: str) -> Any:
        return await self.call(media_type, "get_genres" if media_type == "itv" else "get_categories")

    @staticmethod
    def _as_list(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            data = value.get("data", value)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                return [item for item in data.values() if isinstance(item, dict)]
        return []

    async def listing(self, media_type: str, category: str = "*", page: int = 1, search: str = "") -> Any:
        if media_type == "itv":
            raw = await self.call("itv", "get_all_channels")
            channels = self._as_list(raw)
            if category not in {"", "*", "all"}:
                channels = [
                    item for item in channels
                    if str(item.get("tv_genre_id") or item.get("genre_id") or item.get("category_id") or "") == str(category)
                ]
            if search:
                needle = search.casefold()
                channels = [
                    item for item in channels
                    if needle in str(item.get("name") or item.get("title") or item.get("ch_name") or "").casefold()
                ]
            return channels
        return await self.call(
            media_type,
            "get_ordered_list",
            genre=category,
            category=category,
            p=page,
            sortby="added",
            hd="0",
            fav="0",
            not_ended="0",
            search=search,
        )

    async def epg(self, channel_id: str | None = None, period: int = 6) -> Any:
        if channel_id:
            return await self.call("itv", "get_short_epg", ch_id=channel_id, size=period)
        return await self.call("itv", "get_epg_info", period=period)

    async def episodes(self, series_id: str, season: str | None = None) -> Any:
        return await self.call("series", "get_episodes", movie_id=series_id, season_id=season)

    async def create_link(self, media_type: str, command: str, series: str | None = None) -> str:
        result = await self.call(
            media_type,
            "create_link",
            cmd=command,
            forced_storage="0",
            disable_ad="0",
            download="0",
            series=series,
        )
        if not isinstance(result, dict):
            raise PortalError("Portal returned an invalid stream response")
        value = result.get("cmd") or result.get("url")
        if not value:
            raise PortalError("Portal did not return a stream URL")
        value = str(value).strip()
        if value.startswith("ffmpeg "):
            value = value[7:].strip()
        return value

    def portal_headers_for_stream(self) -> dict[str, str]:
        headers = self.headers.copy()
        headers.pop("Authorization", None)
        return headers

    def encoded_mac(self) -> str:
        return quote(self.settings.portal_mac, safe="")