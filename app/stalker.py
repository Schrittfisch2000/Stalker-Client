from __future__ import annotations

import asyncio
import re
import time
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

import httpx

from .config import Settings


class PortalError(RuntimeError):
    pass


class StalkerClient:
    _channel_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
    _channel_cache_lock = asyncio.Lock()
    _channel_cache_ttl = 90.0
    _adult_genre_ids: dict[str, set[str]] = {}

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
        return {
            "mac": self.settings.portal_mac,
            "stb_lang": "de",
            "timezone": "Europe/Berlin",
            "adult": "1",
        }

    @property
    def _cache_key(self) -> str:
        return f"{self.settings.portal_url}|{self.settings.portal_mac}"

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
            action = f"{params.get('type', '?')}/{params.get('action', '?')}"
            content_type = response.headers.get("content-type", "unknown")
            raise PortalError(f"Portal returned invalid JSON for {action} ({content_type})") from exc
        if isinstance(payload, dict) and payload.get("js") is not None:
            return payload["js"]
        return payload

    async def handshake(self, *, force: bool = False) -> str:
        async with self._lock:
            if self._token and not force and time.time() - self._token_time < 900:
                return self._token
            result = await self._request(
                {"type": "stb", "action": "handshake", "token": "", "JsHttpRequest": "1-xml"},
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
            show_adult="1",
            adult="1",
            metrics='{"mac":"%s","sn":"0000000000000","model":"MAG250","type":"STB","uid":""}' % self.settings.portal_mac,
        )

    @staticmethod
    def _as_list(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            data = value.get("data", value.get("js", value))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                return [item for item in data.values() if isinstance(item, dict)]
        return []

    @staticmethod
    def _genre_values(item: dict[str, Any]) -> set[str]:
        values: set[str] = set()
        for key in ("tv_genre_id", "genre_id", "category_id", "genre", "category", "genres", "genre_ids"):
            value = item.get(key)
            if value is None:
                continue
            for part in re.split(r"[,;|\s]+", str(value)):
                part = part.strip()
                if part:
                    values.add(part)
        return values

    @staticmethod
    def _is_adult_item(item: dict[str, Any]) -> bool:
        truthy = {1, "1", True, "true", "yes", "on"}
        if any(item.get(key) in truthy for key in ("adult", "censored", "is_adult", "for_adults", "restricted")):
            return True
        text = " ".join(
            str(item.get(key) or "")
            for key in ("name", "title", "ch_name", "genre_name", "tv_genre_name", "category_name")
        ).casefold()
        return any(word in text for word in ("xxx", "adult", "erotik", "18+", "for adults"))

    async def _all_channels(self, *, force: bool = False) -> list[dict[str, Any]]:
        key = self._cache_key
        cached = self._channel_cache.get(key)
        if not force and cached and time.time() - cached[0] < self._channel_cache_ttl:
            return cached[1]
        async with self._channel_cache_lock:
            cached = self._channel_cache.get(key)
            if not force and cached and time.time() - cached[0] < self._channel_cache_ttl:
                return cached[1]
            channels = self._as_list(await self.call("itv", "get_all_channels", show_adult="1", adult="1"))
            self._channel_cache[key] = (time.time(), channels)
            return channels

    async def categories(self, media_type: str) -> Any:
        action = "get_genres" if media_type == "itv" else "get_categories"
        categories = self._as_list(await self.call(media_type, action, show_adult="1", adult="1"))
        if media_type != "itv":
            return categories

        adult_ids = self._adult_genre_ids.setdefault(self._cache_key, set())
        known_ids: set[str] = set()
        for category in categories:
            category_id = str(category.get("id") or category.get("genre_id") or category.get("category_id") or category.get("tv_genre_id") or "")
            if category_id:
                known_ids.add(category_id)
                if self._is_adult_item(category):
                    adult_ids.add(category_id)

        channels = await self._all_channels()
        for channel in channels:
            genre_ids = self._genre_values(channel)
            if self._is_adult_item(channel):
                adult_ids.update(genre_ids)
            for genre_id in genre_ids:
                if genre_id in known_ids:
                    continue
                title = (
                    channel.get("tv_genre_name")
                    or channel.get("genre_name")
                    or channel.get("category_name")
                    or ("XXX : FOR ADULTS" if self._is_adult_item(channel) else f"Kategorie {genre_id}")
                )
                categories.append({"id": genre_id, "title": str(title)})
                known_ids.add(genre_id)
                if self._is_adult_item(channel):
                    adult_ids.add(genre_id)
        return categories

    async def _category_channels_from_portal(self, category: str) -> list[dict[str, Any]]:
        attempts = [
            ("get_ordered_list", {"genre": category, "category": category, "p": 1, "sortby": "number"}),
            ("get_all_channels", {"genre": category, "category": category}),
        ]
        for action, params in attempts:
            try:
                result = self._as_list(await self.call("itv", action, show_adult="1", adult="1", **params))
            except (PortalError, httpx.HTTPError):
                continue
            if result:
                return result
        return []

    async def listing(self, media_type: str, category: str = "*", page: int = 1, search: str = "") -> Any:
        if media_type == "itv":
            channels = list(await self._all_channels())
            if category not in {"", "*", "all"}:
                requested = str(category)
                adult_category = requested in self._adult_genre_ids.get(self._cache_key, set())
                filtered = [
                    item for item in channels
                    if requested in self._genre_values(item) or (adult_category and self._is_adult_item(item))
                ]
                if adult_category and not filtered:
                    filtered = await self._category_channels_from_portal(requested)
                channels = filtered
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
            show_adult="1",
            adult="1",
        )

    async def epg(self, channel_id: str | None = None, period: int = 6) -> Any:
        if channel_id:
            return await self.call("itv", "get_short_epg", ch_id=channel_id, size=period)
        return await self.call("itv", "get_epg_info", period=period)

    async def episodes(self, series_id: str, season: str | None = None) -> Any:
        clean_id = str(series_id).split(":", 1)[0].strip()
        clean_season = str(season).split(":", 1)[0].strip() if season else None
        attempts = [
            ("series", "get_ordered_list", {"movie_id": clean_id, "series_id": clean_id, "season_id": clean_season, "episode_id": "*", "p": 1}),
            ("series", "get_episodes", {"movie_id": clean_id, "series_id": clean_id, "season_id": clean_season}),
            ("vod", "get_ordered_list", {"movie_id": clean_id, "series_id": clean_id, "season_id": clean_season, "p": 1}),
        ]
        errors: list[str] = []
        for candidate_type, action, params in attempts:
            try:
                result = await self.call(candidate_type, action, **params)
                if self._as_list(result):
                    return result
            except (PortalError, httpx.HTTPError) as exc:
                errors.append(str(exc))
        raise PortalError("Portal did not return episodes" + (f": {errors[-1]}" if errors else ""))

    @staticmethod
    def _extract_url(command: str) -> str | None:
        value = command.strip().strip("\"'")
        if value.lower().startswith("ffmpeg "):
            value = value[7:].strip().strip("\"'")
        match = re.search(r"https?://[^\s\"']+", value)
        return match.group(0) if match else None

    def _usable_direct_url(self, command: str) -> str | None:
        url = self._extract_url(command)
        if not url:
            return None
        parsed = urlparse(url)
        if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or parsed.path.startswith("/ch/"):
            return None
        return url

    def _normalize_portal_url(self, value: str) -> str | None:
        url = self._extract_url(value)
        if not url:
            return None
        parsed = urlparse(url)
        if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
            portal = urlparse(self.settings.portal_url)
            parsed = parsed._replace(scheme=portal.scheme or "http", netloc=portal.netloc)
            url = urlunparse(parsed)
        return url

    @staticmethod
    def _valid_command(value: Any) -> bool:
        return bool(value and str(value).strip() not in {"", ".", "null", "None"})

    async def create_link(
        self,
        media_type: str,
        command: str,
        series: str | None = None,
        item: dict[str, Any] | None = None,
    ) -> str:
        direct = self._usable_direct_url(command)
        if direct:
            return direct

        item = item or {}
        command_candidates = [
            command,
            item.get("cmd"),
            item.get("command"),
            item.get("stream_url"),
            item.get("url"),
            item.get("file"),
        ]
        commands = list(dict.fromkeys(str(value).strip() for value in command_candidates if self._valid_command(value)))
        if not commands:
            raise PortalError("Portal item does not contain a playable command")

        clean_series = str(series).split(":", 1)[0].strip() if series else None
        episode_id = item.get("episode_id") or item.get("id") or item.get("movie_id")
        movie_id = item.get("movie_id") or item.get("series_id") or item.get("id")
        season_id = item.get("season_id") or item.get("season") or item.get("season_number")
        media_attempts = [media_type]
        if media_type == "series":
            media_attempts.extend(["vod", "itv"])

        errors: list[str] = []
        for candidate_type in dict.fromkeys(media_attempts):
            for candidate_command in commands:
                basic = {
                    "cmd": candidate_command,
                    "forced_storage": "0",
                    "disable_ad": "0",
                    "download": "0",
                }
                parameter_attempts = [
                    basic,
                    {**basic, "series": clean_series},
                    {**basic, "series": clean_series, "episode_id": episode_id, "movie_id": movie_id, "season_id": season_id},
                ]
                for params in parameter_attempts:
                    try:
                        result = await self.call(candidate_type, "create_link", **params)
                    except (PortalError, httpx.HTTPError) as exc:
                        errors.append(f"{candidate_type}: {exc}")
                        continue
                    if isinstance(result, dict):
                        value = result.get("cmd") or result.get("url") or result.get("link")
                        normalized = self._normalize_portal_url(str(value)) if value else None
                        if normalized and "stream=." not in normalized:
                            return normalized
                    errors.append(f"{candidate_type}: no usable stream URL")
        summary = "; ".join(errors[-5:])
        raise PortalError("Portal could not create a stream link" + (f" ({summary})" if summary else ""))

    def portal_headers_for_stream(self) -> dict[str, str]:
        headers = self.headers.copy()
        headers.pop("Authorization", None)
        return headers

    def encoded_mac(self) -> str:
        return quote(self.settings.portal_mac, safe="")
