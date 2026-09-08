#!/usr/bin/env python3
"""Validate cloud-drive platform registration in k8s-home."""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = "git@github.com:miruohotspring/cloud-drive-gitops.git"
DESTINATION = {"namespace": "cloud-drive-prod", "server": "https://kubernetes.default.svc"}


class CloudDrivePlatformTest(unittest.TestCase):
    def test_argocd_application_tracks_the_dedicated_gitops_repo(self):
        application = yaml.safe_load((ROOT / "apps/cloud-drive/application.yaml").read_text())
        self.assertEqual(application["metadata"]["name"], "cloud-drive-prod")
        self.assertEqual(application["spec"]["source"]["repoURL"], REPO)
        self.assertEqual(application["spec"]["source"]["path"], "app/overlays/prod")
        self.assertEqual(application["spec"]["destination"], DESTINATION)
        self.assertTrue(application["spec"]["syncPolicy"]["automated"]["prune"])
        self.assertTrue(application["spec"]["syncPolicy"]["automated"]["selfHeal"])

    def test_apps_project_allows_only_the_expected_repo_and_namespace(self):
        for relative in (
            "bootstrap/projects/project-apps.yaml",
            "bootstrap/root-app/project-apps.yaml",
        ):
            project = yaml.safe_load((ROOT / relative).read_text())
            self.assertIn(REPO, project["spec"]["sourceRepos"])
            self.assertIn(DESTINATION, project["spec"]["destinations"])

    def test_required_sealed_secrets_are_scoped_and_contain_expected_keys(self):
        expected = {
            "authentik-cloud-drive-env-sealed.yaml": (
                "authentik",
                "authentik-cloud-drive-env",
                {"AUTHENTIK_CLOUD_DRIVE_CLIENT_SECRET"},
            ),
            "cloud-drive-github-ssh-app-sealed.yaml": (
                "concourse-main",
                "cloud-drive-github-ssh-app",
                {"private_key"},
            ),
            "cloud-drive-github-ssh-gitops-sealed.yaml": (
                "concourse-main",
                "cloud-drive-github-ssh-gitops",
                {"private_key"},
            ),
            "argocd-repo-cloud-drive-gitops-sealed.yaml": (
                "argocd",
                "argocd-repo-cloud-drive-gitops",
                {"type", "url", "sshPrivateKey"},
            ),
        }
        for filename, (namespace, name, keys) in expected.items():
            document = yaml.safe_load((ROOT / "infra/secrets" / filename).read_text())
            self.assertEqual(document["metadata"]["namespace"], namespace)
            self.assertEqual(document["metadata"]["name"], name)
            self.assertLessEqual(keys, set(document["spec"]["encryptedData"]))


if __name__ == "__main__":
    unittest.main()
