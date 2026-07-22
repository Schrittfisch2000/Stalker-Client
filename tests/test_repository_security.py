from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositorySecurityTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_gitignore_protects_runtime_configuration(self) -> None:
        gitignore = set(self.read(".gitignore").splitlines())
        required = {
            "konfiguration/",
            "portal-einstellungen.json",
            "portal-zuweisungen.json",
            "benutzer.json",
            "benutzer-freigaben.json",
            "wiedergabeverlauf.json",
            "favoriten.json",
            "fortschritt.json",
            ".stalker-geheimnis",
            "stalker-client.log",
            "stalker-client.log.*",
        }
        self.assertTrue(required.issubset(gitignore), required - gitignore)

    def test_dockerignore_excludes_runtime_configuration(self) -> None:
        dockerignore = set(self.read(".dockerignore").splitlines())
        self.assertIn("konfiguration", dockerignore)
        self.assertIn(".git", dockerignore)
        self.assertIn("*.log", dockerignore)

    def test_secure_card_renderer_is_loaded_before_extensions(self) -> None:
        template = self.read("app/templates/index.html")
        app_position = template.index("/static/app.js")
        security_position = template.index("/static/card-security.js")
        media_position = template.index("/static/media-ui.js")
        download_position = template.index("/static/download-ui.js")
        self.assertLess(app_position, security_position)
        self.assertLess(security_position, media_position)
        self.assertLess(security_position, download_position)

    def test_secure_card_renderer_uses_dom_properties(self) -> None:
        asset = self.read("app/static/card-security.js")
        self.assertIn("document.createElement('img')", asset)
        self.assertIn("image.src = url.href", asset)
        self.assertIn("title.textContent", asset)
        self.assertIn("description.textContent", asset)
        self.assertIn("new Set(['http:', 'https:'])", asset)
        self.assertNotIn("innerHTML", asset)
        self.assertNotIn("<img", asset)


if __name__ == "__main__":
    unittest.main()
