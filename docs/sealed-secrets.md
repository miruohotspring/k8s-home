# Sealed Secrets Operational Guide

## Overview
Sealed Secrets encrypts Kubernetes Secret manifests so they can be safely stored in Git.
Only the Sealed Secrets controller in the cluster can decrypt them back into Secret objects.

- Controller namespace: `kube-system`
- Controller name: `sealed-secrets-controller`
- CLI tool: `kubeseal`

## Prerequisites
- `kubectl` can access target cluster
- `kubeseal` is installed locally
- Sealed Secrets controller is running

Check commands:

```bash
kubectl get pods -n kube-system | grep sealed-secrets-controller
kubeseal --version
kubeseal --fetch-cert > /tmp/sealed-secrets-cert.pem
rm /tmp/sealed-secrets-cert.pem
```

## Standard Secret Creation Flow
1. Create plain Secret YAML (never commit plaintext):

```bash
kubectl create secret generic sample-secret \
  -n example-dev \
  --from-literal=username=demo \
  --from-literal=password='change-me' \
  --dry-run=client -o yaml > /tmp/sample-secret.yaml
```

2. Encrypt and write repository file:

```bash
kubeseal --format yaml < /tmp/sample-secret.yaml > infra/secrets/sample-secret-sealed.yaml
```

3. Remove plaintext immediately:

```bash
rm /tmp/sample-secret.yaml
```

4. Commit only sealed manifest:

```bash
git add infra/secrets/sample-secret-sealed.yaml
git commit -m "feat: add sample SealedSecret"
git push
```

5. Verify reconciliation:

```bash
kubectl get sealedsecret sample-secret -n example-dev
kubectl get secret sample-secret -n example-dev
```

## Token / Password Rotation Flow
Use this for Argo CD admin password, Concourse local user password, API tokens, and registry credentials.

1. Generate new credential outside Git.
2. Recreate plaintext secret YAML into `/tmp`.
3. Re-seal and overwrite existing `*-sealed.yaml` in repo.
4. Commit and push.
5. Trigger Argo CD sync and verify app/secret health.
6. Validate actual login/API access using the new credential.

Example:

```bash
kubectl create secret generic argocd-admin-login \
  -n argocd \
  --from-literal=password='<NEW_PASSWORD>' \
  --dry-run=client -o yaml > /tmp/argocd-admin-login.yaml

kubeseal --format yaml < /tmp/argocd-admin-login.yaml > infra/secrets/argocd-admin-login-sealed.yaml
rm /tmp/argocd-admin-login.yaml
```

## Update Existing Secret
1. Export current secret as template:

```bash
kubectl get secret sample-secret -n example-dev -o yaml > /tmp/sample-secret.yaml
```

2. Regenerate or edit desired values.
3. Reseal and replace managed file:

```bash
kubeseal --format yaml < /tmp/sample-secret.yaml > infra/secrets/sample-secret-sealed.yaml
rm /tmp/sample-secret.yaml
```

4. Apply/Sync and verify:

```bash
kubectl apply -f infra/secrets/sample-secret-sealed.yaml
kubectl get sealedsecret sample-secret -n example-dev
kubectl get secret sample-secret -n example-dev
```

## Existing Secret Migration (Important)
If the same Secret name already exists and is not managed by Sealed Secrets, controller sync may fail with:
`Resource "<name>" already exists and is not managed by SealedSecret`.

Safe migration steps:

```bash
kubectl apply -f infra/secrets/<name>-sealed.yaml
kubectl delete secret <name> -n <namespace>
kubectl get sealedsecret <name> -n <namespace>
kubectl get secret <name> -n <namespace>
```

## Key Backup and Restore (Critical)
If the private key is lost, existing SealedSecrets cannot be decrypted.

### Backup
```bash
kubectl get secrets -n kube-system | grep sealed-secrets-key
kubectl get secret -n kube-system <sealed-secrets-key-name> -o yaml > sealed-secrets-key-backup.yaml
```
- Store backup in secure secret storage (for example password manager or cloud secret store).
- Do not commit backup key to Git repositories.

### Restore (Disaster Recovery)
1. Recreate key secret in target cluster.
2. Restart controller.
3. Reconcile one known sealed secret to confirm decryption.

```bash
kubectl apply -f sealed-secrets-key-backup.yaml
kubectl rollout restart deploy/sealed-secrets-controller -n kube-system
kubectl rollout status deploy/sealed-secrets-controller -n kube-system
kubectl get sealedsecret -A
```

## Troubleshooting
- `kubeseal --fetch-cert` fails:
  - Verify cluster connectivity and current context (`kubectl config current-context`).
  - Verify controller pod is running in `kube-system`.
- `SealedSecret SYNCED=False`:
  - Check details: `kubectl describe sealedsecret <name> -n <namespace>`.
  - Check controller logs: `kubectl logs -n kube-system deploy/sealed-secrets-controller`.
- Argo CD Application stays `Unknown`:
  - Ensure AppProject allows destination namespace and source repo.
  - Verify `sourceRepos` includes external Helm repo and Git repo used by `sources`.
- Secret not recreated after apply:
  - Confirm encrypted data namespace/name matches expected destination.
  - Re-apply SealedSecret and re-check controller logs.
- Secret mismatch after credential rotation:
  - Confirm application pod actually restarted and consumed new secret.
  - Check stale env var mounts and force rollout if required.
