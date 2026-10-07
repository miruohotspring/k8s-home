# Cloudflare Access Terraform

This root owns only the existing Cloudflare Zero Trust organization settings and the three new OIDC SaaS Access applications/policies: `argocd`, `hermes`, and `cloud-drive`.

It **does not** manage existing SSH Access applications, identity providers, Access groups, users, DNS, tunnels, or Kubernetes/Sealed Secrets.

## State and credentials

- S3 backend: `web-app-template-tfstate-dev/platform/cloudflare-access/terraform.tfstate`, encrypted with an S3 lockfile.
- The state contains the sensitive email allowlists and generated SaaS client secrets. Do not print it, commit it, or upload plan/state artifacts.
- The provider reads `CLOUDFLARE_API_TOKEN`; CI maps this only from GitHub secret `CLOUDFLARE_ACCESS_API_TOKEN`.
- Required repository variable: `CLOUDFLARE_ACCOUNT_ID`.
- Required repository secret: `CLOUDFLARE_ACCESS_ALLOWED_EMAILS_JSON`, a JSON object with exactly `argocd`, `hermes`, and `cloud-drive` keys. The values must be email arrays; never put personal email addresses in this public repository.

The Access token must be scoped only to Access Organizations/Identity Providers/Groups and Access Applications/Policies write plus Users read. Do not grant DNS, Tunnel, R2, or account-token-edit permissions.

## One-time bootstrap

An administrator with existing AWS credentials first creates the state-only Actions role from the separate federation root:

```bash
cd infra/terraform/github-actions
terraform init
terraform plan -out=/secure/path/github-actions.tfplan
terraform apply /secure/path/github-actions.tfplan
terraform output -raw cloudflare_access_state_role_arn
```

Set the returned ARN as repository variable `CLOUDFLARE_ACCESS_STATE_ROLE_ARN`. Its OIDC trust is exactly `repo:miruohotspring/k8s-home:ref:refs/heads/main`; it can read/write only this root's state object and create/delete only its `.tflock` object.

Before the first Cloudflare apply, import the existing organization. Set sensitive values through your approved secret manager/environment rather than a shell history file:

```bash
cd infra/terraform/cloudflare-access
terraform init
terraform import cloudflare_zero_trust_organization.this "$TF_VAR_cloudflare_account_id"
terraform plan -out=/secure/path/cloudflare-access.tfplan
```

Review that the plan changes only the organization settings and creates the three intended applications/policies. The `saas_clients` output is sensitive; do not run a non-redacted `terraform output` in logs. Store generated client credentials through the separately reviewed secret-management path; this change intentionally does not create or sync a SealedSecret.

## Argo CD Web / CLI and Hermes integration

Argo CD uses its existing bundled Dex as the broker. The Cloudflare upstream client is confidential authorization-code only with callback `https://argocd.miruohotspring.net/api/dex/callback`; Dex provides Argo's separate Web and CLI clients, including public CLI S256 PKCE with the localhost callback. Hermes uses the same Dex issuer through its own public `hermes-dashboard` PKCE client and callback. Both applications therefore traverse the same Cloudflare SaaS application, allowing Access to reuse its existing application/global browser session; Dex v2.41.1 is not the browser-session authority. Cloudflare Access remains the upstream identity and MFA policy. The legacy direct Cloudflare callbacks remain registered for controlled rollback but are not the active Argo or Hermes login route. See `docs/argocd-cloudflare-access-oidc-runbook.md` for the native v2.13 compatibility limitations and staged cutover.

Administrator emails are encrypted in a SealedSecret and rendered into a private `policy.cloudflare.csv` overlay by a narrowly scoped PostSync Job. Keep the base `platform-admins` mapping, non-member denial, and break-glass admin; never replace these with `policy.default: role:admin`. Application callbacks, real browser login, and CLI token exchange must be verified separately from Terraform apply.

## CI behavior

Pull requests run formatting, backend-free validation, the contract test, actionlint, and zizmor without Cloudflare/AWS credentials or OIDC. On `main`, `workflow_dispatch` defaults to `plan`; choosing `apply` applies the same local saved plan only after rejecting all delete/replacement actions.
