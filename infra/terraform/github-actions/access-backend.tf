resource "aws_iam_role" "cloudflare_access_state" {
  name = "github-actions-k8s-home-cloudflare-access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = "repo:miruohotspring/k8s-home:ref:refs/heads/main"
          }
        }
      }
    ]
  })

  max_session_duration = 3600

  tags = {
    ManagedBy  = "terraform"
    Purpose    = "cloudflare-access-state"
    Repository = "miruohotspring/k8s-home"
  }
}

resource "aws_iam_role_policy" "cloudflare_access_state" {
  name = "cloudflare-access-state-only"
  role = aws_iam_role.cloudflare_access_state.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadCloudflareAccessStateBucketLocation"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation"]
        Resource = "arn:aws:s3:::web-app-template-tfstate-dev"
      },
      {
        Sid      = "ListOnlyCloudflareAccessState"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::web-app-template-tfstate-dev"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "platform/cloudflare-access/terraform.tfstate",
              "platform/cloudflare-access/terraform.tfstate.tflock",
            ]
          }
        }
      },
      {
        Sid      = "ReadWriteCloudflareAccessState"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "arn:aws:s3:::web-app-template-tfstate-dev/platform/cloudflare-access/terraform.tfstate"
      },
      {
        Sid      = "ManageCloudflareAccessStateLock"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "arn:aws:s3:::web-app-template-tfstate-dev/platform/cloudflare-access/terraform.tfstate.tflock"
      },
    ]
  })
}

output "cloudflare_access_state_role_arn" {
  description = "GitHub Actions role limited to the Cloudflare Access Terraform state object and lock."
  value       = aws_iam_role.cloudflare_access_state.arn
}
