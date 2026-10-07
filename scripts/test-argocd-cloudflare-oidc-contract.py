#!/usr/bin/env python3
"""Static safety contracts for the staged Argo CD Cloudflare Access cutover."""
import pathlib
import re
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
ARGO = REPO / "apps" / "argocd"


class ArgoCDCloudflareOIDCContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cm = (ARGO / "argocd-cm.yaml").read_text()
        cls.app = (ARGO / "application.yaml").read_text()
        cls.kustomization = (ARGO / "kustomization.yaml").read_text()
        cls.rbac_patch = (ARGO / "argocd-cloudflare-rbac-patch.yaml").read_text()
        cls.sealed_secret = (ARGO / "argocd-cloudflare-oidc-sealed.yaml").read_text()
        cls.runbook = (REPO / "docs" / "argocd-cloudflare-access-oidc-runbook.md").read_text()

    def test_secret_is_visible_to_argocd_settings_watcher(self):
        self.assertRegex(self.sealed_secret, r"(?m)^      labels:\n        app\.kubernetes\.io/part-of: argocd$")

    def test_phase_b_oidc_uses_only_sealed_references_and_no_groups_claim(self):
        self.assertIn("admin.enabled: \"true\"", self.cm)
        self.assertIn("users.session.duration: \"720h\"", self.cm)
        self.assertIn("name: Cloudflare Access", self.cm)
        for secret_key in ("issuer", "clientID", "clientSecret"):
            self.assertIn(f"$argocd-cloudflare-oidc:{secret_key}", self.cm)
        self.assertIn('scopes: ["openid", "profile", "email"]', self.cm)
        self.assertNotIn("requestedIDTokenClaims", self.cm)
        self.assertNotIn('"groups"', self.cm)
        self.assertNotRegex(self.cm, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")

    def test_bundled_dex_brokers_confidential_upstream_and_web_cli_clients(self):
        self.assertIn("dex.config:", self.cm)
        self.assertNotIn("oidc.config:", self.cm)
        self.assertIn("redirectURI: https://argocd.miruohotspring.net/api/dex/callback", self.cm)
        self.assertIn("clientSecret: $argocd-cloudflare-oidc:clientSecret", self.cm)

    def test_otp_display_name_mapping_preserves_subject_and_verification(self):
        self.assertIn("userNameKey: email", self.cm)
        self.assertNotIn("userIDKey:", self.cm)
        # Access verifies the approved account upstream; its ID token omits this
        # optional OIDC claim. Trust only this pinned connector, not arbitrary IdPs.
        self.assertIn("insecureSkipEmailVerified: true", self.cm)
        self.assertIn('promptType: ""', self.cm)
        self.assertNotIn("insecureSkipVerify: true", self.cm)

    def test_sealed_secret_contains_only_encrypted_generated_values(self):
        self.assertIn("kind: SealedSecret", self.sealed_secret)
        self.assertIn("name: argocd-cloudflare-oidc", self.sealed_secret)
        for key in ("issuer", "clientID", "clientSecret", "rbac-patch.json"):
            self.assertRegex(self.sealed_secret, rf"(?m)^    {re.escape(key)}: .+")
        self.assertNotIn("\nstringData:", self.sealed_secret)
        self.assertNotRegex(self.sealed_secret, r"(?m)^data:")
        self.assertNotRegex(self.sealed_secret, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")

    def test_postsync_patch_job_has_no_secret_api_permission(self):
        self.assertIn("kind: Job", self.rbac_patch)
        self.assertIn("argocd.argoproj.io/hook: PostSync", self.rbac_patch)
        self.assertIn("argocd.argoproj.io/hook-delete-policy: BeforeHookCreation,HookSucceeded", self.rbac_patch)
        self.assertIn("activeDeadlineSeconds: 120", self.rbac_patch)
        self.assertIn("backoffLimit: 1", self.rbac_patch)
        self.assertIn(
            "registry.k8s.io/kubectl@sha256:1c6309bd167feb49b2bc1605bce05973002872fd0d26a2e76499ed0c903ea3cf",
            self.rbac_patch,
        )
        self.assertIn("serviceAccountName: argocd-rbac-patch", self.rbac_patch)
        self.assertIn("automountServiceAccountToken: true", self.rbac_patch)
        self.assertIn("runAsNonRoot: true", self.rbac_patch)
        self.assertIn("readOnlyRootFilesystem: true", self.rbac_patch)
        self.assertIn("allowPrivilegeEscalation: false", self.rbac_patch)
        self.assertIn("resourceNames:", self.rbac_patch)
        self.assertIn("- argocd-rbac-cm", self.rbac_patch)
        self.assertIn('verbs: ["get", "patch"]', self.rbac_patch)
        self.assertNotIn("secrets", self.rbac_patch)
        self.assertIn("key: rbac-patch.json", self.rbac_patch)
        self.assertNotIn("key: clientSecret", self.rbac_patch)
        self.assertIn("--patch-file=/patch/rbac-patch.json", self.rbac_patch)

    def test_generated_policy_key_is_preserved_by_its_owner_application(self):
        self.assertIn("RespectIgnoreDifferences=true", self.app)
        self.assertIn("name: argocd-rbac-cm", self.app)
        self.assertIn("namespace: argocd", self.app)
        self.assertIn("/data/policy.cloudflare.csv", self.app)


    def test_phase_order_and_recovery_are_documented(self):
        self.assertIn("Phase A", self.runbook)
        self.assertIn("Phase B", self.runbook)
        self.assertIn("SealedSecret", self.runbook)
        self.assertIn("PostSync", self.runbook)
        self.assertIn("admin.enabled", self.runbook)
        self.assertIn("rollback", self.runbook.lower())

    def test_resources_are_rendered_from_argocd_application_path(self):
        for resource in (
            "argocd-cloudflare-oidc-sealed.yaml",
            "argocd-cloudflare-rbac-patch.yaml",
        ):
            self.assertIn(resource, self.kustomization)


if __name__ == "__main__":
    unittest.main()
