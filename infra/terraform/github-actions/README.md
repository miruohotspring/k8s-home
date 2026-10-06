# GitHub Actions AWS federation

共有OIDC providerと5つの用途別roleを管理する専用Terraform root。アプリ既存state・resource addressは変更しない。

- backend: 既存S3 bucket `web-app-template-tfstate-dev` 内の専用key `platform/github-actions/terraform.tfstate`。既存templateのstate keyとは別。templateを退役してもこのbucketを削除しない。S3 lockfileで排他。
- ECR roleは対象repositoryのpush/pullのみ。Terraform roleは対象ECR/IAM/DynamoDB/stateの管理APIに限定。
- trustは`aud=sts.amazonaws.com`とrepository/branchの完全一致。PR、任意branch、Environment subjectは許可しない。
- Cloud Drive既存Concourse IAM policy/attachmentとtemplate既存IAM userは移行中維持。旧資格情報削除は別作業。
- 新しいAWSアクセスキーを作成しない。人間のAWS SSO設定とは独立。

管理者の既存認証で`terraform init`、`terraform plan -out=<安全なpath>`。変更がこのrootの新規資源のみであることを確認後、同じplanをapplyする。AWS readbackとno-op planで確認する。

構成contract: repo rootから `python3 scripts/test-github-actions-iam.py`。
