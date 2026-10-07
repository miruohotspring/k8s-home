#!/usr/bin/env python3
"""Dependency-free safety contracts for the Cloudflare Access Terraform root."""
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
ROOT = REPO / "infra" / "terraform" / "cloudflare-access"
WORKFLOW = REPO / ".github" / "workflows" / "cloudflare-access.yml"
BOOTSTRAP = REPO / "infra" / "terraform" / "github-actions" / "access-backend.tf"


class CloudflareAccessContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terraform = "\n".join(
            path.read_text() for path in sorted(ROOT.glob("*.tf"))
        )
        cls.workflow = WORKFLOW.read_text()
        cls.bootstrap = BOOTSTRAP.read_text()

    def test_first_apply_and_shared_organization_are_guarded(self):
        self.assertIn("depends_on = [cloudflare_zero_trust_organization.this]", self.terraform)
        self.assertIn("terraform state show cloudflare_zero_trust_organization.this", self.workflow)
        self.assertIn("git/ref/heads/main", self.workflow)
        self.assertIn('workspace_key_prefix', self.terraform)
        self.assertIn('platform/cloudflare-access/workspaces/', self.bootstrap)

    def test_dedicated_encrypted_state_and_pinned_provider(self):
        self.assertIn('source  = "cloudflare/cloudflare"', self.terraform)
        self.assertIn('version = "5.27.0"', self.terraform)
        self.assertIn('key          = "platform/cloudflare-access/terraform.tfstate"', self.terraform)
        self.assertIn("encrypt      = true", self.terraform)
        self.assertIn("use_lockfile = true", self.terraform)

    def test_only_intended_zero_trust_resources_are_managed(self):
        self.assertEqual(
            set(re.findall(r'^resource\s+"([^"]+)"\s+"', self.terraform, re.M)),
            {
                "cloudflare_zero_trust_organization",
                "cloudflare_zero_trust_access_application",
                "cloudflare_zero_trust_access_policy",
            },
        )
        self.assertIn('allowed_idps     = [var.email_otp_identity_provider_id]', self.terraform)
        self.assertIn('auto_redirect_to_identity = each.key == "hermes"', self.terraform)
        self.assertNotIn("cloudflare_zero_trust_access_identity_provider", self.terraform)
        self.assertNotIn("cloudflare_zero_trust_access_group", self.terraform)
        self.assertIn("prevent_destroy = true", self.terraform)

    def test_access_contract_is_totp_email_otp_and_720_hours(self):
        for callback in (
            "https://argocd.miruohotspring.net/auth/callback",
            "https://argocd.miruohotspring.net/api/dex/callback",
            "https://argocd.miruohotspring.net/pkce/verify",
            "http://localhost:8085/auth/callback",
            "https://hermes.miruohotspring.net/auth/callback",
            "https://api-drive.miruohotspring.net/v1/auth/callback",
        ):
            self.assertIn(callback, self.terraform)
        self.assertIn('allowed_authenticators = ["totp"]', self.terraform)
        self.assertIn('amr_matching_session_duration = "0m"', self.terraform)
        self.assertIn('session_duration              = "720h"', self.terraform)
        self.assertIn('session_duration = "720h"', self.terraform)
        self.assertIn('access_token_lifetime            = "10m"', self.terraform)
        self.assertIn('lifetime = "719h"', self.terraform)
        self.assertIn('allow_pkce_without_secret = true', self.terraform)
        self.assertIn('allow_pkce_without_secret = false', self.terraform)
        self.assertIn('allow_pkce_without_client_secret = each.value.allow_pkce_without_secret', self.terraform)
        self.assertIn('grant_types                      = each.key == "argocd" ? ["authorization_code", "refresh_tokens"] : ["authorization_code_with_pkce", "refresh_tokens"]', self.terraform)
        self.assertIn('mfa_disabled           = false', self.terraform)
        self.assertNotIn('"groups"', self.terraform)

    def test_allowlists_are_a_single_sensitive_map_with_static_app_keys(self):
        self.assertRegex(
            self.terraform,
            r'variable "allowed_emails" \{[\s\S]*?type\s+=\s+map\(set\(string\)\)[\s\S]*?sensitive\s+=\s+true',
        )
        self.assertIn("for_each = local.apps", self.terraform)
        self.assertNotRegex(self.terraform, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")

    def test_bootstrap_role_is_limited_to_the_single_state_key(self):
        self.assertIn('name = "github-actions-k8s-home-cloudflare-access"', self.bootstrap)
        self.assertIn('repo:miruohotspring/k8s-home:ref:refs/heads/main', self.bootstrap)
        self.assertIn('token.actions.githubusercontent.com:aud', self.bootstrap)
        self.assertIn('platform/cloudflare-access/terraform.tfstate', self.bootstrap)
        self.assertIn('platform/cloudflare-access/terraform.tfstate.tflock', self.bootstrap)
        self.assertNotIn('s3:*', self.bootstrap)
        self.assertNotIn('"Resource": "*"', self.bootstrap)

    def test_workflow_is_pr_safe_and_manual_apply_uses_saved_plan(self):
        self.assertIn("pull_request:", self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn("init -backend=false", self.workflow)
        self.assertIn("terraform validate", self.workflow)
        self.assertIn("scripts/test-cloudflare-access-contract.py", self.workflow)
        self.assertIn("persona: pedantic", self.workflow)
        self.assertIn("CLOUDFLARE_ACCESS_API_TOKEN", self.workflow)
        self.assertIn("CLOUDFLARE_ACCESS_ALLOWED_EMAILS_JSON", self.workflow)
        self.assertIn("TF_VAR_allowed_emails", self.workflow)
        self.assertIn("CLOUDFLARE_ACCESS_STATE_ROLE_ARN", self.workflow)
        self.assertIn("terraform show -json tfplan", self.workflow)
        self.assertIn("terraform apply -input=false -auto-approve tfplan", self.workflow)
        self.assertIn("delete", self.workflow)
        self.assertIn("replace", self.workflow)
        self.assertNotIn("upload-artifact", self.workflow)
        self.assertNotIn("actions/upload-artifact", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)


if __name__ == "__main__":
    unittest.main()
