output "user_name" {
  description = "IAM user name"
  value       = aws_iam_user.k8s_image_pull.name
}

output "user_arn" {
  description = "IAM user ARN"
  value       = aws_iam_user.k8s_image_pull.arn
}

output "access_key_id" {
  description = "IAM access key ID"
  value       = aws_iam_access_key.k8s_image_pull.id
  sensitive   = true
}

output "secret_access_key" {
  description = "IAM secret access key"
  value       = aws_iam_access_key.k8s_image_pull.secret
  sensitive   = true
}

