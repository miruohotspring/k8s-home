terraform {
  required_version = ">= 1.14.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.7.0"
    }
  }

  backend "s3" {
    bucket       = "web-app-template-tfstate-dev"
    key          = "platform/google-identity/terraform.tfstate"
    region       = "ap-northeast-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "google" {
  project = var.gcp_project_id
}
