# ECR Token Refresh — systemd-timer

k3sコントロールプレーンノード（k8s-control-1: 192.168.1.101）上で動作するsystemd-timerにより、
ECR認証トークンを6時間ごとに自動更新する。

## 背景

旧構成（Kubernetes CronJob）からの移行。

| 項目 | 旧構成 | 新構成 |
|------|--------|--------|
| 実行環境 | kube-system CronJob | ホストsystemd-timer |
| AWS認証情報 | k8s-image-pull-credentials Secret | `/etc/ecr-token-refresh/credentials` |
| RBAC | ClusterRole + ServiceAccount | 不要（hostのkubeconfigを使用） |
| イメージ | amazon/aws-cli + bitnami/kubectl | ホストのaws-cli + kubectl |

## インストール手順

### 1. AWS認証情報ファイルの作成

```bash
sudo mkdir -p /etc/ecr-token-refresh
sudo tee /etc/ecr-token-refresh/credentials > /dev/null <<'EOF'
AWS_ACCESS_KEY_ID=<your_access_key_id>
AWS_SECRET_ACCESS_KEY=<your_secret_access_key>
EOF
sudo chmod 600 /etc/ecr-token-refresh/credentials
```

> **注意**: 既存の `k8s-image-pull-credentials` SecretからAWS認証情報を取得する場合:
> ```bash
> kubectl get secret k8s-image-pull-credentials -n kube-system \
>   -o go-template='{{index .data "access_key_id" | base64decode}}{{"\n"}}'
> kubectl get secret k8s-image-pull-credentials -n kube-system \
>   -o go-template='{{index .data "secret_access_key" | base64decode}}{{"\n"}}'
> ```

### 2. スクリプトの配置

```bash
sudo cp ecr-token-refresh.sh /usr/local/bin/ecr-token-refresh.sh
sudo chmod +x /usr/local/bin/ecr-token-refresh.sh
```

### 3. systemdユニットの配置と有効化

```bash
sudo cp ecr-token-refresh.service /etc/systemd/system/
sudo cp ecr-token-refresh.timer   /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now ecr-token-refresh.timer
```

### 4. 動作確認

```bash
# タイマー状態確認
systemctl status ecr-token-refresh.timer

# 即時実行でテスト
sudo systemctl start ecr-token-refresh.service

# ログ確認
journalctl -u ecr-token-refresh.service -f
```

## 削除された旧リソース

以下のKubernetesリソースはArgoCD pruneにより自動削除される:

- `kube-system/ecr-token-refresh` CronJob
- `kube-system/ecr-token-updater` ServiceAccount
- `ecr-token-updater` ClusterRole / ClusterRoleBinding
- `kube-system/k8s-image-pull-credentials` Secret（SealedSecret削除後）
- `example-dev/ecr-secret` Static SealedSecret（systemd-timerが動的に上書き）
