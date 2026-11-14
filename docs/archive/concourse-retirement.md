# Concourse retirement record

Concourse was replaced by GitHub Actions for m3usick, Cloud Drive, and web-app-template. The final source cleanup removes the Argo CD Application, Helm values, runtime credential copies, authentik relying party, and namespace/project allowlists. GitHub Actions credentials and Argo repository read keys are preserved.

## Recovery evidence

The protected backup remains outside Git at:

`/home/miruo/.hermes/backups/concourse-retirement-20261006T092935Z/`

A fresh offline restore into PostgreSQL 17.6 with networking disabled verified:

- `tables=61`
- `pipelines=3`
- `builds=79`

The directory also contains pipeline YAML, build/workload inventory, and the custom-format PostgreSQL dump. Keep directory mode 0700 and files 0600.

## Restore boundary

Normal application rollback uses GitHub Actions/GitOps and does not restore Concourse. A historical restore requires a new isolated PostgreSQL instance, creation of the `concourse` database role, and `pg_restore` validation before any network exposure. Never restore over an active database.

Deleting the three retained PVCs requires **explicit data-destruction approval**. The final cluster cleanup must read back namespace, PVC, Argo Application, DNS, and authentik state before this retirement is considered complete.
