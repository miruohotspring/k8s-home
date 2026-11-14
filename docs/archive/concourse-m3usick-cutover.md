# Archive: m3usick Concourse delivery cutover

> **Status:** historical record. This is not an operational Concourse runbook.

m3usick delivery moved to GitHub Actions in `gammaLaboratory/m3usick` commit
`9dc2893` (`ci: migrate Concourse delivery to GitHub Actions (#36)`). The
GitOps target is `gammaLaboratory/m3usick-gitops`; Argo CD reads that repository
through the `m3usick-apps` app-of-apps managed in this repository.

## Former Concourse path

The former `m3usick` Concourse pipeline read the application repository and
wrote image revisions to `m3usick-gitops`. Its two repository-scoped Kubernetes
credentials were:

- `concourse-main/concourse-github-ssh-app` — application read key
- `concourse-main/concourse-github-ssh` — GitOps write key

The pipeline definition may remain in the application repository as historical
source, but it is not an approved recovery path. The SealedSecret manifests for
these two credentials were removed from `k8s-home` by the #65 retirement work.
Do not recreate either Secret or unpause the old pipeline. A recovery that needs
a m3usick deployment must use the GitHub Actions workflows below.

## Replacement writer and audit evidence

As of 2026-11-14 (JST), the GitHub repository had:

- `CI_DEPLOY_ENABLED=true`
- a `GITOPS_DEPLOY_KEY` repository secret (name/updated time read only; value was
  not retrieved)
- OIDC-backed ECR publication in `build-deploy.yml`
- GitOps updates in `build-deploy.yml` (develop) and `deploy-prod.yml` (manual
  promotion from main)
- successful `Build and deploy` runs for develop and main after the 2026-10-06
  cutover

The writer contract is executable from this repository:

```bash
python3 scripts/verify_m3usick_writer.py
```

It checks the GitHub Actions configuration and workflow source without reading
secret values or mutating GitHub/Kubernetes. After Argo CD syncs the removal,
perform the cluster read-back in
[`docs/concourse-retirement-inventory.md`](../concourse-retirement-inventory.md).
