#!/usr/bin/env python3
"""Validate the ECR pull-secret mirror manifest."""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "infra/manifests/ecr-secret-mirror.yaml"
IMAGE = "python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a"


class EcrSecretMirrorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = MANIFEST.read_text()
        self.documents = [doc for doc in yaml.safe_load_all(self.text) if doc]

    def find(self, kind: str, name: str, namespace: str | None = None) -> dict:
        for document in self.documents:
            metadata = document.get("metadata", {})
            if (
                document.get("kind") == kind
                and metadata.get("name") == name
                and (namespace is None or metadata.get("namespace") == namespace)
            ):
                return document
        self.fail(f"missing {kind} {namespace or '*'} / {name}")

    def test_cronjob_uses_runtime_source_secret_without_aws_credentials(self) -> None:
        cronjob = self.find("CronJob", "ecr-secret-mirror", "default")
        self.assertEqual(cronjob["spec"]["schedule"], "17 * * * *")
        container = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["image"], IMAGE)
        script = container["args"][0]
        compile(script, "ecr-secret-mirror.py", "exec")
        self.assertIn('SOURCE_NAMESPACE = "default"', script)
        self.assertIn('TARGET_NAMESPACES = ("m3usick-dev", "m3usick-prod")', script)
        self.assertNotIn("AWS_ACCESS_KEY", self.text)
        self.assertNotIn("AWS_SECRET", self.text)

    def test_rbac_is_bound_only_in_source_and_target_namespaces(self) -> None:
        self.find("ServiceAccount", "ecr-secret-mirror", "default")
        source_role = self.find("Role", "ecr-secret-mirror-source", "default")
        self.assertEqual(source_role["rules"][0]["resourceNames"], ["ecr-secret"])
        self.assertEqual(source_role["rules"][0]["verbs"], ["get"])
        self.find("RoleBinding", "ecr-secret-mirror-source", "default")

        for namespace in ("m3usick-dev", "m3usick-prod"):
            role = self.find("Role", "ecr-secret-mirror-target", namespace)
            self.assertEqual(
                role["rules"][0]["verbs"],
                ["get", "create", "update", "patch"],
            )
            binding = self.find("RoleBinding", "ecr-secret-mirror-target", namespace)
            self.assertEqual(binding["subjects"][0]["namespace"], "default")


if __name__ == "__main__":
    unittest.main()
