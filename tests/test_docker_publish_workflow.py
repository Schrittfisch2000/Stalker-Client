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

    def test_release_is_reusable_and_manually_runnable(self) -> None:
        self.assertIn("workflow_call:", self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("branches:\n      - main", self.workflow)

    def test_ci_publishes_only_after_successful_main_tests(self) -> None:
        self.assertIn("needs: test", self.ci)
        self.assertIn("github.event_name == 'push'", self.ci)
        self.assertIn("github.ref == 'refs/heads/main'", self.ci)
        self.assertIn("uses: ./.github/workflows/docker-publish.yml", self.ci)
        self.assertIn("secrets: inherit", self.ci)

    def test_release_cancels_outdated_runs(self) -> None:
        self.assertIn("group: docker-release-${{ github.repository }}", self.workflow)
        self.assertIn("cancel-in-progress: true", self.workflow)

    def test_release_has_write_permission(self) -> None:
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

    def test_release_checks_credentials_inside_the_running_job(self) -> None:
        self.assertNotIn("required: true", self.workflow)
        self.assertIn("Docker-Hub-Zugang prüfen", self.workflow)
        self.assertIn('[[ -z "$HUB_USERNAME" || -z "$HUB_TOKEN" ]]', self.workflow)
        self.assertIn("docker/login-action@v3", self.workflow)

    def test_release_reports_success_and_failure_with_run_link(self) -> None:
        self.assertIn("Veröffentlichung erfolgreich melden", self.workflow)
        self.assertIn("Veröffentlichung fehlgeschlagen melden", self.workflow)
        self.assertIn("actions/runs/${GITHUB_RUN_ID}", self.workflow)
        self.assertIn('REPORT_ISSUE: "19"', self.workflow)


if __name__ == "__main__":
    unittest.main()
