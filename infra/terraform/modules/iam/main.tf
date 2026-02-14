resource "aws_iam_user" "k8s_image_pull" {
  name = var.user_name
  path = var.user_path
  tags = var.tags
}

resource "aws_iam_access_key" "k8s_image_pull" {
  user = aws_iam_user.k8s_image_pull.name
}

resource "aws_iam_user_policy" "ecr_pull" {
  name = "${var.user_name}-ecr-pull"
  user = aws_iam_user.k8s_image_pull.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
        ]
        Resource = "*"
      },
    ]
  })
}

