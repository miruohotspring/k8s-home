locals {
  apps = {
    argocd = {
      name                      = "Argo CD"
      domain                    = "argocd.miruohotspring.net"
      redirect_uri              = "https://argocd.miruohotspring.net/auth/callback"
      allow_pkce_without_secret = false
    }
    hermes = {
      name                      = "Hermes Dashboard"
      domain                    = "hermes.miruohotspring.net"
      redirect_uri              = "https://hermes.miruohotspring.net/auth/callback"
      allow_pkce_without_secret = true
    }
    cloud-drive = {
      name                      = "Cloud Drive"
      domain                    = "api-drive.miruohotspring.net"
      redirect_uri              = "https://api-drive.miruohotspring.net/v1/auth/callback"
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
  domain     = each.value.domain
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
    auth_type                        = "oidc"
    access_token_lifetime            = "10m"
    allow_pkce_without_client_secret = each.value.allow_pkce_without_secret
    grant_types                      = ["authorization_code_with_pkce", "refresh_tokens"]
    redirect_uris                    = [each.value.redirect_uri]
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
