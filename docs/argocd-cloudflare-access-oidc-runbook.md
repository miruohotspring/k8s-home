# Argo CD Cloudflare Access OIDC staged cutover

Cloudflare Access is the standard OIDC provider for Argo CD. Google is the only allowed upstream IdP for this SaaS application. The built-in Argo CD `admin` path remains enabled as an independent break-glass route until a separate recovery procedure is proven.

## Membership and authorization ownership

Application entry is managed in the Cloudflare Zero Trust Web GUI through Rule group `app-argocd-users`. Terraform reads that group by name and attaches it to the Argo CD Access policy, but deliberately does not manage its members.

A user admitted by Cloudflare receives Argo CD's safe default `role:readonly`. Administrator access is separate and explicit: private email-to-`platform-admins` mappings are sealed into `rbac-patch.json`, and the Git-managed base policy maps `platform-admins` to `role:admin`. Never set `policy.default: role:admin`.

## Phase A — private administrator RBAC overlay

1. Prepare an owner-only JSON file containing the explicit Argo CD administrator emails. It must be a non-empty JSON array and use mode `0600`. Do not commit it.
2. Run `scripts/prepare-argocd-cloudflare-oidc-secret.py` with `--terraform-dir`, `--team-name`, and `--admin-emails-file`. Pipe its Secret output directly to `kubeseal`; never write the plaintext Secret or Terraform output to disk or logs.
3. Commit only `apps/argocd/argocd-cloudflare-oidc-sealed.yaml`. It contains encrypted `issuer`, `clientID`, `clientSecret`, and `rbac-patch.json` values.
4. The PostSync Job mounts only `rbac-patch.json` and merges `data.policy.cloudflare.csv` into `argocd-rbac-cm`. Its ServiceAccount can only `get` and `patch` that ConfigMap.
5. Verify that the SealedSecret produced `argocd-cloudflare-oidc`, the PostSync Job completed, GUI-admitted ordinary users resolve to `role:readonly`, and explicit administrators resolve through `platform-admins` to `role:admin`.

Cloudflare GUI membership and Argo administrator RBAC are intentionally not the same list. Adding someone to `app-argocd-users` grants read-only use; administrator promotion requires a reviewed SealedSecret update.

## Phase B — Google-backed Cloudflare OIDC

Argo CD v2.13 browser PKCE omits OAuth state, while Cloudflare requires it. A shared direct Web/CLI client also caused incompatible PKCE requirements. The bundled Dex broker therefore remains the standards-compatible boundary: Dex uses the confidential Cloudflare authorization-code client at `/api/dex/callback`, while Argo keeps separate Web and CLI clients, including the CLI loopback PKCE callback on `http://localhost:8085/auth/callback`.

The Dex connector requests `openid`, `profile`, `email`, and `offline_access`. Cloudflare's SaaS application enables `authorization_code` and `refresh_tokens`; its 719-hour refresh lifetime supports the 720-hour Argo session policy. Keep JWT signature, issuer, audience, TLS, expiry, and subject validation enabled.

Cloudflare Access sends users directly to Google. Google performs primary authentication, including account-side Passkey when available. Cloudflare independently requires the enrolled TOTP factor according to the application policy. The exact per-application membership gate remains `app-argocd-users` in the Cloudflare GUI.

The connector uses `userNameKey: email` only for display and keeps identity on signed subject data. The pinned Cloudflare connector may use `insecureSkipEmailVerified: true` because Access has already restricted the Google identity through the exact Rule group and independent MFA policy; do not generalize that exception to arbitrary issuers. `insecureSkipVerify` must remain disabled.

## Verification

After any identity, group, RBAC, or OIDC change:

1. Run the Cloudflare Terraform plan and require zero delete or replacement actions.
2. Verify an existing administrator can log in through Google and retains administrator operations.
3. Verify a GUI-admitted non-admin can log in and receives read-only access.
4. Verify a user outside `app-argocd-users` is denied by Cloudflare Access.
5. Run `argocd login argocd.miruohotspring.net --sso --grpc-web` and confirm the loopback callback succeeds.
6. Run a second Terraform plan and require `No changes.`

## Rollback and recovery

- Keep `admin.enabled: "true"` until independent recovery is tested.
- If Google or Cloudflare login fails, use the built-in administrator and revert only the affected OIDC or policy change.
- If GUI membership is wrong, restore the Rule group in Cloudflare Zero Trust; Terraform does not overwrite its members.
- If the generated RBAC key disappears, confirm the `argocd-ingress` Application still ignores `/data/policy.cloudflare.csv` with `RespectIgnoreDifferences=true`, then rerun the PostSync Job through an ordinary sync.
- Do not remove the previous Authentik client or identities until the remaining Cloud Drive migration and full recovery validation are complete.
