# 共有 Cloudflare Tunnel の冗長化と m3usick API 経路計画

## 承認境界

これは提案であり、適用・経路作成済みを意味しません。`infra/cloudflared` は全 Tunnel アプリが共有し、Argo CD が `main` を自動同期します。**この変更の merge / apply は全利用アプリに影響する本番変更です。利用者の明示的な本番承認までは push、merge、apply、手動 sync を行いません。** PR の作成も別途判断します。既存 Tunnel 経路、DNS、Access はこの変更では編集しません。

## 変更内容と限界

- cloudflared を 2 replicas にし、RollingUpdate は `maxUnavailable: 0`、`maxSurge: 1`。hostname ごとの `maxSkew: 1` / `DoNotSchedule` で分散を試みます。必須 pod anti-affinity は使わず、2 ノード上でも surge Pod を置ける設計です。
- PDB は `minAvailable: 1`。これは eviction API による自発的な退避を制限するもので、ノード障害や Deployment rollout を防ぐ保証ではありません。rollout は Deployment strategy が制御します。
- 2 台は同一物理 Proxmox 上の VM であり、物理ホスト障害に対する HA ではありません。片ノード停止時に 2 replica 全てを直ちに再配置できる保証もありません。readiness は Tunnel 全利用アプリの正常性の証明ではなく、既存接続も rollout や障害時に切れる可能性があります。
- 通常時の connector requests 合計は 100m CPU / 128Mi memory、rollout の最大 3 Pod では 150m / 192Mi です。limits は各 200m / 256Mi。これは予約量であり実使用量や他 workload の余裕を示しません。承認前に両 eligible node の allocatable、既存 requests、Pod 数、taint と空き容量を確認し、surge を収容できない場合は保留します。

## 将来の新 API 経路（別作業、未適用）

| 公開 hostname | Tunnel の直接 origin 候補 |
| --- | --- |
| `api-dev.m3usick.com` | `http://m3usick-web.m3usick-dev.svc.cluster.local:80` |
| `api.m3usick.com` | `http://m3usick-web.m3usick-prod.svc.cluster.local:80` |

既存 ClusterIP Service の port 80 に直接接続し、退役済み ingress を経由しません。Service 名、port、endpoint、ルーティング優先順位を実施直前に再確認します。他の既存 Tunnel 経路は全て維持し、全 ingress の移行は対象外です。新しい公開 hostname の Tunnel 設定、DNS、および Cloudflare Access の認証方式・対象・例外のレビューはそれぞれ別の明示承認後の操作です。ブラウザの API 呼び出しや CORS、cookie、Access の相互作用と認可を dev で実検証し、本番経路に進むか別途判断します。DNS や Access が完成する前に公開しません。

Pages の専用 Edit token が未準備であり、Cloudflare 上の Pages / DNS / Access 作業は保留です。`API_SPLIT_DEV_READY` と `PAGES_DEPLOY_ENABLED` も未設定のため、準備不足を隠して有効化しません。これらの gate は connector 冗長化の承認とは別です。

## 承認後の rollout / 検証

1. 対象 revision と render 差分をレビューし、共有 Tunnel 全アプリの影響、担当者、監視、復旧判断、切り戻し先、surge capacity を確認する。`kubectl kustomize infra/cloudflared` と `python3 -m unittest discover -s scripts -p 'test_cloudflared_ha.py' -v` を実行する（依存は `scripts/requirements-cloudflared-test.txt`）。
2. 利用者から本番変更の明示承認を得てから、承認済み GitOps 手順で merge する。Argo 自動同期により反映されるため、手動 apply や rollout restart で GitOps を迂回しない。
3. Argo の対象 revision と Synced/Healthy、Deployment の rollout、Pod の Ready と配置、PDB を確認する。例: `kubectl -n cloudflared rollout status deployment/cloudflared --timeout=180s`、`kubectl -n cloudflared get pods -l app=cloudflared -o wide`、`kubectl -n cloudflared get pdb cloudflared`。2 Pod が異なる hostname 上で Ready であることを確認する。Pending や接続不良なら原因を調査し、無理に続行しない。
4. 共有 Tunnel の代表的な既存アプリの外部アクセスと認証を実確認する。必要な監視・ログを確認し、secret や token 値を記録しない。readiness と Argo Healthy だけでは公開経路の正常性を証明できない。

## 失敗時と rollback

影響が出たら後続作業を停止し、影響範囲と Argo / Pod / scheduling 状態を記録する。承認された運用者が変更 commit を Git 上で revert して `main` へ戻し、Argo の自動同期と rollout 完了、元の 1 replica Ready、既存の代表経路の復旧を確認する。PDB は revert で削除される。自動同期が失敗した場合は原因を確認し、別途承認された復旧手順を選ぶ。手動 scale、apply、force sync は GitOps と競合し得るため代替手段として黙って使わない。新しい API 経路を別途作成した後は、その経路、DNS、Access の切り戻しをそれぞれの承認済み変更単位で行い、既存経路を削除しない。

旧 `docs/cloudflared-readiness-runbook.md` の「常に 1 Pod」と restart 例はこの提案の適用後の検証には使わず、本計画の手順を優先します。
