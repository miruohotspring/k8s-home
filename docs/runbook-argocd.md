# Argo CD Operational Runbook

## 1. Scope and Daily Operations
- URL: `https://argocd.miruohotspring.net`
- Namespace: `argocd`
- App namespace examples: `example-dev`, `concourse`, `ingress-nginx`

### 1.1 Application Inventory
```bash
kubectl get applications -n argocd
argocd app list
```

### 1.2 Sync Status Check
- Web UI: Application list (`Synced` / `OutOfSync` / `Degraded`)
- CLI:

```bash
argocd app get <app-name>
argocd app history <app-name>
```

### 1.3 Manual Sync
```bash
argocd app sync <app-name>
argocd app wait <app-name> --health --timeout 300
```

## 2. Authentication and Password Management

### 2.1 Initial Admin Password (cmd_022 reference flow)
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d; echo
```

### 2.2 Login
```bash
argocd login argocd.miruohotspring.net --username admin --password '<PASSWORD>'
```

### 2.3 Change Admin Password
```bash
argocd account update-password
```
- After change, update secret source and reseal if managed via Sealed Secrets.

### 2.4 Session Token Refresh
- Re-login if CLI returns `Unauthenticated`.
- For automation token rotation:

```bash
argocd account generate-token --account admin
```
- Store new token in secret management and reseal before commit.

## 3. Application Management

### 3.1 Create / Delete Application
```bash
kubectl apply -f <application.yaml>
kubectl delete -f <application.yaml>
```

### 3.2 Force Sync and Prune
```bash
argocd app sync <app-name> --force --prune
```

### 3.3 Debug Sync Failure
```bash
argocd app get <app-name>
argocd app logs <app-name>
kubectl logs -n argocd deploy/argocd-application-controller --tail=200
```

## 4. Incident Recovery

### 4.1 Cannot Login
1. Confirm ingress and server pod status.
2. Retrieve/reset admin credential per cmd_022 procedure.
3. Re-login and rotate password/token.

```bash
kubectl get pods -n argocd
kubectl get ingress -n argocd
kubectl logs -n argocd deploy/argocd-server --tail=200
```

### 4.2 App is OutOfSync
1. Inspect diff.
2. Verify targetRevision and chart/image tags are pinned.
3. Sync manually.

```bash
argocd app diff <app-name>
argocd app sync <app-name>
```

### 4.3 Sync Loop (Repeated OutOfSync)
1. Temporarily disable auto-sync.
2. Find mutable fields or controllers writing back state.
3. Add ignoreDifferences or fix source manifest.

```bash
argocd app set <app-name> --sync-policy none
argocd app sync <app-name>
```

### 4.4 Controller Recovery
```bash
kubectl rollout restart deploy/argocd-application-controller -n argocd
kubectl rollout status deploy/argocd-application-controller -n argocd
```

## 5. Operational Checks After Recovery
```bash
kubectl get applications -n argocd
argocd app list
argocd app wait <critical-app> --health --timeout 300
```
- Expected: critical apps become `Synced` and `Healthy`.
