# k8s-home

Home Kubernetes cluster bootstrap and GitOps source for Argo CD, ingress-nginx, Cloudflare Tunnel, authentik, Sealed Secrets, and application registrations.

## Source of truth

- Cluster bootstrap: `bootstrap/`
- Platform applications: `infra/`
- Product applications: `apps/`
- Encrypted platform credentials: `infra/secrets/*-sealed.yaml`
- Operational runbooks: `docs/`

Apply only the bootstrap entrypoints directly:

```bash
kubectl apply -k bootstrap/argocd
kubectl apply -k bootstrap/root-app
```

Argo CD owns the remaining resources. Validate changes before merge with:

```bash
kubectl kustomize . >/dev/null
kubectl apply --dry-run=client -k . >/dev/null
pre-commit run --all-files
```

## Delivery

Application repositories use GitHub Actions with AWS OIDC and repository-scoped GitOps credentials. Argo CD reconciles the resulting GitOps commits. Concourse was retired on 2026-11-14; recovery evidence is documented in `docs/archive/concourse-retirement.md`.

## Runbooks

- Cluster bootstrap: `docs/bootstrap-proxmox.md`
- Argo CD: `docs/runbook-argocd.md`
- authentik/OIDC: `docs/runbook-authentik.md`
- GitHub Actions: `docs/runbook-github-actions.md`
- Sealed Secrets: `docs/sealed-secrets.md`
