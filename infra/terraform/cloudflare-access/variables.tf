variable "cloudflare_account_id" {
  description = "Cloudflare account ID that owns the existing Zero Trust organization."
  type        = string
}

variable "email_otp_identity_provider_id" {
  description = "Existing Cloudflare One-time PIN identity provider ID. This root only references it."
  type        = string
  default     = "690dc63b-9a1c-4f6c-8aac-98da9eef09db"
}

variable "allowed_emails" {
  description = "Sensitive per-application email allowlists keyed by argocd, hermes, and cloud-drive."
  type        = map(set(string))
  sensitive   = true
}
