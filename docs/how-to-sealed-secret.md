# How To: Create SealedSecret for Concourse Telegram Credentials

## 1. Install kubeseal (0.27.x recommended)

```bash
KUBESEAL_VERSION="0.27.0"
curl -sL "https://github.com/bitnami-labs/sealed-secrets/releases/download/v${KUBESEAL_VERSION}/kubeseal-${KUBESEAL_VERSION}-linux-amd64.tar.gz" \
  | tar -xz kubeseal && sudo install -m 755 kubeseal /usr/local/bin/
```

## 2. Create Secret YAML (`telegram-creds`, namespace: `concourse`)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: telegram-creds
  namespace: concourse
type: Opaque
stringData:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
```

Save as `telegram-creds-secret.yaml`.

## 3. Convert to SealedSecret

```bash
kubeseal --format yaml \
  --controller-namespace kube-system \
  --controller-name sealed-secrets-controller \
  < ./secrets/telegram-creds-secret.yaml \
  > ./infra/secrets/telegram-creds-sealed.yaml
```

## 4. Place under `k8s-home/infra/concourse/` and push

- Commit and push `k8s-home/infra/concourse/sealed-telegram-creds.yaml`.
- Argo CD will auto-apply it via the concourse Application.
- `bitnami.com/SealedSecret` is already included in the infra AppProject whitelist.

## 5. Inject vars into Concourse pipeline

```bash
# credentials.yml（.gitignore に追加済み）
telegram-creds:
  bot_token: YOUR_BOT_TOKEN
  chat_id: YOUR_CHAT_ID

fly -t home set-pipeline -p web-app-template \
  -c ci/pipeline.yml \
  -l credentials.yml
```
