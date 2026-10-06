output "saas_clients" {
  description = "Cloudflare Access OIDC client credentials. They are intentionally sensitive and must not be logged or exported as CI artifacts."
  value = {
    for key, app in cloudflare_zero_trust_access_application.app : key => {
      client_id     = app.saas_app.client_id
      client_secret = app.saas_app.client_secret
    }
  }
  sensitive = true
}
