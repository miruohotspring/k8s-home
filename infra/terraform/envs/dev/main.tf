terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "k8s_image_pull_iam" {
  source = "../../modules/iam"

  user_name = "k8s-image-pull"
  user_path = "/service/"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "k8s-image-pull-ecr"
  }
}

output "k8s_image_pull_access_key_id" {
  description = "Kubernetes image pull IAM access key ID"
  value       = module.k8s_image_pull_iam.access_key_id
  sensitive   = true
}

output "k8s_image_pull_secret_access_key" {
  description = "Kubernetes image pull IAM secret access key"
  value       = module.k8s_image_pull_iam.secret_access_key
  sensitive   = true
}

