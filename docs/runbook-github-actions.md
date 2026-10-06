# GitHub Actions 移行・運用

## 管理範囲

Concourseのbuild/クラウド操作/GitOps更新をGitHub-hosted Linux runnerへ移す。ECR、Cloudflare、アプリTerraform state、Argo CDによる反映は維持。クラスタkubeconfigはGitHubに配置しない。人間向けAWS SSOとauthentikは変更しない。

- `gammaLaboratory/m3usick`: develop自動dev反映、main build、本番は手動。
- `miruohotspring/cloud-drive`: main検証→Terraform delete拒否→同じplan apply→build→D1 migrate→prod GitOps。
- `miruohotspring/web-app-template`: developの変更path別frontend/backend/infra検証、Terraform applyは手動。

## AWS federation

所有rootは `infra/terraform/github-actions`。共有OIDC provider・用途別5 rolesを管理する。backendは既存S3 bucket内の専用keyで、既存アプリstateを変更しない。rootのREADMEも参照。

GitHubの `GET /repos/{owner}/{repo}/actions/oidc/customization/sub` で **実際のsub_claim_prefix** を確認する。Cloud Driveはimmutable subjectを使用し、owner/repo名に数値IDが付く。従来形式の`repo:owner/repo`を全リポジトリに決め打ちしない。2026-10-06に確認した完全一致のsubjectをIAM trustへ設定済み。Environment subjectは許可しない。

AWSの長期access keyをActionsへコピーしない。ECR roleとTerraform roleを分け、対象branch/対象resourceのみ許可する。

## GitHub設定

共通repository variables:

- `CI_DEPLOY_ENABLED`: 初期値`false`。Concourse側writerをpause/drainしてから`true`にする。
- `AWS_REGION`, `ECR_REGISTRY`, `ECR_REPOSITORY`, `AWS_ECR_ROLE_ARN`
- Cloud Drive/templateのみ `AWS_TERRAFORM_ROLE_ARN`

Secretsは値を記録せず、元のKubernetes Secretと用途を示す。初回登録後はGitHub APIから名前/更新状態を読み戻して確認する。GitHubからsecret実値を取得できるとは扱わない。

- m3usick `GITOPS_DEPLOY_KEY` ← `concourse-main/concourse-github-ssh.private_key`
- Cloud Drive `GITOPS_DEPLOY_KEY` ← `cloud-drive-github-ssh-gitops.private_key`
- template `GITOPS_DEPLOY_KEY` ← `web-app-template-github-ssh-gitops.private_key`
- Cloud Drive/template `CLOUDFLARE_API_TOKEN` ← `concourse-cloudflare-creds.api_token`
- Cloud Drive `R2_STATE_ACCESS_KEY_ID`, `R2_STATE_SECRET_ACCESS_KEY` ← `cloud-drive-r2-state`
- Cloud Drive `DRIVE_D1_API_TOKEN` ← `cloud-drive-runtime.d1_api_token`
- template `TELEGRAM_BOT_TOKEN` ← `telegram-creds.bot_token`

追加variables: Cloud Driveの `DRIVE_D1_ACCOUNT_ID`, `DRIVE_D1_DATABASE_ID`、templateの `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_ZONE_ID`, `VITE_API_BASE_URL`, `TELEGRAM_CHAT_ID`。

移行では既存の**対象GitOpsリポジトリ専用write deploy key**を再利用。公開鍵が対象repoのdeploy keyと一致し、read_only=falseであることを検証した。汎用PATや個人のSSH鍵は使わない。ConcourseのSecret削除時にGitHub deploy key自体をrevokeしない。将来GitHub Appへ移す場合は新旧両者の動作確認後にrotationする。

## 安全な切替

1. `CI_DEPLOY_ENABLED=false`でworkflowをPR検証。secretをPRへ渡さない。
2. 現行GitOps commit/imageと実行中Concourse buildを記録。
3. workflowを既定branchへmergeし、安全モードの実行成功を確認。
4. 対象Concourse pipelineをpause。実行中buildの完了を確認する。pauseは実行中buildの停止ではない。
5. 対象repoだけ`CI_DEPLOY_ENABLED=true`へ変更し、読み戻す。
6. default branchから手動dispatchして、AWS OIDC、ECR publish、GitOps実commit、Argo Synced/Healthy、公開HTTP動作まで確認。Cloud DriveはD1 migrationを含め検証する。
7. ActionsとConcourse両方が同じGitOps/state/DBを書く状態にしない。

## 復旧

対象repoの`CI_DEPLOY_ENABLED=false`を設定し、実行中Actionsのapply/migrationが完了したことを確認してからConcourseをunpauseする。実行中applyを無闇にcancelしない。GitOpsの既知imageへ戻す場合もDB schemaの後方互換を確認する。image rollbackはD1 migration rollbackを意味しない。

## Concourse停止条件

3 pipelineの移行先が実実行成功し、手動経路も検証できるまではWeb/worker/PostgreSQLを停止しない。停止時はDB backupを権限0700の退避先へ取り、PVCと復旧用定義を保持する。Argoのreconcileで復活しないGitOps上の停止設定を行い、実リソースとメモリ使用を確認する。PVC/DNS/authentikアプリ/旧AWS access keyの削除は別承認とする。

## Concourseの停止設定と復旧

停止設定は `infra/concourse/values.yaml` の `web.replicas: 0` / `worker.replicas: 0` と、`infra/concourse/retired/postgresql.yaml` の `spec.replicas: 0`。Chart 20.0.1はPostgreSQLを1 replicaに固定しているため、既存values sourceに`path`を付けて同じStatefulSetだけを後順位sourceで上書きする。`postgresql.enabled`はtrueのままとし、接続Secret・ConfigMap・Serviceをpruneしない。

Argo CDのmulti-source仕様により、このStatefulSetの`RepeatedResourceWarning`は意図したもの。これ以外の重複や差分は許容しない。参照: `https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/`。停止状態でもApplicationと全17 resourcesを保持し、PVCはwhenScaled/whenDeletedともRetain。ConcourseのHTTP画面は停止に伴い利用できなくなる。DNS/ingress/authentik/旧credentialsは保持する。

2026-10-06の停止前backup: `/home/miruo/.hermes/backups/concourse-retirement-20261006T092935Z/`（directory 0700、files 0600）。pipeline定義3本、build一覧、workload/PVC定義、PostgreSQL custom-format dumpを保存。ネットワークを無効にした一時PostgreSQL 17.6へ実restoreし、61 tables / 3 pipelines / 79 buildsを確認。一時DBは削除済み。秘密値をGitへ登録しない。

復旧手順:

1. 対象GitHub repositoryの`CI_DEPLOY_ENABLED=false`を設定・読み戻し、実行中Actionsのapply/migration/GitOps書込みが終了したことを確認する。
2. `web.replicas` / `worker.replicas`を1へ戻し、Applicationのvalues sourceから`path: infra/concourse/retired`だけを外してPR mergeする。retired manifestは復旧時に参照されなくなる。Chartが同名PostgreSQLを1へ復元し、既存PVCを使う。
3. Argo同期後PostgreSQL、web、workerがReadyになったことを確認。pipelineはpausedのまま保持される。必要な対象だけ`fly -t home unpause-pipeline -p <name>`し、Actionsとの二重writerを避ける。
4. 通常復旧ではDB restore不要。PVC破損時のみ隔離したDBへdumpをrestoreして検証してから切り替える。稼働DBへ直接上書きrestoreしない。

Chart更新時はretired StatefulSetと当該版renderを比較する。退役中のChart更新を無闇に行わない。

## 料金確認

GitHub Actionsの予算はrepositoryでなくownerごと。2026-10-06のgammaLaboratory billing usageではActions netAmount=0を確認。個人ownerのbilling APIは現在のgh token scopeでは読めない（404/user scope不足）。無料枠残量や有料超過の無効化は未確認であり、無料を保証しない。必要最小限のrunner実行・短いartifact retentionを使い、移行後の実時間を確認する。
