# The enrollment portal needs its own Access application; SaaS tiles alone do
# not enable it. Limit portal login to the existing application allowlists.
resource "cloudflare_zero_trust_access_application" "launcher" {
  account_id       = var.cloudflare_account_id
  name             = "Access App Launcher"
  type             = "app_launcher"
  domain           = cloudflare_zero_trust_organization.this.auth_domain
  allowed_idps     = [var.email_otp_identity_provider_id]
  session_duration = "720h"

  policies = [{
    id         = cloudflare_zero_trust_access_policy.launcher_enrollment.id
    precedence = 1
  }]

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_zero_trust_access_policy" "launcher_enrollment" {
  account_id = var.cloudflare_account_id
  name       = "Allow approved users to enroll MFA"
  decision   = "allow"

  include = [
    for email in toset(flatten([
      for app in keys(local.apps) : tolist(var.allowed_emails[app])
      ])) : {
      email = { email = email }
    }
  ]

  session_duration = "720h"

  # Users must reach enrollment before they have a TOTP device. This policy is
  # attached ONLY to the launcher; all SaaS applications keep mandatory TOTP.
  mfa_config = {
    mfa_disabled = true
  }
}
