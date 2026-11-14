#!/usr/bin/env python3
"""Source contracts for the final Concourse retirement."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

RETIRED_SECRET_FILES = (
    "concourse-admin-sealed.yaml",
    "concourse-worker-sealed.yaml",
    "concourse-web-sealed.yaml",
    "concourse-argocd-creds-sealed.yaml",
    "concourse-aws-creds-sealed.yaml",
    "concourse-cloudflare-creds-sealed.yaml",
    "telegram-creds-sealed.yaml",
    "cloud-drive-github-ssh-app-sealed.yaml",
    "cloud-drive-github-ssh-gitops-sealed.yaml",
    "cloud-drive-r2-state-sealed.yaml",
    "cloud-drive-runtime-sealed.yaml",
    "web-app-template-github-ssh-app-sealed.yaml",
    "web-app-template-github-ssh-gitops-sealed.yaml",
)


class ConcourseRetirementContractTest(unittest.TestCase):
    def test_operational_concourse_application_and_values_are_absent(self) -> None:
        self.assertFalse((ROOT / "infra/concourse").exists())

    def test_concourse_runtime_credentials_are_absent_from_gitops(self) -> None:
        secrets = ROOT / "infra/secrets"
        remaining = [name for name in RETIRED_SECRET_FILES if (secrets / name).exists()]
        self.assertEqual([], remaining)

    def test_authentik_blueprint_and_secret_no_longer_define_concourse(self) -> None:
        blueprint = (ROOT / "infra/authentik/manifests/platform-blueprint.yaml").read_text()
        authentik_secret = (ROOT / "infra/secrets/authentik-env-sealed.yaml").read_text()
        self.assertNotIn("concourse-provider", blueprint)
        self.assertNotIn("slug: concourse", blueprint)
        self.assertNotIn("concourse.miruohotspring.net", blueprint)
        self.assertNotIn("AUTHENTIK_CONCOURSE_CLIENT_SECRET", authentik_secret)

    def test_namespaces_and_argocd_projects_no_longer_allow_concourse(self) -> None:
        paths = (
            ROOT / "namespaces.yaml",
            ROOT / "bootstrap/root-app/project-apps.yaml",
            ROOT / "bootstrap/root-app/project-infra.yaml",
            ROOT / "bootstrap/projects/project-apps.yaml",
            ROOT / "bootstrap/projects/project-infra.yaml",
        )
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                self.assertNotIn("name: concourse", text)
                self.assertNotIn("namespace: concourse", text)
                self.assertNotIn("namespace: concourse-main", text)

    def test_active_docs_do_not_direct_operators_back_to_concourse(self) -> None:
        active_docs = (
            ROOT / "README.md",
            ROOT / "docs/bootstrap-proxmox.md",
            ROOT / "docs/runbook-authentik.md",
            ROOT / "docs/runbook-github-actions.md",
        )
        forbidden = (
            "https://concourse.miruohotspring.net",
            "fly -t home",
            "concourse-main",
            "concourse-aws-creds-sealed.yaml",
            "cloud-drive-runtime-sealed.yaml",
            "web-app-template-github-ssh-app-sealed.yaml",
        )
        for path in active_docs:
            text = path.read_text()
            for fragment in forbidden:
                with self.subTest(path=path.relative_to(ROOT), fragment=fragment):
                    self.assertNotIn(fragment, text)

    def test_retirement_record_preserves_backup_and_restore_instructions(self) -> None:
        record = (ROOT / "docs/archive/concourse-retirement.md").read_text()
        self.assertIn("concourse-retirement-20261006T092935Z", record)
        self.assertIn("tables=61", record)
        self.assertIn("pipelines=3", record)
        self.assertIn("builds=79", record)
        self.assertIn("explicit data-destruction approval", record)


if __name__ == "__main__":
    unittest.main()
