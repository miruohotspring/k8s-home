#!/usr/bin/env python3
"""Behavioral contracts for the rendered shared Cloudflare connector."""

from pathlib import Path
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class CloudflaredHAContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rendered = subprocess.run(
            ["kubectl", "kustomize", "infra/cloudflared"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
        cls.resources = list(yaml.safe_load_all(rendered))
        cls.deployment = next(r for r in cls.resources if r["kind"] == "Deployment")
        cls.spec = cls.deployment["spec"]
        cls.pod = cls.spec["template"]

    def test_rollout_keeps_existing_connector_available(self):
        self.assertEqual(2, self.spec["replicas"])
        self.assertEqual("RollingUpdate", self.spec["strategy"]["type"])
        self.assertEqual({"maxUnavailable": 0, "maxSurge": 1}, self.spec["strategy"]["rollingUpdate"])

    def test_connector_spread_uses_matching_labels_without_hard_anti_affinity(self):
        labels = self.spec["selector"]["matchLabels"]
        self.assertEqual({"app": "cloudflared"}, labels)
        self.assertTrue(labels.items() <= self.pod["metadata"]["labels"].items())
        constraints = self.pod["spec"].get("topologySpreadConstraints", [])
        self.assertEqual(1, len(constraints))
        constraint = constraints[0]
        self.assertEqual(1, constraint["maxSkew"])
        self.assertEqual("kubernetes.io/hostname", constraint["topologyKey"])
        self.assertEqual("DoNotSchedule", constraint["whenUnsatisfiable"])
        self.assertEqual({"matchLabels": labels}, constraint["labelSelector"])
        anti_affinity = self.pod["spec"].get("affinity", {}).get("podAntiAffinity", {})
        self.assertFalse(anti_affinity.get("requiredDuringSchedulingIgnoredDuringExecution"))

    def test_pdb_protects_one_matching_connector(self):
        pdbs = [r for r in self.resources if r["kind"] == "PodDisruptionBudget"]
        self.assertEqual(1, len(pdbs))
        pdb = pdbs[0]
        self.assertEqual("policy/v1", pdb["apiVersion"])
        self.assertEqual(self.deployment["metadata"]["namespace"], pdb["metadata"]["namespace"])
        self.assertEqual(1, pdb["spec"]["minAvailable"])
        self.assertEqual({"matchLabels": self.spec["selector"]["matchLabels"]}, pdb["spec"]["selector"])

    def test_existing_connection_and_health_contract_is_preserved(self):
        containers = self.pod["spec"]["containers"]
        self.assertEqual(1, len(containers))
        container = containers[0]
        self.assertEqual("cloudflared", container["name"])
        self.assertRegex(container["image"], r"^cloudflare/cloudflared:[^@]+@sha256:[0-9a-f]{64}$")
        self.assertEqual(["tunnel", "--no-autoupdate", "--metrics", "0.0.0.0:2000", "run"], container["args"])
        self.assertEqual([{"secretRef": {"name": "cloudflared-tunnel-token"}}], container["envFrom"])
        self.assertEqual({"requests": {"cpu": "50m", "memory": "64Mi"},
                          "limits": {"cpu": "200m", "memory": "256Mi"}}, container["resources"])
        for probe in ("readinessProbe", "livenessProbe"):
            with self.subTest(probe=probe):
                self.assertEqual({"path": "/ready", "port": 2000}, container[probe]["httpGet"])


if __name__ == "__main__":
    unittest.main()
