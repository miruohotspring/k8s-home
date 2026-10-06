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
