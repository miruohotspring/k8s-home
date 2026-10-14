variable "cloudflare_account_id" {
  description = "Cloudflare account ID that owns the existing Zero Trust organization."
  type        = string
}

variable "google_oauth_client_id" {
  description = "Google OAuth client ID used only by the Cloudflare Access identity provider."
  type        = string
  sensitive   = true
}

variable "google_oauth_client_secret" {
  description = "Google OAuth client secret used only by the Cloudflare Access identity provider."
  type        = string
  sensitive   = true
}
