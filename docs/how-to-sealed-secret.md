# How To: Create SealedSecret for Concourse Pipeline

### 前提
- k8s-homeがセットアップ済み
- アプリケーションのリポジトリに`pipeline.yml`を作成済み

## 1. Install kubeseal (0.27.x recommended)

```bash
KUBESEAL_VERSION="0.27.0"
curl -sL "https://github.com/bitnami-labs/sealed-secrets/releases/download/v${KUBESEAL_VERSION}/kubeseal-${KUBESEAL_VERSION}-linux-amd64.tar.gz" \
  | tar -xz kubeseal && sudo install -m 755 kubeseal /usr/local/bin/
```

## 2. Create Secret YAML

- Create `*-secret.yaml` file in `secrets/` directory
- This file will be git ignored

### `secrets/your-credential-name-secret.yaml`
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: your-credential-name
  namespace: concourse
type: Opaque
stringData:
  some_id: "SOME_ID_VALUE"
  some_secret_key: "SOME_SECRET_KEY_VALUE"
```

## 3. Convert to SealedSecret

- `kubeseal`コマンドを使用して、sealed.yamlをinfra/配下の各アプリケーションディレクトリに配置します

```bash
kubeseal --format yaml \
  --controller-namespace kube-system \
  --controller-name sealed-secrets-controller \
  < ./secrets/your-credential-name-secret.yaml \
  > ./infra/{application}/your-credential-name-sealed.yaml
```

## 4. Apply to Concourse Application

- `git commit` and `git push`
- Argo CD will auto-apply it via the concourse Application.

## 5. Inject vars into Concourse pipeline

Move to your application repository. In your `pipeline.yml`,

```yaml
params:
  SOME_ID: ((your-credential-name.some_id))
  SOME_SECRET_KEY: ((telegram-creds.some_secret_key))
```

Finally, set pipeline:

```bash
fly -t home set-pipeline -p web-app-template -c ci/pipeline.yml
```
