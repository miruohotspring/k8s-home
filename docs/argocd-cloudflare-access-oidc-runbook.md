# Argo CD Cloudflare Access OIDC staged cutover

This migration keeps the built-in `admin` path enabled while Cloudflare Access OIDC and the private RBAC overlay are validated. Do not disable it during either phase.

## Phase A — private RBAC material and overlay

1. From `infra/terraform/cloudflare-access`, use the checked-in generator with a configured Terraform backend. It captures `terraform output -json saas_clients` and the current Argo CD allowlist policy from Terraform state in process memory, rejects invalid CSV-sensitive values, and emits a Kubernetes Secret only to the `kubeseal` pipe.
2. Seal the generated Secret for the in-cluster controller. Commit only `apps/argocd/argocd-cloudflare-oidc-sealed.yaml`; it contains encrypted `issuer`, `clientID`, `clientSecret`, and `rbac-patch.json` values.
3. Apply Phase A through the normal GitOps review and sync path. The PostSync Job mounts only `rbac-patch.json` and merges `data.policy.cloudflare.csv` into `argocd-rbac-cm`. Its ServiceAccount can only `get` and `patch` that ConfigMap.
4. Verify before Phase B: the SealedSecret has produced `argocd-cloudflare-oidc`, the PostSync Job completed, `argocd-rbac-cm` contains the generated key, and a Cloudflare-accessenticated administrator resolves through the `platform-admins` mapping. Keep the current Authentik login and `admin.enabled: "true"` available for this validation.

## Phase B — OIDC settings cutover

Argo CD v2.13 browser PKCE omits OAuth state (`expectNoState` in its source), while Cloudflare requires state; a real browser returned `state is a required parameter`. Therefore Web deliberately uses the server-side confidential authorization-code flow (`enablePKCEAuthentication: false`) with its sealed client secret and state validation. The CLI keeps public S256 PKCE and its loopback callback. Only the Argo SaaS client allows both code grant variants; Hermes and Cloud Drive remain PKCE-only. `/pkce/verify` is registered but not the active browser callback. Restart only `argocd-server` after issuer/client settings changes if its cached OIDC provider still redirects to the old issuer; `/api/v1/settings` updating alone does not prove that the login handler refreshed.

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
