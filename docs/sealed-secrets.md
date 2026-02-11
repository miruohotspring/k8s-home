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

## Create a New Sealed Secret
1. Create plain Secret YAML (not committed to Git):

```bash
kubectl create secret generic sample-secret \
  -n example-dev \
  --from-literal=username=demo \
  --from-literal=password='change-me' \
  --dry-run=client -o yaml > /tmp/sample-secret.yaml
```

2. Encrypt with kubeseal:

```bash
kubeseal --format yaml < /tmp/sample-secret.yaml > infra/secrets/sample-secret-sealed.yaml
```

3. Remove plaintext file immediately:

```bash
rm /tmp/sample-secret.yaml
```

4. Commit only `*-sealed.yaml` to Git:

```bash
git add infra/secrets/sample-secret-sealed.yaml
git commit -m "feat: add sample SealedSecret"
git push
```

## Update Existing Secret
1. Export current secret:

```bash
kubectl get secret sample-secret -n example-dev -o yaml > /tmp/sample-secret.yaml
```

2. Edit data source or regenerate secret YAML (recommended: recreate using `kubectl create secret ... --dry-run=client -o yaml`).

3. Reseal and overwrite file:

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

## Backup Sealed Secrets Private Key (Critical)
If the private key is lost, existing SealedSecrets cannot be decrypted.
Backup immediately after setup and store in secure secret storage.

```bash
kubectl get secret -n kube-system sealed-secrets-key -o yaml > sealed-secrets-key-backup.yaml
# Store securely (e.g. 1Password, AWS Secrets Manager)
```

Note: key name may include suffix (for example `sealed-secrets-keyxxxxx`).
Use this command to discover exact name:

```bash
kubectl get secrets -n kube-system | grep sealed-secrets-key
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
