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

## 2. Authentication and Connection

### 2.1 Login
```bash
fly -t home login -c https://concourse.miruohotspring.net
```

### 2.2 Token Refresh
- `fly` token is automatically refreshed while session is valid.
- If `401 unauthorized` appears, run login again.
- If browser SSO callback fails, use user/password directly:

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
fly -t home set-pipeline -p <name> -c ci/pipeline.yml \
  -l ci/vars/<env>.yml \
  -l /tmp/<name>-secrets.yml \
  -v git_branch=main
fly -t home unpause-pipeline -p <name>
```
- `-l /tmp/<name>-secrets.yml` (or equivalent secrets vars file) is mandatory for this environment.

### 3.2 Pause / Unpause / Destroy
```bash
fly -t home pause-pipeline -p <name>
fly -t home unpause-pipeline -p <name>
fly -t home destroy-pipeline -p <name>
```

### 3.3 Variable Supply (Secrets and Runtime Vars)
- Non-secret vars: keep in `ci/vars/<env>.yml` and review in PR.
- Secret vars: do not hardcode in pipeline YAML.
- Concourse is configured without Kubernetes credential manager, so secrets must be injected at `set-pipeline` time with `-l <secrets-file>`.
- `fly set-pipeline` must always include a dedicated secrets vars file (example: `/tmp/web-app-template-secrets.yml`).
- Minimal deployment variables for web apps:
  - `image_tag`
  - `ecr_registry`
  - `kube_context`
  - `namespace`
  - `domain`

Example:
```bash
fly -t home set-pipeline -p web-app-template -c ci/pipeline.yml \
  -l /tmp/web-app-template-secrets.yml \
  -v image_tag=$(git rev-parse --short HEAD)
```

### 3.4 Credential運用

Temporary secrets vars file handling (`mktemp` + `trap` required):
```bash
tmp_vars="$(mktemp /tmp/web-app-template-secrets.XXXXXX.yml)"
cleanup() { rm -f "$tmp_vars"; }
trap cleanup EXIT INT TERM
chmod 600 "$tmp_vars"

cat >"$tmp_vars" <<'EOF'
"concourse-github-ssh-app.private_key": |
  <PRIVATE_KEY_PEM>
"concourse-github-ssh.private_key": |
  <PRIVATE_KEY_PEM>
"concourse-aws-creds.aws_access_key_id": "<AWS_ACCESS_KEY_ID>"
"concourse-aws-creds.aws_secret_access_key": "<AWS_SECRET_ACCESS_KEY>"
"concourse-aws-creds.aws_region": "ap-northeast-1"
EOF

fly -t home set-pipeline -p web-app-template -c ci/pipeline.yml \
  -l ci/vars/prod.yml \
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
1. Generate/register a new GitHub deploy key, then update secret source used for `set-pipeline`.
2. Create a new AWS access key, update the secret source, and prepare a new secrets vars file.
3. Re-apply pipelines with `fly set-pipeline --check-creds`.
4. Run `fly check-resource` on key resources.
5. Disable and delete old credentials only after verification passes.

### 3.6 Verification

After credential updates or rotation, run:
```bash
fly -t home set-pipeline -p <name> -c ci/pipeline.yml \
  -l ci/vars/<env>.yml \
  -l "$tmp_vars" \
  --check-creds

fly -t home check-resource -r <name>/<resource>
fly -t home check-resource -r <name>/<resource2>
fly -t home jobs -p <name>
```
- Expected: `set-pipeline --check-creds` returns no missing/invalid credential errors.
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
kubectl get secret -n concourse
fly -t home watch -b <build-id>
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
