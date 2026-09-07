# authentik OIDC Operational Runbook

## 1. Scope

- authentik URL: `https://auth.miruohotspring.net`
- Namespace: `authentik`
- OIDC consumers:
  - Argo CD: `https://argocd.miruohotspring.net`
  - Concourse: `https://concourse.miruohotspring.net`
- Authorization group: `platform-admins`
- Authentication: email address + password + RFC 6238 TOTP
- Session lifetime: 365 days

The 365-day session is a deliberate convenience trade-off for this private platform. It
also increases the impact of a stolen browser session. Sign out explicitly on shared or
lost devices and revoke that user's active authentik sessions after a suspected compromise.
The **Remember me** and **Remember device** options remain disabled because the base
authentik session itself is persistent for 365 days.

The built-in Argo CD administrator and the Concourse local administrator remain enabled during migration. Do not disable them until both OIDC paths have been verified from a private browser session.

## 2. Deployment and health

```bash
kubectl -n argocd get application authentik
kubectl -n authentik get deploy,sts,pod,pvc,ingress
kubectl -n authentik rollout status deploy/authentik-server --timeout=10m
kubectl -n authentik rollout status deploy/authentik-worker --timeout=10m
kubectl -n authentik rollout status sts/authentik-postgresql --timeout=10m
curl -fsS https://auth.miruohotspring.net/-/health/ready/
```

Expected:

- `authentik`, `authentik-postgresql`, and `authentik-postgresql-backups` PVCs are `Bound`.
- Server and worker deployments are available.
- The health endpoint returns HTTP 200.
- The `k8s-home platform authentication` blueprint is `Successful`.

If the public hostname is not configured, add the DNS route for the existing tunnel:

```bash
cloudflared tunnel route dns k8s-home auth.miruohotspring.net
```

The `k8s-home` tunnel is remotely managed. Add or update its ingress rule through the Cloudflare API/CLI workflow while preserving every existing rule and the final `http_status:404` catch-all:

```yaml
hostname: auth.miruohotspring.net
service: https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443
originRequest:
  noTLSVerify: true
```

The HTTPS origin is intentional: ingress-nginx must pass `X-Forwarded-Proto: https` so authentik publishes HTTPS OIDC issuer URLs. Using the otherwise-common HTTP port 80 makes authentik publish an `http://` issuer and Concourse rejects it. `noTLSVerify` applies only to the tunnel-to-ingress internal hop because ingress-nginx uses its internal/default certificate.

Verify the route and both OIDC issuers:

```bash
curl -fsS https://auth.miruohotspring.net/-/health/live/
curl -fsS https://auth.miruohotspring.net/application/o/argocd/.well-known/openid-configuration
curl -fsS https://auth.miruohotspring.net/application/o/concourse/.well-known/openid-configuration
```

Both discovery documents must return their corresponding `https://auth.miruohotspring.net/application/o/.../` issuer.

## 3. First-time initialization

Open the trailing-slash URL:

```text
https://auth.miruohotspring.net/if/flow/initial-setup/
```

1. Set a strong password and email address for bootstrap administrator `akadmin`.
2. Open **Admin interface** and confirm **System > Blueprints > Instances** reports `k8s-home platform authentication` as successful.
3. Confirm the `Argo CD` and `Concourse` applications and providers exist.
4. Sign out, then sign in again from a private browser window. The platform authentication flow now requires TOTP; scan the QR code using any RFC 6238-compatible app and enter the generated code.
5. Open `https://auth.miruohotspring.net/if/flow/default-authenticator-static-setup/` and create static single-use recovery codes. Store them offline and separately from the TOTP device.
6. Verify one recovery code in a private browser, then generate a fresh set if authentik invalidates the tested set.
7. Keep `akadmin` for authentik administration only; do not use it as the daily application identity.

## 4. Invite a daily user

Public self-registration is disabled. The GitOps-managed enrollment flow
`platform-invitation-enrollment` requires a valid Invitation token and creates an internal
user without creating an authenticated session. This ensures the user's first application
login still passes through password and required TOTP validation.

1. Sign in as an authentik administrator and open **Directory > Invitations**.
2. Select **New Invitation**. Choose enrollment flow `platform-invitation-enrollment`.
3. Use a non-sensitive slug-style name, set **Expires** to no more than **24 hours**, and
   enable **Single use**.
4. Optionally prefill the intended identity with **Custom attributes**. Keep username and
   email identical for email-first login:

   ```yaml
   username: user@example.com
   email: user@example.com
   name: Example User
   ```

5. Create the invitation and select **Copy Link**. SMTP is not configured, so do not use
   **Send via Email**. Send the URL over a trusted private channel. Treat the URL as a
   bearer credential and never put it in Git, an issue, a PR, or a shared log.
6. The recipient opens the link in a private browser, confirms that username and email are
   their unique email address, enters their name, and chooses a password.
7. After enrollment, an administrator opens **Directory > Users**, selects the user, and
   adds them to `platform-admins` only if they should administer both Argo CD and the
   Concourse `main` team. Do not grant authentik superuser. A user who should have less
   privilege needs a separate group and relying-party RBAC mapping.
8. The recipient starts a fresh login from Argo CD or Concourse. Enter email and password;
   the platform authentication flow requires RFC 6238 TOTP enrollment before access.
9. Open `https://auth.miruohotspring.net/if/flow/default-authenticator-static-setup/` and
   create static single-use recovery codes. Store them offline and separately from the
   TOTP device.
10. Verify the invitation was consumed and cannot be reused, both OIDC applications work,
    and only the intended group permissions were granted.

To revoke an unused invitation, delete it from **Directory > Invitations**. If it expires,
create a new invitation instead of extending or reusing the old URL.

## 5. OIDC verification gate

Use a private browser session so an existing administrator cookie cannot hide an RBAC failure.

### Argo CD

1. Open `https://argocd.miruohotspring.net`.
2. Select **Log in via Authentik**.
3. Complete email, password, and TOTP authentication.
4. Confirm the user can list, inspect, and synchronize applications.
5. Confirm Argo CD reports membership in `platform-admins`.

CLI verification:

```bash
argocd login argocd.miruohotspring.net --sso
argocd account get-user-info
argocd app list
```

### Concourse

1. Open `https://concourse.miruohotspring.net`.
2. Select **Authentik**.
3. Complete authentication.
4. Confirm the user is a member of the `main` team and can list pipelines.

CLI verification:

```bash
fly -t home login -c https://concourse.miruohotspring.net
fly -t home teams
fly -t home pipelines
```

Do not disable either local administrator unless all checks above pass and at least one `pg_restore --list`-validated dump has been copied to encrypted off-cluster storage.

## 6. Disable routine local login after verification

Make these changes through a reviewed Git commit:

- Argo CD: set `admin.enabled: "false"` in `apps/argocd/argocd-cm.yaml`.
- Concourse: set `concourse.web.localAuth.enabled: false` and remove `mainTeam.localUser` from `infra/concourse/values.yaml`.

Keep the encrypted emergency credentials and the following recovery procedure available outside authentik.

## 7. Break-glass recovery

If authentik is unavailable:

1. Do not delete or recreate authentik PVCs.
2. Re-enable Argo CD `admin` and/or Concourse local auth through GitOps.
3. Wait for Argo CD sync and the affected rollout.
4. Use the existing local administrator credential.
5. Repair authentik, verify OIDC, then disable routine local login again.

Health and logs:

```bash
kubectl -n authentik get pod,pvc
kubectl -n authentik logs deploy/authentik-server --tail=200
kubectl -n authentik logs deploy/authentik-worker --tail=200
kubectl -n authentik logs sts/authentik-postgresql --tail=200
```

## 8. Backup

A logical PostgreSQL dump runs daily at 03:17 UTC and keeps 14 days on the `authentik-postgresql-backups` PVC.

```bash
kubectl -n authentik get cronjob authentik-postgresql-backup
kubectl -n authentik create job --from=cronjob/authentik-postgresql-backup authentik-backup-manual
kubectl -n authentik wait --for=condition=complete job/authentik-backup-manual --timeout=10m
kubectl -n authentik logs job/authentik-backup-manual
```

The backup PVC uses `local-path`; it does not protect against loss of the Kubernetes node. Regularly copy a verified dump to encrypted off-cluster storage.

Example export using a temporary reader pod:

```bash
kubectl -n authentik apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: authentik-backup-export
spec:
  restartPolicy: Never
  containers:
    - name: reader
      image: postgres:17.11-bookworm@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0
      command: ["sleep", "3600"]
      volumeMounts:
        - name: backup
          mountPath: /backup
  volumes:
    - name: backup
      persistentVolumeClaim:
        claimName: authentik-postgresql-backups
EOF
kubectl -n authentik wait --for=condition=Ready pod/authentik-backup-export --timeout=2m
kubectl -n authentik exec authentik-backup-export -- sh -c 'ls -1t /backup/authentik-*.dump'
kubectl -n authentik cp authentik-backup-export:/backup/<DUMP_FILE> ./<DUMP_FILE>
docker run --rm -v "$PWD:/backup:ro" postgres:17.11-bookworm@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0 pg_restore --list /backup/<DUMP_FILE> >/dev/null
kubectl -n authentik delete pod authentik-backup-export
```

## 9. Restore

A restore replaces identity, group, TOTP, and OIDC state. Take a fresh backup first and use a maintenance window.

1. Scale authentik server and worker to zero.
2. Copy the selected dump into a temporary PostgreSQL client pod or the backup PVC.
3. Terminate active database sessions.
4. Drop and recreate the `authentik` database owned by `authentik`.
5. Run `pg_restore --clean --if-exists --no-owner --dbname=authentik <dump>`.
6. Scale authentik back up.
7. Verify the blueprint, user login, TOTP, and both OIDC applications.

Never restore a dump into a running authentik instance.

## 10. Secret rotation

Secrets are stored only as SealedSecret ciphertext:

- `authentik-env`: authentik key, database password, OIDC client secrets
- `authentik-postgresql`: PostgreSQL user/admin passwords
- `argocd-authentik-oidc`: Argo CD OIDC client secret
- `concourse-web`: Concourse runtime keys and OIDC client credentials

OIDC client secret rotation must update authentik and the corresponding application secret in the same change. PostgreSQL password rotation requires a coordinated database password change; replacing only the Kubernetes Secret will cause an outage.
