#!/usr/bin/env python3
"""Safety contracts for Google identity GitHub Actions federation."""
import pathlib
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
ROOT = REPO / "infra" / "terraform" / "google-identity"
BACKEND = REPO / "infra" / "terraform" / "github-actions" / "google-identity-backend.tf"
WORKFLOW = REPO / ".github" / "workflows" / "google-identity.yml"


class GoogleIdentityContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terraform = "\n".join(path.read_text() for path in sorted(ROOT.glob("*.tf")))
        cls.backend = BACKEND.read_text() if BACKEND.exists() else ""
        cls.workflow = WORKFLOW.read_text() if WORKFLOW.exists() else ""

    def test_github_uses_keyless_google_federation(self):
        self.assertIn('resource "google_iam_workload_identity_pool" "github"', self.terraform)
        self.assertIn('resource "google_iam_workload_identity_pool_provider" "github"', self.terraform)
        self.assertIn('assertion.repository == \\"miruohotspring/k8s-home\\"', self.terraform)
        self.assertIn('assertion.ref == \\"refs/heads/main\\"', self.terraform)
        self.assertIn('resource "google_service_account" "github_actions"', self.terraform)
        self.assertNotIn("google_service_account_key", self.terraform)
        self.assertNotIn("private_key", self.terraform)

    def test_state_role_is_limited_to_google_identity_state(self):
        self.assertIn('name = "github-actions-k8s-home-google-identity"', self.backend)
        self.assertIn('platform/google-identity/terraform.tfstate', self.backend)
        self.assertIn('platform/google-identity/terraform.tfstate.tflock', self.backend)
        self.assertNotIn('s3:*', self.backend)
        self.assertNotIn('"Resource": "*"', self.backend)

    def test_workflow_uses_oidc_and_saved_plan(self):
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", self.workflow)
        self.assertIn("GCP_WORKLOAD_IDENTITY_PROVIDER", self.workflow)
        self.assertIn("GCP_GOOGLE_IDENTITY_SERVICE_ACCOUNT", self.workflow)
        self.assertIn("terraform show -json tfplan", self.workflow)
        self.assertIn("terraform apply -input=false -auto-approve tfplan", self.workflow)
        self.assertIn("delete", self.workflow)
        self.assertIn("replace", self.workflow)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS_JSON", self.workflow)
        self.assertNotIn("service_account_key", self.workflow)

    def test_state_is_encrypted_and_provider_is_pinned(self):
        self.assertIn('source  = "hashicorp/google"', self.terraform)
        self.assertIn('version = "8.7.0"', self.terraform)
        self.assertIn('key          = "platform/google-identity/terraform.tfstate"', self.terraform)
        self.assertIn("encrypt      = true", self.terraform)
        self.assertIn("use_lockfile = true", self.terraform)


if __name__ == "__main__":
    unittest.main()
