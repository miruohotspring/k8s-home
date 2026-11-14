# GitHub Actions delivery runbook

## Current state

GitHub Actions is the only CI/cloud/GitOps writer for m3usick, Cloud Drive, and web-app-template. Repository variables have `CI_DEPLOY_ENABLED=true`; AWS access uses OIDC roles; GitOps writes use repository-scoped deploy keys. No cluster kubeconfig is stored in GitHub.

## Verification

For each repository, verify the default-branch workflow, GitOps commit, Argo revision, and public health endpoint before changing credentials:

```bash
gh run list -R <owner/repo> --limit 10
gh api repos/<owner/gitops-repo>/commits/main --jq '{sha:.sha,message:.commit.message}'
kubectl -n argocd get applications
```

Repository secrets are verified only by name and update timestamp. Their values are never printed or copied back from the retired Kubernetes credential store. The existing GitOps write deploy keys remain active because GitHub Actions uses them; only their obsolete cluster copies were removed. Rotate them later by proving a new key writes successfully before revoking the old key.

## Safety

- Pull-request workflows receive no deployment credentials.
- Terraform apply uses the exact reviewed plan and rejects unrelated deletes.
- Production promotion remains an explicit manual operation.
- Set `CI_DEPLOY_ENABLED=false` before credential rotation or incident response, then wait for active apply/migration/GitOps jobs to finish.

Historical migration and recovery details are under `docs/archive/`.
