# Cloudflared Readiness Verification Runbook

## 1. Purpose
This runbook defines repeatable operational checks for the cloudflared deployment after manifest updates or restarts. It closes the residual medium-risk item from `cmd_047` by making `/ready` and infra app health checks explicit and auditable.

## 2. Environment Assumptions and References
- Cluster model and namespace strategy follow `context/k8s-home.md` (k3s, GitOps with Argo CD, cloudflared in `cloudflared` namespace).
- Why this runbook exists follows `docs/review-after-improvement-2026-02.md` (cloudflared probes/metrics were added, but operations needed a concrete verification flow).
- Current deployment exposes probe/metrics on `localhost:2000` (`infra/cloudflared/deployment.yaml`).

## 3. Preflight
Run these checks before changing anything:

```bash
kubectl config current-context
kubectl get deploy cloudflared -n cloudflared
kubectl get applications -n argocd
```

Expected:
- Context is the home cluster you intend to operate.
- `deploy/cloudflared` exists in namespace `cloudflared`.
- Argo CD `Application` resources are queryable.

## 4. Standard Verification Flow

### 4.1 Identify the current cloudflared Pod
```bash
kubectl get pods -n cloudflared -l app=cloudflared -o wide
```

Expected:
- Exactly one running pod for normal operation.
- Example status: `Running`, `READY 1/1`.

### 4.2 Restart cloudflared and wait for rollout
```bash
kubectl rollout restart deploy/cloudflared -n cloudflared
kubectl rollout status deploy/cloudflared -n cloudflared --timeout=180s
kubectl get pods -n cloudflared -l app=cloudflared
```

Expected:
- Rollout command accepted.
- Rollout status finishes with `successfully rolled out`.
- New pod returns to `READY 1/1`.

### 4.3 Verify `/ready` from inside the pod
Get the active pod name first:

```bash
POD="$(kubectl get pods -n cloudflared -l app=cloudflared -o jsonpath='{.items[0].metadata.name}')"
echo "$POD"
kubectl exec -n cloudflared "$POD" -- curl -fsS localhost:2000/ready
```

Expected:
- `curl` exits with status code `0`.
- Body indicates readiness (commonly `OK` or equivalent ready response).

### 4.4 Verify metrics endpoint
```bash
kubectl exec -n cloudflared "$POD" -- curl -fsS localhost:2000/metrics | head -n 20
```

Expected:
- Command succeeds with exit code `0`.
- Prometheus-formatted metric lines are returned (for example, `# HELP` / `# TYPE` headers).

### 4.5 Confirm Argo CD infra apps remain Synced/Healthy
```bash
kubectl get applications -n argocd \
  ingress-nginx cloudflared sealed-secrets concourse \
  -o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status
```

Expected:
- All four applications are present.
- `SYNC` is `Synced` and `HEALTH` is `Healthy` for each.

## 5. One-Block Quick Check Example
Use this block for a single-pass validation after manifest changes:

```bash
set -euo pipefail
kubectl rollout restart deploy/cloudflared -n cloudflared
kubectl rollout status deploy/cloudflared -n cloudflared --timeout=180s
POD="$(kubectl get pods -n cloudflared -l app=cloudflared -o jsonpath='{.items[0].metadata.name}')"
kubectl exec -n cloudflared "$POD" -- curl -fsS localhost:2000/ready
kubectl exec -n cloudflared "$POD" -- curl -fsS localhost:2000/metrics >/dev/null
kubectl get applications -n argocd ingress-nginx cloudflared sealed-secrets concourse \
  -o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status
```

If any command fails, treat the check as failed and move to Section 6.

## 6. Failure Handling, Reporting, and Resume Criteria

### 6.1 `/ready` check fails
1. Capture diagnostics:
```bash
kubectl logs -n cloudflared deploy/cloudflared --tail=200
kubectl describe pod -n cloudflared "$POD"
```
2. Report with timestamp, command, and stderr/stdout summary.
3. Resume only after `/ready` returns success and pod is `READY 1/1`.

### 6.2 `/metrics` check fails
1. Confirm process health and port exposure:
```bash
kubectl exec -n cloudflared "$POD" -- ss -lntp
kubectl logs -n cloudflared deploy/cloudflared --tail=200
```
2. Report endpoint failure with captured logs.
3. Resume only after `curl -fsS localhost:2000/metrics` succeeds.

### 6.3 Argo CD app not Synced/Healthy
1. Identify the app and reason:
```bash
kubectl describe application -n argocd <app-name>
argocd app get <app-name>
```
2. Record affected app, status, and remediation action (sync/retry/rollback).
3. Resume only after all required infra apps return to `Synced/Healthy`.

### 6.4 Mandatory report fields for every failed run
- Timestamp (with timezone)
- Operator
- Command executed
- Observed failure
- Immediate action taken
- Resume decision (`resume` / `hold`) and reason

## 7. Execution Frequency
Run this checklist:
- After every manifest change that affects `infra/cloudflared/*`, ingress flow, or related infra apps.
- After any manual or automated restart of `deploy/cloudflared`.
- After Argo CD syncs that touch `cloudflared`, `ingress-nginx`, `sealed-secrets`, or `concourse`.

Minimum cadence: run at least once per change event; do not skip post-restart verification.

## 8. Verification Log Template
Use the table below to keep date-stamped operation records.

| Timestamp (TZ) | Operator | Scope | Outcome | Notes |
|---|---|---|---|---|
| 2026-02-20T02:30:00+09:00 | your-name | restart + /ready + /metrics + Argo infra status | PASS | All four apps Synced/Healthy |
| YYYY-MM-DDThh:mm:ss+TZ | your-name | check scope | PASS/FAIL | failure details, mitigation, resume decision |
