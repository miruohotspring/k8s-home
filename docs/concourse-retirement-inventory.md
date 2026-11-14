# Concourse retirement inventory and staged plan

**Audit date:** 2026-11-14 JST

**Source baseline:** `62041732c3b59e67b1e2a679de5e8a143bed527b`

**Scope:** `k8s-home`, the reachable local CI/GitOps repositories, GitHub Actions
metadata for m3usick, and read-only queries against the default Kubernetes
context. No cluster mutation was performed for this audit.

## Preserved recovery evidence

The pre-stop backup exists outside Git at
`/home/miruo/.hermes/backups/concourse-retirement-20261006T092935Z/`. Its
inventory contains pipeline/build metadata, a PostgreSQL dump, workload data,
and restore verification:

- `pipelines.json`, `builds.json`, `workloads.json`
- `concourse-postgresql.dump`
- `m3usick-pipeline.yml`, `cloud-drive-pipeline.yml`,
  `web-app-template-pipeline.yml`
- `restore-verification.json`, `post-retirement-verification.json`

The backup is intentionally not copied into Git because it can contain sensitive
operational metadata. The earlier restore verification recorded 61 tables, three
pipelines, and 79 builds. See `docs/runbook-github-actions.md` for the guarded
restore procedure.

## Current cluster inventory

Read-only inspection on 2026-11-14 found all Concourse workloads stopped:

| Resource | Desired replicas | Retained data |
| --- | ---: | --- |
| `Deployment/concourse-web` | 0 | none |
| `StatefulSet/concourse-worker` | 0 | `concourse-work-dir-concourse-worker-{0,1}` (20 Gi each) |
| `StatefulSet/concourse-postgresql` | 0 | `data-concourse-postgresql-0` (10 Gi) |

The `argocd/Application/concourse` remains `Synced` and owns the Helm chart plus
the PostgreSQL replica override. It still has automated prune/self-heal and a
known intentional repeated-resource warning for `concourse-postgresql`. The
`concourse-main` namespace and `concourse-web-main` RoleBinding also remain.

## Consumer audit and deletion boundary

| Consumer | Evidence | Retirement decision |
| --- | --- | --- |
| **m3usick** | `gammaLaboratory/m3usick` has active GitHub Actions writer workflows; `CI_DEPLOY_ENABLED=true`; the `GITOPS_DEPLOY_KEY` secret exists; successful post-cutover Actions runs write `gammaLaboratory/m3usick-gitops`. | Remove only the two m3usick-specific Concourse repository-key manifests in this change. The source-only contract is `scripts/verify_m3usick_writer.py`. |
| **Cloud Drive** | Local `cloud-drive/ci/pipeline.yml` still references `cloud-drive-github-ssh-{app,gitops}`, `concourse-aws-creds`, `concourse-cloudflare-creds`, runtime/D1 and R2 state Secrets. | **Blocker:** retain its scoped and shared credentials, `concourse-main`, RBAC, and Concourse resources until its pipeline is destroyed after an independently verified Actions cutover. |
| **web-app-template** | Local `web-app-template/ci/pipeline.yml` still references `web-app-template-github-ssh-{app,gitops}`, `concourse-aws-creds`, `concourse-cloudflare-creds`, and `telegram-creds`. | **Blocker:** retain its scoped and shared credentials, `concourse-main`, RBAC, and Concourse resources until migration/retirement is complete. |
| **Historical documentation** | `k8s-home-document` and application-repository historical files contain Concourse descriptions. | Not Kubernetes source of truth; retain as history and do not use as an operational recovery instruction. |

Therefore, deleting the Concourse Helm Application, namespace, RBAC, PVCs, shared
AWS/Cloudflare credentials, or Cloud Drive/template credentials in #65 would be
unsafe.

## This change: m3usick-only source cleanup

This commit removes the GitOps-managed SealedSecret manifests for:

- `concourse-main/concourse-github-ssh-app`
- `concourse-main/concourse-github-ssh`

They are only referenced by the former m3usick pipeline in the audited source.
The replacement GitHub Actions writer has its own repository secret; removing the
Kubernetes copies does **not** revoke the deploy key registered on
`gammaLaboratory/m3usick-gitops`.

After merge and Argo CD reconciliation, use only read commands to confirm the
source cleanup applied before calling the writer cutover complete:

```bash
python3 scripts/verify_m3usick_writer.py
kubectl -n concourse-main get secret concourse-github-ssh-app concourse-github-ssh
kubectl -n argocd get application platform-secrets -o wide
```

Expected result: the verifier succeeds, `platform-secrets` is synced/healthy, and
both removed Secret names return `NotFound`. If either Secret remains, investigate
Argo CD sync/prune state; do not manually delete unrelated Secrets.

## Staged global retirement plan

1. **Complete m3usick cleanup (this change).** Merge, let Argo CD prune only the
   two listed Secrets, run the read-back above, and keep the backup intact.
2. **Migrate Cloud Drive and web-app-template separately.** For each consumer,
   pause/drain its Concourse writer, validate the Actions writer from its default
   branch through ECR/GitOps/Argo health, and prove no shared state or database
   writer overlaps. Destroy the obsolete pipeline only after that proof.
3. **Remove Concourse credentials and access after the final consumer.** Inventory
   every `concourse-main` Secret, the `concourse-web-main` RoleBinding, the
   cluster role/service accounts, ingress/DNS/Authenik provider, and AWS access
   key/policies. Revoke credentials only after the corresponding pipeline is
   destroyed and its replacement has a verified rollback path.
4. **Remove the application and retained storage last.** Export and restore-test a
   final PostgreSQL backup, record the Argo resource inventory, then remove the
   Concourse Application from the root app. Delete the three PVCs only under an
   explicit data-destruction approval; PVC retention is the final recovery guard.

Each stage needs a separate PR and read-back of the exact target state. Never
remove the shared Concourse resources merely because the web/worker/PostgreSQL
replicas are zero.
