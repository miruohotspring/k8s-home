variable "user_name" {
  description = "IAM user name for Kubernetes image pull"
  type        = string
}

variable "user_path" {
  description = "IAM user path"
  type        = string
  default     = "/service/"
}

variable "ecr_repository_arns" {
  description = "List of ECR repository ARNs"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to IAM resources"
  type        = map(string)
  default     = {}
}

