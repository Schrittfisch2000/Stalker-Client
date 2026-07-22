from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_readme_current_version_matches_application(self) -> None:
        readme = self.read("README.md")
        match = re.search(r"\*\*Aktuelle Version: ([0-9]+\.[0-9]+\.[0-9]+)", readme)
        self.assertIsNotNone(match, "README enthält keine aktuelle Versionsangabe")
        self.assertEqual(match.group(1), APP_VERSION)

    def test_frontend_version_markers_match_application(self) -> None:
        template = self.read("app/templates/index.html")
        title_match = re.search(r"<title>Stalker Client ([0-9]+\.[0-9]+\.[0-9]+)</title>", template)
        badge_match = re.search(r'id="appVersion"[^>]*>Version ([0-9]+\.[0-9]+\.[0-9]+)</div>', template)
        cache_versions = set(re.findall(r"/static/[^\"']+\?v=([0-9]+\.[0-9]+\.[0-9]+)", template))

        self.assertIsNotNone(title_match, "Frontend-Titel enthält keine App-Version")
        self.assertIsNotNone(badge_match, "Frontend-Versionsanzeige fehlt")
        self.assertEqual(title_match.group(1), APP_VERSION)
        self.assertEqual(badge_match.group(1), APP_VERSION)
        self.assertEqual(cache_versions, {APP_VERSION})

    def test_root_compose_matches_application_version(self) -> None:
        compose = self.read("docker-compose.yml")
        self.assertIn(f"image: stalker-client-deutsch:{APP_VERSION}", compose)
        self.assertIn(f'de.stalker-client.version: "{APP_VERSION}"', compose)

    def test_standard_compose_matches_application_version(self) -> None:
        compose = self.read("deploy/standard/docker-compose.yml")
        self.assertIn(f"image: stalker-client-deutsch:{APP_VERSION}", compose)

    def test_ugreen_compose_matches_application_version(self) -> None:
        compose = self.read("deploy/ugreen/docker-compose.yml")
        self.assertIn(f"image: stalker-client-deutsch:{APP_VERSION}-ugreen", compose)


if __name__ == "__main__":
    unittest.main()
