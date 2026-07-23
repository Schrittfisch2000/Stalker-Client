from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "docker-publish.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class DockerPublishWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        cls.ci = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_manual_release_workflow_remains_available(self) -> None:
        self.assertIn("workflow_call:", self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("branches:\n      - main", self.workflow)

    def test_ci_publishes_directly_after_successful_main_tests(self) -> None:
        self.assertIn("needs: test", self.ci)
        self.assertIn("github.event_name == 'push'", self.ci)
        self.assertIn("github.ref == 'refs/heads/main'", self.ci)
        self.assertNotIn("uses: ./.github/workflows/docker-publish.yml", self.ci)
        self.assertIn("Veröffentlichung gestartet melden", self.ci)
        self.assertIn("docker/login-action@v3", self.ci)
        self.assertIn("docker/build-push-action@v6", self.ci)

    def test_release_has_write_permissions(self) -> None:
        self.assertIn("contents: write", self.ci)
        self.assertIn("issues: write", self.ci)
        self.assertIn('git push origin "$TAG"', self.ci)
        self.assertIn('gh release create "$TAG"', self.ci)

    def test_release_uses_version_file_and_official_image(self) -> None:
        self.assertIn('< VERSION', self.ci)
        self.assertIn("IMAGE_NAME: schrittfisch2000/stalker-client", self.ci)
        self.assertIn("${{ env.IMAGE_NAME }}:${{ steps.version.outputs.tag }}", self.ci)
        self.assertIn("${{ env.IMAGE_NAME }}:latest", self.ci)

    def test_release_publishes_supported_architectures_and_uses_cache(self) -> None:
        self.assertIn("platforms: linux/amd64,linux/arm64", self.ci)
        self.assertIn("cache-from: type=gha", self.ci)
        self.assertIn("cache-to: type=gha,mode=max", self.ci)

    def test_release_checks_credentials_inside_the_job(self) -> None:
        self.assertIn("Docker-Hub-Zugang prüfen", self.ci)
        self.assertIn('[[ -z "$HUB_USERNAME" || -z "$HUB_TOKEN" ]]', self.ci)

    def test_release_reports_start_success_and_failure_with_run_link(self) -> None:
        self.assertIn("Veröffentlichung gestartet melden", self.ci)
        self.assertIn("Veröffentlichung erfolgreich melden", self.ci)
        self.assertIn("Veröffentlichung fehlgeschlagen melden", self.ci)
        self.assertIn("actions/runs/${GITHUB_RUN_ID}", self.ci)
        self.assertIn('REPORT_ISSUE: "19"', self.ci)


if __name__ == "__main__":
    unittest.main()
