# Proxmox Bootstrap Runbook (k8s-home Restore)

## 1. Scope

This runbook restores `k8s-home` on a clean Proxmox VM with minimum steps.
Daily Concourse operations are intentionally out of scope here; use `docs/runbook-concourse.md`.

## 2. Prerequisites

### 2.1 Infrastructure assumptions

- Proxmox VM (Debian/Ubuntu family assumed)
- k3s cluster on the VM
- Cloudflare-managed domain and Zero Trust Tunnel
- DNS hosts prepared for:
  - `argocd.<YOUR_DOMAIN>`
  - `concourse.<YOUR_DOMAIN>`

### 2.2 Required CLI

- `kubectl`
- `argocd`
- `sops` and/or `kubeseal`
- `fly`
- `git`

Preflight:

```bash
kubectl version --client
argocd version --client
kubeseal --version || true
sops --version || true
fly --version
git --version
```

## 3. Bootstrap Order and Dependencies

Execute in this order:

1. k3s baseline ready (and Traefik disabled)
2. Argo CD bootstrap (`bootstrap/argocd`)
3. Argo CD repo authentication (`git@github.com:miruohotspring/k8s-home.git`)
4. root-app apply (`bootstrap/root-app`)
5. Sealed Secrets key restore
6. cloudflared secret + app health
7. Concourse health check

Dependency notes:

- `root-app` can be applied before repo auth, but sync will stall until repo auth is valid.
- `platform-secrets` decryption depends on Sealed Secrets key restore.
- `cloudflared` should be checked before external URL validation.

## 4. Step-by-Step Restore Procedure

### 4.1 VM and k3s baseline

1. Prepare VM networking and time sync.
2. Ensure k3s is installed and Traefik is disabled.
3. Confirm cluster readiness:

```bash
kubectl get nodes -o wide
kubectl get pods -A
```

### 4.2 Clone repository

```bash
git clone git@github.com:miruohotspring/k8s-home.git
cd k8s-home
```

### 4.3 Argo CD bootstrap

```bash
kubectl apply -k bootstrap/argocd/
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s
kubectl -n argocd get pods
```

### 4.4 Repo authentication for Argo CD

Register repo access (SSH deploy key):

```bash
argocd login argocd.<YOUR_DOMAIN> --username admin --password '<ARGOCD_ADMIN_PASSWORD>'
argocd repo add git@github.com:miruohotspring/k8s-home.git \
  --ssh-private-key-path <PATH_TO_K8S_HOME_DEPLOY_KEY>
argocd repo list | grep k8s-home
```

### 4.5 Apply root-app

```bash
kubectl apply -k bootstrap/root-app/
kubectl -n argocd get applications
argocd app wait root-app --sync --health --timeout 600
```

### 4.6 Restore Sealed Secrets key

If you have backup key YAML:

```bash
kubectl apply -f <SEALED_SECRETS_KEY_BACKUP_YAML>
kubectl rollout restart deploy/sealed-secrets-controller -n kube-system
kubectl rollout status deploy/sealed-secrets-controller -n kube-system --timeout=300s
kubectl get sealedsecret -A
```

Reference: `docs/sealed-secrets.md`

### 4.7 cloudflared restore

```bash
kubectl create namespace cloudflared --dry-run=client -o yaml | kubectl apply -f -
kubectl -n cloudflared create secret generic cloudflared-tunnel-token \
  --from-literal=TUNNEL_TOKEN='<CLOUDFLARE_TUNNEL_TOKEN>' \
  --dry-run=client -o yaml | kubectl apply -f -

argocd app wait cloudflared --sync --health --timeout 600
kubectl -n cloudflared get pods
```

### 4.8 Concourse health check

```bash
argocd app wait concourse --sync --health --timeout 600
kubectl -n concourse get pods,svc,ingress
fly -t home login -c https://concourse.<YOUR_DOMAIN>
fly -t home pipelines
```

For Concourse operation details, see `docs/runbook-concourse.md`.

## 5. Current-State Differences and Cautions

### 5.1 targetRevision / HEAD tracking cautions

- Current manifests are mixed:
  - Some apps are pinned (`v0.1.0`, chart versions)
  - Some apps track `main` (for example `infra/concourse/application.yaml`, `infra/secrets/application.yaml`)
- Avoid introducing `targetRevision: HEAD` for recovery-critical apps.
- During restore, always check effective revision:

```bash
kubectl -n argocd get app root-app concourse platform-secrets -o wide
argocd app get root-app
```

### 5.2 cmd_035 reflected changes (important)

- `concourse-main` dependency has been removed from credential flow.
- Do not revive legacy `concourse-main` namespace assumptions.
- Concourse credential handling follows current `concourse` namespace and current runbook:
  - `docs/runbook-concourse.md` section 3.4-3.6.

## 6. Minimal Recovery Path When Blocked

If stuck, check in this order:

1. Argo CD app sync/health:

```bash
kubectl -n argocd get applications
argocd app get root-app
```

2. Sealed Secrets decryption/key status:

```bash
kubectl get sealedsecret -A
kubectl logs -n kube-system deploy/sealed-secrets-controller --tail=200
```

3. cloudflared tunnel pod and token:

```bash
kubectl -n cloudflared get secret cloudflared-tunnel-token
kubectl -n cloudflared logs deploy/cloudflared --tail=200
```

4. Concourse endpoint and pods:

```bash
kubectl -n concourse get pods,ingress
```

## 7. Done Checklist

All must be true:

- Argo CD: critical apps (`root-app`, `cloudflared`, `concourse`, `platform-secrets`) are `Synced` and `Healthy`
- URL reachability:
  - `https://argocd.<YOUR_DOMAIN>`
  - `https://concourse.<YOUR_DOMAIN>`
- Major pods are Running:
  - `argocd` namespace core components
  - `cloudflared` namespace deployment
  - `concourse` namespace web/worker/postgresql

Verification:

```bash
kubectl -n argocd get applications
kubectl -n argocd get pods
kubectl -n cloudflared get pods
kubectl -n concourse get pods
curl -I https://argocd.<YOUR_DOMAIN>
curl -I https://concourse.<YOUR_DOMAIN>
```

## 8. Shortest Command Sequence for Lord

```bash
git clone git@github.com:miruohotspring/k8s-home.git
cd k8s-home
kubectl apply -k bootstrap/argocd/
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s
argocd login argocd.<YOUR_DOMAIN> --username admin --password '<ARGOCD_ADMIN_PASSWORD>'
argocd repo add git@github.com:miruohotspring/k8s-home.git --ssh-private-key-path <PATH_TO_K8S_HOME_DEPLOY_KEY>
kubectl apply -k bootstrap/root-app/
kubectl apply -f <SEALED_SECRETS_KEY_BACKUP_YAML>
kubectl -n cloudflared create secret generic cloudflared-tunnel-token --from-literal=TUNNEL_TOKEN='<CLOUDFLARE_TUNNEL_TOKEN>' --dry-run=client -o yaml | kubectl apply -f -
argocd app wait root-app cloudflared concourse --sync --health --timeout 600
kubectl -n argocd get applications
kubectl -n cloudflared get pods
kubectl -n concourse get pods
```
