resource "aws_iam_role" "google_identity_state" {
  name = "github-actions-k8s-home-google-identity"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
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
    }]
  })

  max_session_duration = 3600

  tags = {
    ManagedBy  = "terraform"
    Purpose    = "google-identity-state"
    Repository = "miruohotspring/k8s-home"
  }
}

resource "aws_iam_role_policy" "google_identity_state" {
  name = "google-identity-state-only"
  role = aws_iam_role.google_identity_state.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadGoogleIdentityStateBucketLocation"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation"]
        Resource = "arn:aws:s3:::web-app-template-tfstate-dev"
      },
      {
        Sid      = "ListOnlyGoogleIdentityState"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::web-app-template-tfstate-dev"
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "platform/google-identity/terraform.tfstate",
              "platform/google-identity/terraform.tfstate.tflock",
            ]
          }
        }
      },
      {
        Sid      = "ReadWriteGoogleIdentityState"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "arn:aws:s3:::web-app-template-tfstate-dev/platform/google-identity/terraform.tfstate"
      },
      {
        Sid      = "ManageGoogleIdentityStateLock"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "arn:aws:s3:::web-app-template-tfstate-dev/platform/google-identity/terraform.tfstate.tflock"
      },
    ]
  })
}

output "google_identity_state_role_arn" {
  description = "GitHub Actions role limited to the Google identity Terraform state and lock."
  value       = aws_iam_role.google_identity_state.arn
}
