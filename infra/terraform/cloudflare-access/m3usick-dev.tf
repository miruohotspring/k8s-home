# Dedicated GUI-managed group and reusable dev access policy.
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
  description = "Enable the dedicated dev group lookup and policy; does not by itself protect hostnames."
  type        = bool
  default     = false
}

variable "enable_m3usick_api_access" {
  type        = bool
  default     = false
  description = "Protect the API hostname before it becomes public."
  validation {
    condition     = !var.enable_m3usick_api_access || var.enable_m3usick_dev_policy_draft
    error_message = "The dedicated dev policy must be enabled for API Access."
  }
}

variable "enable_m3usick_custom_host_access" {
  type        = bool
  default     = false
  description = "Enable only after Pages has accepted dev.m3usick.com as a custom domain."
  validation {
    condition     = !var.enable_m3usick_custom_host_access || (var.enable_m3usick_dev_policy_draft && var.enable_m3usick_api_access)
    error_message = "The dedicated dev policy and API Access must be enabled for custom-host Access."
  }
}

# Attach the already registered Pages custom hostname only after Pages accepts
# it without an Access app. Keep both concrete hosts together for eager cookies.
resource "cloudflare_zero_trust_access_application" "m3usick_dev" {
  count                     = var.enable_m3usick_api_access ? 1 : 0
  account_id                = var.cloudflare_account_id
  name                      = "m3usick dev"
  type                      = "self_hosted"
  domain                    = "api-dev.m3usick.com"
  destinations              = concat([{ type = "public", uri = "api-dev.m3usick.com" }], var.enable_m3usick_custom_host_access ? [{ type = "public", uri = "dev.m3usick.com" }] : [])
  allowed_idps              = [cloudflare_zero_trust_access_identity_provider.google.id]
  auto_redirect_to_identity = true
  options_preflight_bypass  = true
  session_duration          = "720h"
  policies                  = [{ id = cloudflare_zero_trust_access_policy.m3usick_dev[0].id, precedence = 1 }]
}

# Experimental opt-in for an EMPTY Pages project only. API support for direct
# pages.dev hostname creation is unproven; never deploy content until verified.
variable "enable_m3usick_pages_access_trial" {
  type        = bool
  default     = false
  description = "Empty-project-only trial; requires the dedicated dev policy and verified hostname ownership."
  validation {
    condition     = !var.enable_m3usick_pages_access_trial || var.enable_m3usick_dev_policy_draft
    error_message = "The dedicated dev policy must be enabled for the Pages trial."
  }
}

resource "cloudflare_zero_trust_access_application" "m3usick_pages_trial" {
  for_each = var.enable_m3usick_pages_access_trial ? {
    production = "m3usick-dev.pages.dev"
    previews   = "*.m3usick-dev.pages.dev"
  } : {}
  account_id                = var.cloudflare_account_id
  name                      = "m3usick dev pages ${each.key}"
  type                      = "self_hosted"
  domain                    = each.value
  destinations              = [{ type = "public", uri = each.value }]
  allowed_idps              = [cloudflare_zero_trust_access_identity_provider.google.id]
  auto_redirect_to_identity = true
  session_duration          = "720h"
  policies                  = [{ id = cloudflare_zero_trust_access_policy.m3usick_dev[0].id, precedence = 1 }]
}
