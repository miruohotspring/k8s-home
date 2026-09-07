# Concourse CI/CD Operational Runbook

## 1. Scope and Daily Operations
- URL: `https://concourse.miruohotspring.net`
- Namespace: `concourse`
- Typical target alias: `home`

### 1.1 Pipeline Inventory
```bash
fly -t home pipelines
```

### 1.2 Build History and Job Status
```bash
fly -t home builds
fly -t home jobs -p <pipeline>
```

### 1.3 Trigger / Retry Jobs
```bash
fly -t home trigger-job -j <pipeline>/<job>
fly -t home watch -j <pipeline>/<job>
```

### 1.4 Concourse PostgreSQL Baseline (GitOps)
- PostgreSQL image is managed in `infra/concourse/values.yaml`; floating `latest` is forbidden.
- Current manifest and live baseline: `postgres:17.6`.
- Resource expectation for `concourse-postgresql`:
  - `requests`: `cpu=250m`, `memory=512Mi`
  - `limits`: `cpu=1`, `memory=1Gi`

Verification:
```bash
kubectl -n concourse get sts concourse-postgresql \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}{.spec.template.spec.containers[0].resources}{"\n"}'
```

## 2. Authentication and Connection

Primary human authentication uses authentik OIDC with email address, password, and TOTP. The session lifetime is 365 days. The `platform-admins` authentik group maps to the Concourse `main` team. See `docs/runbook-authentik.md` for enrollment, recovery, and session revocation.

### 2.1 SSO Login

```bash
fly -t home login -c https://concourse.miruohotspring.net
```

Select **Authentik** in the browser and verify team membership:

```bash
fly -t home teams
```

### 2.2 Token Refresh
- `fly` token is automatically refreshed while session is valid.
- If `401 unauthorized` appears, run login again.
- If browser SSO callback fails during migration, use the retained break-glass local account directly:

```bash
fly -t home login -c https://concourse.miruohotspring.net -u admin -p '<PASSWORD>'
```

### 2.3 Connection Failure Checklist
```bash
kubectl get pods -n concourse
kubectl get svc -n concourse
kubectl get ingress -n concourse
kubectl logs -n concourse deploy/concourse-web --tail=200
```

## 3. Pipeline Management

### 3.1 Register / Update Pipeline
```bash
# Preferred when the repository provides a checked-in wrapper:
./ci/set-pipeline.sh

# Direct fallback; add -l only for a non-secret vars file that exists in that repo:
fly -t home set-pipeline -p <name> -c ci/pipeline.yml --non-interactive
fly -t home unpause-pipeline -p <name>
fly -t home check-resource -r <name>/<resource>
```
- Secrets are normally resolved at runtime from Kubernetes; a local secrets vars file is
  only for a scoped migration or emergency override.
- Re-validate critical resources with `fly check-resource` immediately after `set-pipeline`.

### 3.2 Pause / Unpause / Destroy
```bash
fly -t home pause-pipeline -p <name>
fly -t home unpause-pipeline -p <name>
fly -t home destroy-pipeline -p <name>
```

### 3.3 Variable Supply (Secrets and Runtime Vars)
- Non-secret vars: keep in `ci/vars/<env>.yml` and review in PR.
- Secret vars: do not hardcode in pipeline YAML.
- Concourse is configured with the Kubernetes credential manager:
  - `CONCOURSE_KUBERNETES_IN_CLUSTER=true`
  - `CONCOURSE_KUBERNETES_NAMESPACE_PREFIX=concourse-`
- The `main` team's `((secret-name.key-name))` references resolve against Kubernetes
  Secrets in `concourse-main`.
- Keep repository-scoped deploy keys separate; do not reuse a generic key between
  unrelated repositories or pipelines.
- Minimal deployment variables for web apps:
  - `image_tag`
  - `ecr_registry`
  - `kube_context`
  - `namespace`
  - `domain`

Example:
```bash
./ci/set-pipeline.sh
```

### 3.4 Credential運用

The source of truth is the GitOps-managed SealedSecrets under
`infra/secrets/*-sealed.yaml`, which create runtime Secrets in `concourse-main`.
`concourse-web` reads them through `RoleBinding/concourse-web-main`.

Repository-specific references currently include:

- m3usick app read: `((concourse-github-ssh-app.private_key))`
- m3usick GitOps write: `((concourse-github-ssh.private_key))`
- web-app-template app read: `((web-app-template-github-ssh-app.private_key))`
- web-app-template GitOps write: `((web-app-template-github-ssh-gitops.private_key))`
- AWS runtime credentials: `((concourse-aws-creds.<key>))`

Use a temporary local vars file only for a migration or emergency override. It must use
`mktemp` and `trap` and must not become a second long-lived source of truth.

Temporary secrets vars file handling (`mktemp` + `trap` required):
```bash
tmp_vars="$(mktemp /tmp/web-app-template-secrets.XXXXXX.yml)"
cleanup() { rm -f "$tmp_vars"; }
trap cleanup EXIT INT TERM
chmod 600 "$tmp_vars"

cat >"$tmp_vars" <<'EOF'
"web-app-template-github-ssh-app.private_key": |
  <PRIVATE_KEY_PEM>
"web-app-template-github-ssh-gitops.private_key": |
  <PRIVATE_KEY_PEM>
"concourse-aws-creds.aws_access_key_id": "<AWS_ACCESS_KEY_ID>"
"concourse-aws-creds.aws_secret_access_key": "<AWS_SECRET_ACCESS_KEY>"
"concourse-aws-creds.aws_region": "ap-northeast-1"
EOF

fly -t home set-pipeline -p web-app-template -c ci/pipeline.yml \
  -l "$tmp_vars" \
  --check-creds
```

Permanent storage rule (must not use `/tmp`):
```bash
install -d -m 700 ~/.config/concourse/secrets
cp <path-from-secret-manager>/<pipeline>.yml ~/.config/concourse/secrets/<pipeline>.yml
chmod 600 ~/.config/concourse/secrets/<pipeline>.yml
```
- Keep long-lived secrets vars files only under `~/.config/concourse/secrets/` (or another restricted directory outside `/tmp`).
- Enforce permissions: directory `700`, file `600`.
- Plaintext secrets are forbidden in Git, PR comments, docs, issue trackers, and chat logs.

### 3.5 Rotation

Recommended regular rotation intervals:
- GitHub deploy key: every 90 days.
- AWS access key used by Concourse: every 90 days.

Emergency rotation triggers (rotate immediately):
- Any leak/suspicion of private key or access key exposure.
- Offboarding or role change of a credential owner.
- Repeated authentication failures or suspicious audit log events.

Rotation procedure highlights:
1. Generate/register a repository-scoped GitHub deploy key or a new AWS access key.
2. Reseal the matching `infra/secrets/*-sealed.yaml` resource.
3. Sync `platform-secrets` and verify the expected Secret name and keys in `concourse-main`
   without printing credential values.
4. Run `fly check-resource` on every affected resource.
5. Disable and delete old credentials only after read/write behavior is verified.

### 3.6 Verification

After credential updates or rotation, run:
```bash
kubectl -n argocd get app platform-secrets
kubectl -n concourse-main get secret
kubectl -n concourse-main get rolebinding concourse-web-main

fly -t home check-resource -r <name>/<resource>
fly -t home check-resource -r <name>/<resource2>
fly -t home jobs -p <name>
```
- Expected: `platform-secrets` is `Synced/Healthy`, required runtime Secrets exist in
  `concourse-main`, and `concourse-web` can read them through the scoped binding.
- Expected: each `check-resource` succeeds and downstream jobs become runnable.

## 4. Incident Recovery

### 4.1 Web UI Not Reachable
1. Check DNS/TLS/Ingress status.
2. Check `concourse-web` pod health and restarts.
3. Restart web deployment only if health probes keep failing.

```bash
kubectl rollout restart deploy/concourse-web -n concourse
kubectl rollout status deploy/concourse-web -n concourse
```

### 4.2 Jobs Keep Failing
1. Inspect failing build logs from Web UI or `fly watch`.
2. Verify required vars/secrets are present.
3. Re-run after fixing inputs.

```bash
kubectl get secret -n concourse-main
kubectl get rolebinding -n concourse-main concourse-web-main
fly -t home watch -b <build-id>
```

If the failure includes `connection refused` against `concourse-postgresql`:
```bash
kubectl -n concourse describe pod concourse-postgresql-0 | sed -n '/Last State/,+8p'
kubectl -n concourse get sts concourse-postgresql \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}{.spec.template.spec.containers[0].resources}{"\n"}'
fly -t home check-resource -r web-app-template/update-gitops-backend-values
```

### 4.3 Worker Not Responding
```bash
kubectl get pods -n concourse -l app=concourse-worker
kubectl logs -n concourse deploy/concourse-worker --tail=200
kubectl rollout restart deploy/concourse-worker -n concourse
kubectl rollout status deploy/concourse-worker -n concourse
```

## 5. Quick Health Verification
```bash
fly -t home pipelines
fly -t home workers
kubectl get pods -n concourse
```
- Expected: all workers are `running`, key pipelines are `unpaused`, no crash loops.
