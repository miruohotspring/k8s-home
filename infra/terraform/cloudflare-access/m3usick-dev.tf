# Unattached draft only. Enabling this does not protect any hostname.
data "cloudflare_zero_trust_access_group" "m3usick_dev" {
  count      = var.enable_m3usick_dev_policy_draft ? 1 : 0
  account_id = var.cloudflare_account_id
  filter = {
    name = "app-m3usick-dev-users"
  }
}

resource "cloudflare_zero_trust_access_policy" "m3usick_dev" {
  count      = var.enable_m3usick_dev_policy_draft ? 1 : 0
  account_id = var.cloudflare_account_id
  name       = "Allow m3usick dev via Google with TOTP"
  decision   = "allow"
  depends_on = [cloudflare_zero_trust_organization.this]

  include = [{
    group = { id = data.cloudflare_zero_trust_access_group.m3usick_dev[0].id }
  }]
  session_duration = "720h"
  mfa_config = {
    allowed_authenticators = ["totp"]
    mfa_disabled           = false
    session_duration       = "720h"
  }
}

variable "enable_m3usick_dev_policy_draft" {
  description = "Draft plan only: create an unattached m3usick dev policy. Do not apply before the reviewed cutover plan."
  type        = bool
  default     = false
}
