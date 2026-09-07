# web-app-example GitOps 環境別ディレクトリ化 設計・実装記録

Status: **実装・live検証済み**

## 目的

`web-app-example-git-ops` のdev manifestを環境別directoryへ分離し、将来stg/prdを追加するときの変更範囲を局所化する。当面はdevのみを運用する。

frontendはCloudflare Pages、home-k8sはbackend APIのみを管理する。

## Repository責務

### `miruohotspring/k8s-home`

- Argo CD root application、AppProject、repository credential、platform SealedSecretを管理する。
- `apps/example/application.yaml`から`web-app-example-git-ops/infra/argocd`を再帰的に読み込む。

### `miruohotspring/web-app-example-git-ops`

- backend APIのArgo CD Application、Helm chart、環境別values、SealedSecretを管理する。
- 現在のdev layout:

```text
infra/
  argocd/
    example-api-dev-app.yaml
    example-secrets-dev-app.yaml
  helm/
    example-api/
      Chart.yaml
      values.yaml
      envs/
        dev.yaml
      templates/
  k8s-secrets/
    envs/
      dev/
        api-credentials-sealed.yaml
        google-oauth-secret-sealed.yaml
```

### `miruohotspring/web-app-template`

- application source、Concourse pipeline、Terraformを管理する。
- Concourseはbackend imageをbuild/pushし、次のdev valuesだけを更新する。

```text
infra/helm/example-api/envs/dev.yaml
```

## Argo CD構成

現在のApplication:

```text
example-apps
  source: web-app-example-git-ops/infra/argocd

example-api-dev
  source: web-app-example-git-ops/infra/helm/example-api
  values: values.yaml + envs/dev.yaml
  destination: example-dev

example-secrets-dev
  source: web-app-example-git-ops/infra/k8s-secrets/envs/dev
  destination: example-dev
```

3 Applicationともliveで`Synced/Healthy`を確認済み。

## 将来のstg/prd追加

環境を追加するときは同じ形で明示的に増やす。

```text
infra/argocd/
  example-api-stg-app.yaml
  example-api-prd-app.yaml
  example-secrets-stg-app.yaml
  example-secrets-prd-app.yaml

infra/helm/example-api/envs/
  stg.yaml
  prd.yaml

infra/k8s-secrets/envs/
  stg/
  prd/
```

namespace、Argo CD Application、values、SealedSecretを環境ごとに分離する。dev buildをprodへ直接反映せず、promote jobまたはreviewed PRでstg/prdのimage tagを更新する。

## Invariants

- Application manifestのfilenameは変更できるが、既存`metadata.name`は不用意に変更しない。
- SealedSecretの`metadata.namespace`と`spec.template.metadata.namespace`は対象環境namespaceに一致させる。
- Concourseの自動更新対象はdevだけにする。
- frontendのKubernetes workloadを再導入しない。
- environment directoryを移動した場合はConcourseの更新先pathも同時に変更する。

## Verification

```bash
# Argo CD
kubectl -n argocd get app example-apps example-api-dev example-secrets-dev

# Backend runtime
kubectl -n example-dev get deploy,svc,ingress,sealedsecret,secret

# Concourse
fly -t home check-resource -r web-app-template/gitops-repo
fly -t home jobs -p web-app-template
```

Expected:

- `example-apps`、`example-api-dev`、`example-secrets-dev`が`Synced/Healthy`
- `example-dev`のbackend API PodがReady
- Concourseが`infra/helm/example-api/envs/dev.yaml`だけを更新する
