mock_provider "cloudflare" {
  mock_data "cloudflare_zero_trust_access_group" {
    defaults = { id = "test-group-id" }
  }
}

variables {
  cloudflare_account_id      = "test-account"
  google_oauth_client_id     = "test-client"
  google_oauth_client_secret = "test-secret"
}

run "disabled_by_default" {
  command = plan
  assert {
    condition     = length(cloudflare_zero_trust_access_policy.m3usick_dev) == 0
    error_message = "The draft policy must not exist by default."
  }
}

run "enabled_policy_uses_gui_group_and_totp" {
  command = plan
  variables { enable_m3usick_dev_policy_draft = true }
  assert {
    condition     = data.cloudflare_zero_trust_access_group.m3usick_dev[0].filter.name == "app-m3usick-dev-users"
    error_message = "The dedicated GUI-managed group must be looked up."
  }
  assert {
    condition     = one(cloudflare_zero_trust_access_policy.m3usick_dev[0].include).group.id == "test-group-id" && cloudflare_zero_trust_access_policy.m3usick_dev[0].decision == "allow"
    error_message = "Only the dedicated group must be allowed."
  }
  assert {
    condition     = length(cloudflare_zero_trust_access_policy.m3usick_dev[0].mfa_config.allowed_authenticators) == 1 && contains(cloudflare_zero_trust_access_policy.m3usick_dev[0].mfa_config.allowed_authenticators, "totp") && cloudflare_zero_trust_access_policy.m3usick_dev[0].mfa_config.mfa_disabled == false
    error_message = "The draft must require TOTP."
  }
}
