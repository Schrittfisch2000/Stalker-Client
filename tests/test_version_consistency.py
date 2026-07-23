from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_IMAGE = "schrittfisch2000/stalker-client:latest"
REMOVED_LEGACY_FILES = (
    "docker-compose-ugreen.yml",
    "docker-compose-synology.yml",
    "deploy",
    "deploy/standard/docker-compose.yml",
    "deploy/ugreen/docker-compose.yml",
    "CHANGELOG-1.0.30.md",
    "RELEASE-1.0.30.md",
    "docs/DOCKER-HUB-UPDATE.md",
)


class VersionConsistencyTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_version_file_matches_application(self) -> None:
        self.assertEqual(self.read("VERSION").strip(), APP_VERSION)

    def test_readme_current_version_matches_application(self) -> None:
        readme = self.read("README.md")
        match = re.search(r"\*\*Aktuelle Version: ([0-9]+\.[0-9]+\.[0-9]+)\*\*", readme)
        self.assertIsNotNone(match, "README enthält keine aktuelle Versionsangabe")
        self.assertEqual(match.group(1), APP_VERSION)

    def test_readme_is_limited_to_ugreen_deployment(self) -> None:
        readme = self.read("README.md")
        self.assertIn("UGREEN NAS", readme)
        self.assertNotIn("Windows mit Docker", readme)
        self.assertNotIn("macOS mit Docker", readme)
        self.assertNotIn("Synology NAS", readme)

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

    def test_single_compose_is_ugreen_registry_deployment(self) -> None:
        compose = self.read("docker-compose.yml")
        self.assertIn("name: stalker-client-ugreen", compose)
        self.assertIn(f"image: {OFFICIAL_IMAGE}", compose)
        self.assertIn("pull_policy: always", compose)
        self.assertIn("./konfiguration:/konfiguration", compose)
        self.assertNotIn("\n    build:", compose)

    def test_obsolete_files_are_removed(self) -> None:
        for relative_path in REMOVED_LEGACY_FILES:
            with self.subTest(path=relative_path):
                self.assertFalse((ROOT / relative_path).exists())


if __name__ == "__main__":
    unittest.main()
