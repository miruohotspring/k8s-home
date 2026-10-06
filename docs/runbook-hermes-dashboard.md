# Hermes Dashboard + authentik

## Ownership

- Dashboard: `https://hermes.miruohotspring.net` (local WSL Hermes host, not Kubernetes).
- IdP: `https://auth.miruohotspring.net/application/o/hermes/`.
- GitOps source: `infra/authentik/manifests/platform-blueprint.yaml`, separate `hermes.yaml` blueprint. Existing application blueprints remain unchanged.
- Access: dedicated `hermes-users` group; only `akadmin`, as explicitly requested by the operator. The daily `miruohotspring` account is not admitted to Hermes; its identity and Cloud Drive access remain unchanged. Do not grant all authentik users dashboard access: Hermes exposes the host's tools and data.
- Authentication: existing password + TOTP flow; public OIDC client with PKCE S256, exact HTTPS callback, signed ID tokens. No client secret.
- Access/ID token lifetime: 10 minutes. Refresh grant: 365 days, with `offline_access` requested. This does not override Hermes' own session-cookie lifetime.

## Local Hermes settings

Apply with `hermes config set` (preserves the rest of the configuration):

```yaml
dashboard:
  public_url: https://hermes.miruohotspring.net
  oauth:
    provider: self-hosted
    self_hosted:
      issuer: https://auth.miruohotspring.net/application/o/hermes/
      client_id: hermes-dashboard
      scopes: openid profile email offline_access
```

The callback is exactly `https://hermes.miruohotspring.net/auth/callback`.
Keep `hermes-dashboard.service` bound to `127.0.0.1:9119`; do not expose the listener on the LAN.
The stock public URL setting owns Host/Origin admission and requires authentication. The old wildcard `*.localhost` source patch is not required.

## Network

A dedicated locally managed Cloudflare Tunnel named `hermes-wsl` runs as the user's `hermes-cloudflared.service`. It routes only the public Hermes hostname to `http://127.0.0.1:9119`; its final rule is `http_status:404`. This avoids depending on Kubernetes-to-WSL addressing or adding a connector to the existing Kubernetes tunnel.

- Local tunnel config: `~/.cloudflared/hermes.yaml`.
- Tunnel credentials: local `~/.cloudflared/` JSON, mode 0600, never commit or print.
- Unit: `~/.config/systemd/user/hermes-cloudflared.service`.
- DNS: proxied CNAME for the public Hermes hostname to the dedicated tunnel.
- The Windows/WSL host must remain running; the Kubernetes IdP alone does not make the local dashboard available.

## Verification and recovery

1. Verify the new blueprint is successful, the exact callback is registered, and the group binding is enabled.
2. Verify OIDC discovery returns the expected HTTPS issuer and signing keys.
3. Before routing public traffic, verify anonymous requests to `/api/config` and `/api/sessions` fail and `/auth/login?provider=self-hosted` points to authentik with PKCE S256 and the exact public callback.
4. Verify the same behavior through the public domain, including a rejected foreign Host and an unauthenticated WebSocket.
5. Complete a normal browser login with the intended user's password/TOTP, then verify the dashboard and chat. Provisioning and a redirect check alone do not prove this final step.
6. To cut off access independently of the IdP, stop `hermes-cloudflared.service`. Do not restore an unauthenticated configuration while the public tunnel is serving.
7. For a local rollback, stop the tunnel, restore the pre-change Hermes config backup and the pre-change Git reference, then restart only `hermes-dashboard.service`. The Telegram gateway need not restart.
