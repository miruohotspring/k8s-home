# Proxmox bootstrap runbook

## Prerequisites

- Proxmox VM with k3s and Traefik disabled
- `kubectl`, `argocd`, `kubeseal`, `git`
- Cloudflare Tunnel token and the k8s-home repository deploy key
- Sealed Secrets controller key backup

## Restore order

1. Confirm the k3s node is Ready.
2. Clone `miruohotspring/k8s-home`.
3. Apply `bootstrap/argocd`.
4. Register the repository read-only deploy key in Argo CD.
5. Restore the Sealed Secrets controller key and restart the controller.
6. Apply `bootstrap/root-app`.
7. Restore the Cloudflare Tunnel token and verify platform applications.

```bash
kubectl get nodes -o wide
kubectl apply -k bootstrap/argocd
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s
kubectl apply -f <SEALED_SECRETS_KEY_BACKUP_YAML>
kubectl rollout restart deploy/sealed-secrets-controller -n kube-system
kubectl apply -k bootstrap/root-app
kubectl -n argocd get applications
```

## Done criteria

- `root-app`, `platform-secrets`, `cloudflared`, `authentik`, and registered product applications are `Synced` and `Healthy`.
- Argo CD, authentik, Cloud Drive, m3usick, and example application health endpoints respond as documented by their runbooks.
- No plaintext secret material is stored in Git.
