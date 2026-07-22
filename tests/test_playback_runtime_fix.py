from __future__ import annotations

import unittest

from app.playback_runtime_fix import (
    _clean_identifier,
    _create_link,
    _episodes,
    _matches_requested_series,
)


class FakePortal:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.ordered_calls: list[tuple[str, dict]] = []

    @staticmethod
    def _as_list(value):
        return value if isinstance(value, list) else []

    @staticmethod
    def _usable_direct_url(_command: str):
        return None

    @staticmethod
    def _valid_command(value) -> bool:
        return bool(value and str(value).strip())

    @staticmethod
    def _normalize_portal_url(value: str):
        return value

    async def call(self, media_type: str, action: str, **params):
        self.calls.append((media_type, action, params))
        if action == "get_episodes":
            return [{"id": "373350", "name": "Fremder Film", "is_movie": 1, "series": []}]
        if action == "create_link":
            return {"cmd": "http://portal.test/play/episode.mp4"}
        return []

    async def _all_ordered_items(self, media_type: str, **params):
        self.ordered_calls.append((media_type, params))
        return [
            {
                "id": "episode-4",
                "episode_id": "4",
                "movie_id": "7783",
                "season_id": "1",
                "name": "Folge 4",
                "cmd": "episode-command",
            }
        ]


class EpisodeIdentityTests(unittest.IsolatedAsyncioTestCase):
    def test_empty_series_array_is_not_an_episode_number(self) -> None:
        self.assertEqual(_clean_identifier([]), "")
        self.assertEqual(_clean_identifier({}), "")

    def test_unrelated_movie_is_rejected_for_series(self) -> None:
        item = {"id": "373350", "is_movie": 1, "series": [], "name": "Fremder Film"}
        self.assertFalse(_matches_requested_series(item, "7783", None))

    def test_episode_for_requested_series_is_accepted(self) -> None:
        item = {"episode_id": "4", "movie_id": "7783", "season_id": "1"}
        self.assertTrue(_matches_requested_series(item, "7783", "1"))

    async def test_specific_episode_action_runs_before_ordered_fallback(self) -> None:
        portal = FakePortal()
        result = await _episodes(portal, "7783", "1")

        self.assertEqual(result[0]["episode_id"], "4")
        self.assertEqual(portal.calls[0][1], "get_episodes")
        self.assertEqual(portal.ordered_calls[0][0], "series")

    async def test_create_link_sends_episode_parameters_first(self) -> None:
        portal = FakePortal()
        result = await _create_link(
            portal,
            "series",
            "series-command",
            "4",
            {
                "series_parent_id": "7783",
                "season_id": "1",
                "episode_id": "4",
            },
        )

        self.assertEqual(result, "http://portal.test/play/episode.mp4")
        _, action, params = portal.calls[0]
        self.assertEqual(action, "create_link")
        self.assertEqual(params["series"], "4")
        self.assertEqual(params["episode_id"], "4")
        self.assertEqual(params["movie_id"], "7783")
        self.assertEqual(params["season_id"], "1")


if __name__ == "__main__":
    unittest.main()
