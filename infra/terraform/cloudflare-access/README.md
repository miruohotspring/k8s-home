# Cloudflare Access Terraform

This root owns the existing Cloudflare Zero Trust organization settings, the Google identity provider, and the three OIDC SaaS Access applications/policies: `argocd`, `hermes`, and `cloud-drive`.

It **does not** manage the existing One-time PIN provider, SSH Access applications, Access groups, users, DNS, tunnels, or Kubernetes/Sealed Secrets. One-time PIN remains available only as a rollback control-plane provider; these three SaaS applications accept Google only.

## State and credentials

- S3 backend: `web-app-template-tfstate-dev/platform/cloudflare-access/terraform.tfstate`, encrypted with an S3 lockfile.
- The state contains the sensitive email allowlists, Google OAuth client secret, and generated SaaS client secrets. Do not print it, commit it, or upload plan/state artifacts.
- The provider reads `CLOUDFLARE_API_TOKEN`; CI maps this only from GitHub secret `CLOUDFLARE_ACCESS_API_TOKEN`.
- Required repository variable: `CLOUDFLARE_ACCOUNT_ID`.
- Required repository secret: `CLOUDFLARE_ACCESS_ALLOWED_EMAILS_JSON`, a JSON object with exactly `argocd`, `hermes`, and `cloud-drive` keys. The values must be email arrays; never put personal email addresses in this public repository.
- Required repository secrets: `CLOUDFLARE_GOOGLE_CLIENT_ID` and `CLOUDFLARE_GOOGLE_CLIENT_SECRET`.

The Access token must be scoped only to Access Organizations/Identity Providers/Groups and Access Applications/Policies write plus Users read. Do not grant DNS, Tunnel, R2, or account-token-edit permissions.

## Google OAuth manual exception

Google does not expose a supported API, `gcloud` command, or Terraform resource for creating a general Google Sign-In OAuth client. Create that single client manually in the `miruohotspring` Google Cloud project as a Web application with redirect URI `https://miruohotspring.cloudflareaccess.com/cdn-cgi/access/callback`. Use only the standard `openid`, `email`, and `profile` identity scopes. Store the resulting values directly in the two GitHub Actions secrets above; never commit or paste them into plans, logs, or documentation.

All other Google resources used by CI—required APIs, the Workload Identity Pool/provider, service account, IAM, and the keyless GitHub Actions trust—are managed in `infra/terraform/google-identity`. No Google service-account key or API key is created.

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

Review that the plan changes only the organization settings, Google identity provider, and three intended applications/policies. The `saas_clients` output is sensitive; do not run a non-redacted `terraform output` in logs. Store generated client credentials through the separately reviewed secret-management path; this change intentionally does not create or sync a SealedSecret.

## Argo CD Web / CLI and Hermes integration

Argo CD uses its existing bundled Dex as the broker. The Cloudflare upstream client is confidential authorization-code only with callback `https://argocd.miruohotspring.net/api/dex/callback`; Dex provides Argo's separate Web and CLI clients, including public CLI S256 PKCE with the localhost callback. Hermes remains a separate direct public-PKCE Cloudflare SaaS client. Routing Hermes through Argo's Dex was tested and reverted because it did not remove the Cloudflare email prompt and added an unnecessary runtime dependency. Cloudflare Access remains the upstream identity and MFA policy for both applications. The legacy direct Argo callbacks remain registered for controlled rollback but are not the active Argo login route. See `docs/argocd-cloudflare-access-oidc-runbook.md` for the native v2.13 compatibility limitations and staged cutover.

Administrator emails are encrypted in a SealedSecret and rendered into a private `policy.cloudflare.csv` overlay by a narrowly scoped PostSync Job. Keep the base `platform-admins` mapping, non-member denial, and break-glass admin; never replace these with `policy.default: role:admin`. Application callbacks, real browser login, and CLI token exchange must be verified separately from Terraform apply.

All three SaaS applications have `auto_redirect_to_identity` enabled and exactly one allowed IdP (Google), so Access redirects directly to the standard Google OIDC flow without rendering an IdP selection page. This is required for the Argo CLI browser callback as well as browser login. Keep this application-scoped; enabling the organization-wide redirect would also change unrelated existing applications and identity providers.

## CI behavior

Pull requests run formatting, backend-free validation, the contract test, actionlint, and zizmor without Cloudflare/AWS credentials or OIDC. On `main`, `workflow_dispatch` defaults to `plan`; choosing `apply` applies the same local saved plan only after rejecting all delete/replacement actions.
