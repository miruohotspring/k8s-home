locals {
  apps = {
    argocd = {
      name   = "Argo CD"
      domain = "argocd.miruohotspring.net"
      redirect_uris = [
        "https://argocd.miruohotspring.net/auth/callback",
        "https://argocd.miruohotspring.net/api/dex/callback",
        "https://argocd.miruohotspring.net/pkce/verify",
        "http://localhost:8085/auth/callback",
      ]
      # The bundled Dex authenticates upstream as a confidential client and
      # provides Argo's separate Web/CLI clients, including CLI PKCE.
      allow_pkce_without_secret = false
    }
    hermes = {
      name                      = "Hermes Dashboard"
      domain                    = "hermes.miruohotspring.net"
      redirect_uris             = ["https://hermes.miruohotspring.net/auth/callback"]
      allow_pkce_without_secret = true
    }
    cloud-drive = {
      name                      = "Cloud Drive"
      domain                    = "api-drive.miruohotspring.net"
      redirect_uris             = ["https://api-drive.miruohotspring.net/v1/auth/callback"]
      allow_pkce_without_secret = false
    }
  }
}

resource "cloudflare_zero_trust_organization" "this" {
  account_id                  = var.cloudflare_account_id
  auth_domain                 = "miruohotspring.cloudflareaccess.com"
  name                        = "miruohotspring.cloudflareaccess.com"
  allow_authenticate_via_warp = false
  is_ui_read_only             = false
  session_duration            = "720h"
  mfa_required_for_all_apps   = false

  # Preserve existing organization-wide behavior; do not alter unrelated apps.
  deny_unmatched_requests                     = false
  deny_unmatched_requests_exempted_zone_names = []
  # The API requires non-null fields even while enforcement remains disabled.
  service_token_inactivity = {
    enabled                   = false
    action                    = "disable"
    inactivity_threshold_days = 90
  }

  mfa_config = {
    allowed_authenticators        = ["totp"]
    amr_matching_session_duration = "0m"
    session_duration              = "720h"
  }

  lifecycle {
    prevent_destroy = true

  }
}

resource "cloudflare_zero_trust_access_application" "app" {
  for_each = local.apps

  account_id = var.cloudflare_account_id
  name       = each.value.name
  type       = "saas"

  allowed_idps     = [var.email_otp_identity_provider_id]
  session_duration = "720h"
  policies = [
    {
      id         = cloudflare_zero_trust_access_policy.allow_email_otp_totp[each.key].id
      precedence = 1
    }
  ]

  saas_app = {
    app_launcher_url                 = each.key == "cloud-drive" ? "https://drive.miruohotspring.net" : "https://${each.value.domain}"
    auth_type                        = "oidc"
    access_token_lifetime            = "10m"
    allow_pkce_without_client_secret = each.value.allow_pkce_without_secret
    grant_types                      = each.key == "argocd" ? ["authorization_code", "refresh_tokens"] : ["authorization_code_with_pkce", "refresh_tokens"]
    redirect_uris                    = each.value.redirect_uris
    refresh_token_options = {
      lifetime = "719h"
    }
    scopes = ["openid", "email", "profile"]
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_zero_trust_access_policy" "allow_email_otp_totp" {
  for_each = local.apps

  # Organization-level enrollment must exist before policies can require MFA.
  depends_on = [cloudflare_zero_trust_organization.this]

  account_id = var.cloudflare_account_id
  name       = "Allow ${each.value.name} email OTP with TOTP"
  decision   = "allow"

  include = [
    for email in var.allowed_emails[each.key] : {
      email = {
        email = email
      }
    }
  ]

  session_duration = "720h"

  mfa_config = {
    allowed_authenticators = ["totp"]
    mfa_disabled           = false
    session_duration       = "720h"
  }
}
