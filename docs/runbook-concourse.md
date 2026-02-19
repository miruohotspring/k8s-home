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
  -v git_branch=main
fly -t home unpause-pipeline -p <name>
```

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
- Recommended flow: generate a temporary vars file from Kubernetes Secrets, apply the pipeline, then delete the temp file.
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

Temporary vars file example:
```bash
tmp_vars=/tmp/web-app-template-secrets.yml

cat >"$tmp_vars" <<'EOF'
"concourse-github-ssh-app.private_key": |
  <PRIVATE_KEY_PEM>
"concourse-github-ssh.private_key": |
  <PRIVATE_KEY_PEM>
"concourse-aws-creds.aws_access_key_id": "<AWS_ACCESS_KEY_ID>"
"concourse-aws-creds.aws_secret_access_key": "<AWS_SECRET_ACCESS_KEY>"
"concourse-aws-creds.aws_region": "ap-northeast-1"
EOF
```

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
