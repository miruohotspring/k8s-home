#!/usr/bin/env python3
"""Contracts for the post-Concourse m3usick GitOps writer verification."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verify_m3usick_writer import (
    M3USICK_GITOPS_REPOSITORY,
    validate_local_source,
    validate_workflows,
)


BUILD_WORKFLOW = """
PUBLISH_IMAGE: ${{ vars.CI_DEPLOY_ENABLED == 'true' }}
GITOPS_DEPLOY_KEY: ${{ secrets.GITOPS_DEPLOY_KEY }}
git clone git@github.com:gammaLaboratory/m3usick-gitops.git gitops
git push origin HEAD:main
"""

PRODUCTION_WORKFLOW = """
if: vars.CI_DEPLOY_ENABLED == 'true'
GITOPS_DEPLOY_KEY: ${{ secrets.GITOPS_DEPLOY_KEY }}
git clone git@github.com:gammaLaboratory/m3usick-gitops.git gitops
git push origin HEAD:main
"""


class M3usickWriterContractTest(unittest.TestCase):
    def test_actions_workflows_are_the_only_configured_m3usick_gitops_writer(self) -> None:
        validate_workflows(BUILD_WORKFLOW, PRODUCTION_WORKFLOW)

    def test_rejects_a_workflow_that_still_calls_concourse(self) -> None:
        with self.assertRaisesRegex(ValueError, "Concourse"):
            validate_workflows(BUILD_WORKFLOW + "\nfly -t home pipelines\n", PRODUCTION_WORKFLOW)

    def test_local_source_removes_the_retired_m3usick_concourse_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            application = root / "apps/m3usick/application.yaml"
            application.parent.mkdir(parents=True)
            application.write_text(
                "spec:\n"
                "  source:\n"
                f"    repoURL: {M3USICK_GITOPS_REPOSITORY}\n"
            )
            (root / "infra/secrets").mkdir(parents=True)

            validate_local_source(root)

            (root / "infra/secrets/concourse-github-ssh-sealed.yaml").write_text("retired")
            with self.assertRaisesRegex(ValueError, "retired m3usick Concourse credential"):
                validate_local_source(root)


if __name__ == "__main__":
    unittest.main()
