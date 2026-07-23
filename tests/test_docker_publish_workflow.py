from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "docker-publish.yml"


class DockerPublishWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_release_runs_after_main_updates(self) -> None:
        self.assertIn("branches:\n      - main", self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)

    def test_release_has_write_permission_for_tags_releases_and_reporting(self) -> None:
        self.assertIn("contents: write", self.workflow)
        self.assertIn("issues: write", self.workflow)
        self.assertIn('git push origin "$TAG"', self.workflow)
        self.assertIn('gh release create "$TAG"', self.workflow)

    def test_release_uses_version_file_and_official_image(self) -> None:
        self.assertIn('< VERSION', self.workflow)
        self.assertIn("IMAGE_NAME: schrittfisch2000/stalker-client", self.workflow)
        self.assertIn("${{ env.IMAGE_NAME }}:${{ steps.version.outputs.tag }}", self.workflow)
        self.assertIn("${{ env.IMAGE_NAME }}:latest", self.workflow)

    def test_release_publishes_supported_architectures(self) -> None:
        self.assertIn("platforms: linux/amd64,linux/arm64", self.workflow)

    def test_release_uses_docker_hub_secrets(self) -> None:
        self.assertIn("secrets.DOCKERHUB_USERNAME", self.workflow)
        self.assertIn("secrets.DOCKERHUB_TOKEN", self.workflow)

    def test_release_reports_success_and_failure_with_run_link(self) -> None:
        self.assertIn("Veröffentlichung erfolgreich melden", self.workflow)
        self.assertIn("Veröffentlichung fehlgeschlagen melden", self.workflow)
        self.assertIn("actions/runs/${GITHUB_RUN_ID}", self.workflow)
        self.assertIn('REPORT_ISSUE: "19"', self.workflow)


if __name__ == "__main__":
    unittest.main()
