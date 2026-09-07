# authentik OIDC Operational Runbook

## 1. Scope

- authentik URL: `https://auth.miruohotspring.net`
- Namespace: `authentik`
- OIDC consumers:
  - Argo CD: `https://argocd.miruohotspring.net`
  - Concourse: `https://concourse.miruohotspring.net`
- Authorization group: `platform-admins`
- Authentication: email address + password + RFC 6238 TOTP
- Session lifetime: 12 hours

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

If the public hostname is not configured, add the DNS route for the existing tunnel and configure its public hostname to forward to the ingress-nginx service:

```bash
cloudflared tunnel route dns k8s-home auth.miruohotspring.net
```

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

## 4. First daily user

Public self-registration is not enabled. Create or invite users administratively.

1. In **Directory > Users**, create a user whose username and email are both the user's unique email address.
2. Set an initial password and require the user to replace it over a separate trusted channel if applicable.
3. Add the user to **Directory > Groups > platform-admins**.
4. In a private browser, start login from Argo CD or Concourse.
5. Enter email address and password.
6. When prompted, scan the TOTP QR code and enter the six-digit code.
7. Open `https://auth.miruohotspring.net/if/flow/default-authenticator-static-setup/` and create static single-use recovery codes. Store them offline and separately from the TOTP device.
8. If the TOTP device is lost, use one recovery code, remove the lost TOTP device, enroll a new one, and rotate the remaining recovery codes. An authentik administrator can reset the device if no recovery code remains.

SMTP-backed invitations and recovery may be added later. Until then, password resets and account recovery are administrator-assisted.

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

Do not disable either local administrator unless all checks above pass.

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
