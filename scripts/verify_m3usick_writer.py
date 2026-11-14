#!/usr/bin/env python3
"""Verify that GitHub Actions is the post-retirement m3usick GitOps writer.

This check deliberately verifies source and GitHub configuration only.  It does not
contact or modify the Kubernetes cluster.  After the removal commit is synced,
run the cluster read-back checks recorded in docs/concourse-retirement-inventory.md.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M3USICK_REPOSITORY = "gammaLaboratory/m3usick"
M3USICK_GITOPS_REPOSITORY = "git@github.com:gammaLaboratory/m3usick-gitops.git"
RETIRED_CREDENTIAL_MANIFESTS = (
    "concourse-github-ssh-app-sealed.yaml",
    "concourse-github-ssh-sealed.yaml",
)


def validate_workflows(build_workflow: str, production_workflow: str) -> None:
    """Require the GitHub Actions workflows to gate and perform GitOps writes."""
    required = {
        "build workflow": (
            build_workflow,
            (
                "vars.CI_DEPLOY_ENABLED == 'true'",
                "secrets.GITOPS_DEPLOY_KEY",
                M3USICK_GITOPS_REPOSITORY,
                "git push origin HEAD:main",
            ),
        ),
        "production workflow": (
            production_workflow,
            (
                "vars.CI_DEPLOY_ENABLED == 'true'",
                "secrets.GITOPS_DEPLOY_KEY",
                M3USICK_GITOPS_REPOSITORY,
                "git push origin HEAD:main",
            ),
        ),
    }
    for label, (workflow, expected_fragments) in required.items():
        if "concourse" in workflow.lower() or "fly -t" in workflow:
            raise ValueError(f"{label} still invokes Concourse")
        for fragment in expected_fragments:
            if fragment not in workflow:
                raise ValueError(f"{label} is missing required writer guard: {fragment}")


def validate_local_source(root: Path) -> None:
    """Ensure k8s-home no longer GitOps-manages the m3usick Concourse keys."""
    application = root / "apps/m3usick/application.yaml"
    if M3USICK_GITOPS_REPOSITORY not in application.read_text():
        raise ValueError("m3usick Argo CD application no longer targets its dedicated GitOps repository")

    secrets_directory = root / "infra/secrets"
    for filename in RETIRED_CREDENTIAL_MANIFESTS:
        if (secrets_directory / filename).exists():
            raise ValueError(f"retired m3usick Concourse credential is still managed: {filename}")


def gh_api(path: str, *, raw: bool = False) -> str:
    command = ["gh", "api"]
    if raw:
        command.extend(["-H", "Accept: application/vnd.github.raw+json"])
    command.append(path)
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def validate_live_actions_state() -> None:
    """Read GitHub configuration and a successful deploy run without exposing secrets."""
    variable = json.loads(
        gh_api(f"repos/{M3USICK_REPOSITORY}/actions/variables/CI_DEPLOY_ENABLED")
    )
    if variable.get("value") != "true":
        raise ValueError("gammaLaboratory/m3usick CI_DEPLOY_ENABLED is not true")

    secrets = json.loads(gh_api(f"repos/{M3USICK_REPOSITORY}/actions/secrets?per_page=100"))
    secret_names = {secret["name"] for secret in secrets.get("secrets", [])}
    if "GITOPS_DEPLOY_KEY" not in secret_names:
        raise ValueError("gammaLaboratory/m3usick is missing GITOPS_DEPLOY_KEY")

    build_workflow = gh_api(
        f"repos/{M3USICK_REPOSITORY}/contents/.github/workflows/build-deploy.yml?ref=develop",
        raw=True,
    )
    production_workflow = gh_api(
        f"repos/{M3USICK_REPOSITORY}/contents/.github/workflows/deploy-prod.yml?ref=develop",
        raw=True,
    )
    validate_workflows(build_workflow, production_workflow)

    runs = json.loads(
        gh_api(
            f"repos/{M3USICK_REPOSITORY}/actions/workflows/build-deploy.yml/runs?status=success&per_page=100"
        )
    ).get("workflow_runs", [])
    if not any(run.get("head_branch") == "develop" and run.get("conclusion") == "success" for run in runs):
        raise ValueError("no successful develop Build and deploy run was found")


def main() -> None:
    validate_local_source(ROOT)
    validate_live_actions_state()
    print(
        "Verified source and GitHub configuration: GitHub Actions is the configured "
        "m3usick GitOps writer after this source cleanup is synced."
    )


if __name__ == "__main__":
    main()
