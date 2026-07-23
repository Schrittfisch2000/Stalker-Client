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
    "CHANGELOG-1.0.31.md",
    "RELEASE-1.0.31.md",
    "CHANGELOG-1.0.32.md",
    "RELEASE-1.0.32.md",
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

    def test_readme_documents_supported_docker_targets(self) -> None:
        readme = self.read("README.md")
        self.assertIn("UGREEN NAS", readme)
        self.assertIn("Installation auf Linux", readme)
        self.assertIn("Installation auf macOS", readme)
        self.assertIn("Installation auf Raspberry Pi", readme)
        self.assertIn("Installation auf Windows", readme)
        self.assertIn("UGREEN-Installation direkt aus dem Docker-Hub-Repository", readme)
        self.assertIn("linux/amd64", readme)
        self.assertIn("linux/arm64", readme)
        self.assertIn(OFFICIAL_IMAGE, readme)

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

    def test_repository_image_defaults_use_writable_configuration_directory(self) -> None:
        dockerfile = self.read("Dockerfile")
        storage = self.read("app/storage.py")
        logging_config = self.read("app/logging_config.py")

        self.assertIn("MAIN_DIRECTORY=/konfiguration", dockerfile)
        self.assertIn("CONFIG_FILE=/konfiguration/portal-einstellungen.json", dockerfile)
        self.assertIn("SECRET_FILE=/konfiguration/.stalker-geheimnis", dockerfile)
        self.assertIn("LOG_FILE=/konfiguration/stalker-client.log", dockerfile)
        self.assertIn('os.getenv("MAIN_DIRECTORY", "/konfiguration")', storage)
        self.assertIn('os.getenv("LOG_FILE", "/konfiguration/stalker-client.log")', logging_config)
        self.assertNotIn("/config/stalker-client.log", logging_config)
        self.assertNotIn("/hauptordner", storage)

    def test_obsolete_files_are_removed(self) -> None:
        for relative_path in REMOVED_LEGACY_FILES:
            with self.subTest(path=relative_path):
                self.assertFalse((ROOT / relative_path).exists())


if __name__ == "__main__":
    unittest.main()
