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

    def test_publish_starts_only_after_successful_main_tests(self) -> None:
        self.assertIn("publish-dockerhub:", self.ci)
        self.assertIn("needs: test", self.ci)
        self.assertIn("github.event_name != 'pull_request'", self.ci)
        self.assertIn("github.ref == 'refs/heads/main'", self.ci)

    def test_publish_uses_dockerhub_secrets(self) -> None:
        self.assertIn("docker/login-action@v3", self.ci)
        self.assertIn("secrets.DOCKERHUB_USERNAME", self.ci)
        self.assertIn("secrets.DOCKERHUB_TOKEN", self.ci)
        self.assertNotIn("Publishing wird übersprungen", self.ci)
        self.assertNotIn("DOCKERHUB_AVAILABLE=false", self.ci)

    def test_publish_builds_amd64_and_arm64(self) -> None:
        self.assertIn("docker/setup-qemu-action@v3", self.ci)
        self.assertIn("docker/setup-buildx-action@v3", self.ci)
        self.assertIn("docker/build-push-action@v6", self.ci)
        self.assertIn("platforms: linux/amd64,linux/arm64", self.ci)
        self.assertIn("push: true", self.ci)

    def test_release_publishes_all_public_tags(self) -> None:
        self.assertIn("IMAGE_NAME: schrittfisch2000/stalker-client", self.ci)
        self.assertIn("${{ env.IMAGE_NAME }}:latest", self.ci)
        self.assertIn("${{ env.IMAGE_NAME }}:${{ steps.version.outputs.version }}", self.ci)
        self.assertIn("${{ env.IMAGE_NAME }}:${{ steps.version.outputs.tag }}", self.ci)

    def test_manifest_verifies_both_architectures(self) -> None:
        self.assertIn("Docker-Hub-Manifest prüfen", self.ci)
        self.assertIn("docker buildx imagetools inspect", self.ci)
        self.assertIn('{"amd64", "arm64"} - architectures', self.ci)

    def test_release_creates_git_tag_and_github_release_last(self) -> None:
        publish_position = self.ci.index("Multi-Arch-Image bauen und veröffentlichen")
        manifest_position = self.ci.index("Docker-Hub-Manifest prüfen")
        tag_position = self.ci.index("Git-Tag erstellen, falls er fehlt")
        release_position = self.ci.index("GitHub Release erstellen, falls es fehlt")
        self.assertLess(publish_position, manifest_position)
        self.assertLess(manifest_position, tag_position)
        self.assertLess(tag_position, release_position)
        self.assertIn('git push origin "$TAG"', self.ci)
        self.assertIn('gh release create "$TAG"', self.ci)


if __name__ == "__main__":
    unittest.main()
