# Temporary path-scoped applications used only to prove that Cloudflare Access
# self-hosted applications consume the organization-wide session across hosts.
# They do not require DNS or Tunnel changes and must remain isolated from the
# production application roots until the browser acceptance test passes.
locals {
  self_hosted_canaries = {
    argocd = {
      name   = "SSO Canary - Argo CD host"
      domain = "argocd.miruohotspring.net/__access_canary"
    }
    hermes = {
      name   = "SSO Canary - Hermes host"
      domain = "hermes.miruohotspring.net/__access_canary"
    }
    cloud-drive = {
      name   = "SSO Canary - Cloud Drive host"
      domain = "drive.miruohotspring.net/__access_canary"
    }
  }
}

resource "cloudflare_zero_trust_access_application" "self_hosted_canary" {
  for_each = local.self_hosted_canaries

  account_id                = var.cloudflare_account_id
  name                      = each.value.name
  type                      = "self_hosted"
  domain                    = each.value.domain
  allowed_idps              = [var.email_otp_identity_provider_id]
  auto_redirect_to_identity = true
  session_duration          = "720h"

  policies = [{
    id         = cloudflare_zero_trust_access_policy.self_hosted_canary[each.key].id
    precedence = 1
  }]

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_zero_trust_access_policy" "self_hosted_canary" {
  for_each = local.self_hosted_canaries

  depends_on = [cloudflare_zero_trust_organization.this]

  account_id = var.cloudflare_account_id
  name       = "Allow ${each.value.name} email OTP with TOTP"
  decision   = "allow"

  # All three canaries intentionally use the existing single-user Argo allowlist
  # so the experiment cannot broaden access to Hermes or Cloud Drive users.
  include = [
    for email in var.allowed_emails["argocd"] : {
      email = { email = email }
    }
  ]

  session_duration = "720h"

  mfa_config = {
    allowed_authenticators = ["totp"]
    mfa_disabled           = false
    session_duration       = "720h"
  }
}
