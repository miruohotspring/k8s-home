# The enrollment portal needs its own Access application; SaaS tiles alone do
# not enable it. Limit portal login to the existing application allowlists.
resource "cloudflare_zero_trust_access_application" "launcher" {
  account_id                = var.cloudflare_account_id
  name                      = "App Launcher"
  type                      = "app_launcher"
  domain                    = cloudflare_zero_trust_organization.this.auth_domain
  allowed_idps              = [var.email_otp_identity_provider_id]
  auto_redirect_to_identity = true
  session_duration          = "720h"

  policies = [{
    id         = cloudflare_zero_trust_access_policy.launcher_enrollment.id
    precedence = 1
  }]

  lifecycle {
    prevent_destroy = true
    # The API materializes a default launcher title even when no custom design
    # is configured. Ignore that provider normalization, not the auth settings.
    ignore_changes = [landing_page_design]
  }
}

resource "cloudflare_zero_trust_access_policy" "launcher_enrollment" {
  account_id = var.cloudflare_account_id
  name       = var.launcher_mfa_enrollment_mode ? "Allow approved users to enroll MFA" : "Allow approved users with TOTP"
  decision   = "allow"

  include = [
    for email in toset(flatten([
      for app in keys(local.apps) : tolist(var.allowed_emails[app])
      ])) : {
      email = { email = email }
    }
  ]

  session_duration = "720h"

  # The steady state makes the launcher the Access session entrypoint, so a
  # launcher session proves the same TOTP requirement as every SaaS app. A
  # short, explicit manual apply can temporarily open MFA enrollment; all SaaS
  # applications remain TOTP-protected during that window.
  mfa_config = {
    allowed_authenticators = ["totp"]
    mfa_disabled           = var.launcher_mfa_enrollment_mode
    session_duration       = "720h"
  }
}
