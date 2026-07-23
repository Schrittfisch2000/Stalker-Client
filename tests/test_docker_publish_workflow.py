from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
REMOVED_WORKFLOWS = (
    ROOT / ".github" / "workflows" / "docker-publish.yml",
    ROOT / ".github" / "workflows" / "tests.yml",
)


class DockerPublishWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_only_one_workflow_remains(self) -> None:
        self.assertTrue(CI_WORKFLOW.exists())
        for workflow in REMOVED_WORKFLOWS:
            with self.subTest(path=workflow.name):
                self.assertFalse(workflow.exists())

    def test_ci_checks_only_the_ugreen_compose_file(self) -> None:
        self.assertIn("docker compose -f docker-compose.yml config", self.ci)
        self.assertNotIn("docker-compose-ugreen.yml", self.ci)
        self.assertNotIn("docker-compose-synology.yml", self.ci)
        self.assertNotIn("deploy/standard", self.ci)
        self.assertNotIn("deploy/ugreen", self.ci)

    def test_publish_runs_after_successful_main_tests(self) -> None:
        self.assertIn("needs: test", self.ci)
        self.assertIn("github.event_name != 'pull_request'", self.ci)
        self.assertIn("github.ref == 'refs/heads/main'", self.ci)
        self.assertIn("docker/login-action@v3", self.ci)
        self.assertIn("docker/build-push-action@v6", self.ci)

    def test_release_has_write_permission_for_tags_and_releases(self) -> None:
        self.assertIn("contents: write", self.ci)
        self.assertIn('git push origin "$TAG"', self.ci)
        self.assertIn('gh release create "$TAG"', self.ci)

    def test_release_uses_versioned_and_latest_tags(self) -> None:
        self.assertIn("IMAGE_NAME: schrittfisch2000/stalker-client", self.ci)
        self.assertIn("${{ env.IMAGE_NAME }}:${{ steps.version.outputs.version }}", self.ci)
        self.assertIn("${{ env.IMAGE_NAME }}:${{ steps.version.outputs.tag }}", self.ci)
        self.assertIn("${{ env.IMAGE_NAME }}:latest", self.ci)

    def test_release_targets_ugreen_architectures(self) -> None:
        self.assertIn("platforms: linux/amd64,linux/arm64", self.ci)
        self.assertIn("UGREEN NAS", self.ci)
        self.assertIn("cache-from: type=gha", self.ci)
        self.assertIn("cache-to: type=gha,mode=max", self.ci)

    def test_release_checks_credentials_inside_publish_job(self) -> None:
        self.assertIn("Docker-Hub-Zugang prüfen", self.ci)
        self.assertIn('[[ -z "$HUB_USERNAME" || -z "$HUB_TOKEN" ]]', self.ci)


if __name__ == "__main__":
    unittest.main()
