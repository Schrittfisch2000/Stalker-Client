from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"\b\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?\b")


class VersionConsistencyTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_readme_current_version_matches_application(self) -> None:
        readme = self.read("README.md")
        match = re.search(r"\*\*Aktuelle Version: ([0-9]+\.[0-9]+\.[0-9]+)", readme)
        self.assertIsNotNone(match, "README enthält keine aktuelle Versionsangabe")
        self.assertEqual(match.group(1), APP_VERSION)

    def test_frontend_uses_only_application_version(self) -> None:
        template = self.read("app/templates/index.html")
        versions = set(VERSION_PATTERN.findall(template))
        self.assertEqual(versions, {APP_VERSION})

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
