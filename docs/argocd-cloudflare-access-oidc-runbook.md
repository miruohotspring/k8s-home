# Argo CD Cloudflare Access OIDC staged cutover

This migration keeps the built-in `admin` path enabled while Cloudflare Access OIDC and the private RBAC overlay are validated. Do not disable it during either phase.

## Phase A — private RBAC material and overlay

1. From `infra/terraform/cloudflare-access`, use the checked-in generator with a configured Terraform backend. It captures `terraform output -json saas_clients` and the current Argo CD allowlist policy from Terraform state in process memory, rejects invalid CSV-sensitive values, and emits a Kubernetes Secret only to the `kubeseal` pipe.
2. Seal the generated Secret for the in-cluster controller. Commit only `apps/argocd/argocd-cloudflare-oidc-sealed.yaml`; it contains encrypted `issuer`, `clientID`, `clientSecret`, and `rbac-patch.json` values.
3. Apply Phase A through the normal GitOps review and sync path. The PostSync Job mounts only `rbac-patch.json` and merges `data.policy.cloudflare.csv` into `argocd-rbac-cm`. Its ServiceAccount can only `get` and `patch` that ConfigMap.
4. Verify before Phase B: the SealedSecret has produced `argocd-cloudflare-oidc`, the PostSync Job completed, `argocd-rbac-cm` contains the generated key, and a Cloudflare-accessenticated administrator resolves through the `platform-admins` mapping. Keep the current Authentik login and `admin.enabled: "true"` available for this validation.

## Phase B — OIDC settings cutover

The native OTP identity was observed to omit the `name` claim, causing Dex to reject a real callback with `missing "name" claim`. Set the connector's `userNameKey: email` for display-name mapping only; do not set `userIDKey` or weaken signature, issuer, audience, or email-verification checks. This mapping does not prove an end-to-end login; verify the next real callback before marking the cutover complete.

Argo CD v2.13 browser PKCE omits OAuth state (`expectNoState`), while Cloudflare requires state. A shared direct Web/CLI client also rejected the server-side Web request with `code_challenge is required for this client`. Use the already-installed Dex v2.41.1 as the broker instead: its upstream Cloudflare client is confidential authorization-code only, while Dex provides the standard separate Argo Web and CLI clients (including CLI PKCE). The upstream callback is `/api/dex/callback`; Hermes and Cloud Drive remain PKCE-only. Dex ID tokens and Argo sessions are capped at 720h. No new identity store or deployment is introduced. Restart `argocd-dex-server` and `argocd-server` after changing provider wiring if their cached settings remain stale; a refreshed settings API alone is not login verification.

1. Apply the separate Phase B commit after Phase A verification. It points Argo CD at the sealed Cloudflare issuer/client references, requests only `openid`, `profile`, and `email`, and sets `users.session.duration: "720h"`.
2. Test in a fresh browser session: email OTP, enrolled TOTP, callback to Argo CD, administrator authorization, denied-user behavior, and CLI login using the loopback PKCE callback on `http://localhost:8085/auth/callback`.
3. Argo CD v2.13.3 combines `policy.csv` with every `policy.<name>.csv` key. The parent `argocd-ingress` Application ignores only `/data/policy.cloudflare.csv` and sets `RespectIgnoreDifferences=true`, so its generated key is preserved while the base `g, platform-admins, role:admin` policy remains Git-managed.

## Rollback and recovery

- If Phase A fails, retain the built-in administrator and the existing Authentik OIDC settings; fix or remove the PostSync overlay resources, then resync. The base RBAC policy remains unchanged.
- If Phase B login or authorization fails, revert only the OIDC settings commit. The Phase A sealed Secret and RBAC overlay can remain in place without changing the active issuer.
- If GitOps reconciliation removes the generated key unexpectedly, confirm the `argocd-ingress` Application still has the exact ignore rule and `RespectIgnoreDifferences=true`, then rerun the PostSync Job through an ordinary sync.
- Do not remove the existing Authentik client secret or disable `admin.enabled` until an independent, approved recovery procedure has been tested.

## Source checks

- Argo CD v2.13.3 `util/rbac/rbac.go` (`PolicyCSV`) for composed `policy.<name>.csv` behavior.
- Argo CD v2.13.3 `util/settings/settings.go` for `users.session.duration` and OIDC secret-reference substitution.
- Cloudflare Access OIDC documentation for the team issuer format and discovery endpoint.
- `registry.k8s.io` manifest response for the digest-pinned kubectl image used by the Job.
