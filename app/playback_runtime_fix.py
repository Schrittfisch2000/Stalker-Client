from __future__ import annotations

from typing import Any

import httpx
from fastapi import Depends

from . import main, safari_hls_fix
from .config import Settings
from .live_runtime_fix import stop_hls_session
from .stalker import PortalError, StalkerClient

_original_start_direct_ffmpeg = safari_hls_fix._start_direct_ffmpeg
_original_create_link = StalkerClient.create_link


def _clean_identifier(value: Any) -> str:
    if value is None or isinstance(value, (list, tuple, dict, set)):
        return ""
    return str(value).split(":", 1)[0].strip()


def _has_values(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return bool(str(value).strip())


def _clearly_unrelated_movie(item: dict[str, Any]) -> bool:
    movie_flag = item.get("is_movie") in {1, "1", True, "true"}
    series_flag = item.get("is_series") in {1, "1", True, "true"}
    episode_shape = any(
        _has_values(item.get(key))
        for key in (
            "episode_id",
            "episode",
            "episode_number",
            "season_id",
            "season",
            "season_number",
            "episodes",
            "episode_list",
            "series_list",
            "season_series",
        )
    )
    return movie_flag and not series_flag and not episode_shape


def _matches_requested_series(
    item: dict[str, Any],
    series_id: str,
    season: str | None,
) -> bool:
    if _clearly_unrelated_movie(item):
        return False

    identifiers = {
        _clean_identifier(item.get(key))
        for key in (
            "movie_id",
            "series_id",
            "parent_id",
            "series_parent_id",
            "parent_movie_id",
        )
    }
    identifiers.discard("")
    if series_id in identifiers:
        return True

    episode_shape = any(
        _has_values(item.get(key))
        for key in (
            "episode_id",
            "episode",
            "episode_number",
            "episodes",
            "episode_list",
            "series_list",
            "season_series",
        )
    )
    if episode_shape:
        if season is None:
            return True
        item_season = next(
            (
                _clean_identifier(item.get(key))
                for key in ("season_id", "season", "season_number")
                if _clean_identifier(item.get(key))
            ),
            "",
        )
        return not item_season or item_season == season

    title = str(
        item.get("name")
        or item.get("title")
        or item.get("episode_name")
        or ""
    ).casefold()
    return title.startswith(("staffel ", "season ", "episode ", "folge "))


async def _episodes(
    self: StalkerClient,
    series_id: str,
    season: str | None = None,
) -> Any:
    clean_id = _clean_identifier(series_id)
    clean_season = _clean_identifier(season) or None
    errors: list[str] = []

    # Die spezifische Portalaktion zuerst verwenden. Die vorherige Reihenfolge
    # konnte bei Portalen, die Filter ignorieren, eine globale Filmliste liefern.
    try:
        result = await self.call(
            "series",
            "get_episodes",
            movie_id=clean_id,
            series_id=clean_id,
            season_id=clean_season,
        )
        items = [item for item in self._as_list(result) if not _clearly_unrelated_movie(item)]
        if items:
            return items
    except (PortalError, httpx.HTTPError) as exc:
        errors.append(str(exc))

    attempts = [
        (
            "series",
            {
                "movie_id": clean_id,
                "series_id": clean_id,
                "season_id": clean_season,
                "episode_id": "*",
            },
        ),
        (
            "vod",
            {
                "movie_id": clean_id,
                "series_id": clean_id,
                "season_id": clean_season,
            },
        ),
    ]
    for candidate_type, params in attempts:
        try:
            result = await self._all_ordered_items(candidate_type, **params)
        except (PortalError, httpx.HTTPError) as exc:
            errors.append(str(exc))
            continue
        filtered = [
            item
            for item in result
            if _matches_requested_series(item, clean_id, clean_season)
        ]
        if filtered:
            return filtered
        if result:
            errors.append(
                f"{candidate_type}/get_ordered_list lieferte nur unpassende Katalogeinträge"
            )

    raise PortalError(
        "Portal lieferte keine passenden Episoden"
        + (f": {errors[-1]}" if errors else "")
    )


async def _create_link(
    self: StalkerClient,
    media_type: str,
    command: str,
    series: str | None = None,
    item: dict[str, Any] | None = None,
) -> str:
    if media_type != "series":
        return await _original_create_link(self, media_type, command, series, item)

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
    commands = list(
        dict.fromkeys(
            str(value).strip()
            for value in command_candidates
            if self._valid_command(value)
        )
    )
    if not commands:
        raise PortalError("Portal item does not contain a playable command")

    clean_series = _clean_identifier(series) or None
    episode_id = (
        _clean_identifier(item.get("episode_id"))
        or _clean_identifier(item.get("episode_number"))
        or clean_series
        or _clean_identifier(item.get("id"))
    )
    movie_id = (
        _clean_identifier(item.get("series_parent_id"))
        or _clean_identifier(item.get("parent_movie_id"))
        or _clean_identifier(item.get("movie_id"))
        or _clean_identifier(item.get("series_id"))
        or _clean_identifier(item.get("id"))
    )
    season_id = (
        _clean_identifier(item.get("season_id"))
        or _clean_identifier(item.get("season"))
        or _clean_identifier(item.get("season_number"))
        or None
    )

    errors: list[str] = []
    for candidate_type in ("series", "vod", "itv"):
        for candidate_command in commands:
            basic = {
                "cmd": candidate_command,
                "forced_storage": "0",
                "disable_ad": "0",
                "download": "0",
            }
            attempts: list[dict[str, Any]] = []
            if clean_series or episode_id or season_id:
                attempts.append(
                    {
                        **basic,
                        "series": clean_series,
                        "episode_id": episode_id,
                        "movie_id": movie_id,
                        "season_id": season_id,
                    }
                )
            if clean_series:
                attempts.append({**basic, "series": clean_series})
            attempts.append(basic)

            for params in attempts:
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
    raise PortalError(
        "Portal could not create a stream link"
        + (f" ({summary})" if summary else "")
    )


async def _start_direct_ffmpeg(
    session_id: str,
    data: dict[str, Any],
    portal: StalkerClient,
    directory,
    playlist,
):
    playback = data.get("playback") if isinstance(data.get("playback"), dict) else None
    if playback:
        command = str(playback.get("cmd", ""))
        series = playback.get("series")
        item = playback.get("item") if isinstance(playback.get("item"), dict) else {}
        if command:
            fresh_url = await portal.create_link(
                str(data.get("media_type", "vod")),
                command,
                _clean_identifier(series) or None,
                item,
            )
            data = {**data, "url": fresh_url}
            main.logger.info(
                "Frischen Portal-Link für Medienwiedergabe erstellt: Session=%s, Typ=%s",
                session_id,
                data.get("media_type"),
            )
    return await _original_start_direct_ffmpeg(
        session_id,
        data,
        portal,
        directory,
        playlist,
    )


async def _release_session(
    ticket: str,
    settings: Settings = Depends(main.settings_dependency),
) -> dict[str, bool]:
    safari_hls_fix._read_ticket(ticket, settings)
    session_id = main.session_id_for(ticket)
    session = main._hls_sessions.get(session_id)
    if session is None:
        return {"released": False}
    await stop_hls_session(session_id, session)
    return {"released": True}


def install() -> None:
    StalkerClient.episodes = _episodes
    StalkerClient.create_link = _create_link
    safari_hls_fix._start_direct_ffmpeg = _start_direct_ffmpeg

    if not any(
        getattr(route, "path", None) == "/api/session-release/{ticket}"
        for route in main.app.routes
    ):
        main.app.add_api_route(
            "/api/session-release/{ticket}",
            _release_session,
            methods=["POST"],
        )
