# m3usick 開発環境 Access 切替手順

本書は ADR ではない。ADR m3usick#69 は人間の申告と GitHub 上の merge 確認済み。実環境の操作・統合は親担当が調整する。Terraform の変数はすべて既定 false で、既定では新しいホストを保護しない。

## 必須の事前確認

- `app-m3usick-dev-users` の存在と必要なメンバー登録は別々に確認する。本人が Cloudflare Zero Trust > Access controls > Policies > Rule groups で専用グループを作成または確認し、必要なメンバーを GUI で登録・確認する。Terraform の名前検索はメンバー確認の代替にならない。メールは記録・出力しない。
- `m3usick-dev.pages.dev` と `m3usick-prod.pages.dev` は実際に確認した別プロジェクトの alias。dev の production alias と `*.m3usick-dev.pages.dev` の両方が保護対象。prod には dev Access を追加しない。空 dev project のまま、保護確認まで何も upload しない。
- Pages は Access 設定済み custom domain を追加できない。`dev.m3usick.com` の既存 DNS、Tunnel、サービス、復旧方法を先に確認し、空 dev Pages project に custom domain を登録してから custom host Access を適用する。ACME の `/.well-known/acme-challenge/*` を妨げない。DNS の自動変更に注意し、復旧の見通しがなければ停止。
- トークン、メンバー、state 全文、API の生応答、saved plan は公開しない。CI の token を取り出さない。現在の既存正当なローカル token は group と Pages の読み取りで 403、別の CI token は従来 root の credentialed plan に成功しているが、新規アプリの write 権限は未確認。

## 実行用の Terraform 切替

`infra/terraform/cloudflare-access` を正本とする。実行時は backend と lock が正しく設定された信頼できる CI で、state のバックアップと plan の機密保持を確保する。CI は repository variables `ENABLE_M3USICK_DEV_POLICY_DRAFT`、`ENABLE_M3USICK_PAGES_ACCESS_TRIAL`、`ENABLE_M3USICK_API_ACCESS`、`ENABLE_M3USICK_CUSTOM_HOST_ACCESS` を受け取り、未設定は false。作成済み資源の維持に必要な値は継続設定する。いずれか true の場合は M3 資源を target し、依存先を含む M3 以外の変更と削除・置換は拒否する。下記フラグは `terraform plan` およびその saved plan を承認後適用するための入力であり、手元の backend 無効 mock テストを実環境操作に使わない。

1. 空プロジェクトで通常 Access API の route を試す: `-var='enable_m3usick_dev_policy_draft=true' -var='enable_m3usick_pages_access_trial=true'`。専用 group lookup、allow/TOTP policy と dev alias、wildcard preview の二つの self-hosted app のみが対象。policy には専用 group のみを指定し、app は Google IdP のみ許可する。API で `pages.dev` への新規 app 作成が実際に受理され、各 URL に強制されるかは未検証である。一般的 API の public destination 記述だけで受理可能と断定しない。GUI が必須とも断定しない。既存の Pages native app と hostname が重複する場合は停止する。
2. plan の全 resource change を点検し、上記新規資源以外の変更は停止。ただし既知の launcher `landing_page_design` の `{}` → `null` のみ cosmetic drift として別途目視確認する。destroy/replacement、既存 SaaS/IdP/TOTP/組織/Launcher の他の変更、本番 host への変更は許さない。group が見つからない・権限不足・予定外の diff なら apply しない。
3. 親担当が saved plan を個別に適用、API の最小限の read-back で app、destinations、policy、IdP を照合し、空 deployment 状態のまま alias と代表的 preview の未認証拒否を検証する。apply が途中失敗したら成功済み資源が残り得るため state と API の対象だけを確認してから回復する。失敗を理由に保護されていないコンテンツを upload しない。直 API route が受理されない場合のみ、公式 Pages Known issues の native 手順を採用し、生成 app の重複を避け、Terraform への import と実効ポリシーを別途確定する。native が必須である証拠なく GUI の変更を先行しない。
4. 公開前に `-var='enable_m3usick_api_access=true'` を有効化して API ホストを先行保護する（専用 policy 必須）。Pages が custom domain を受け付けた後、前記フラグを維持し `-var='enable_m3usick_custom_host_access=true'` を追加して plan。`dev.m3usick.com` と `api-dev.m3usick.com` を一つの self-hosted app に接続する。OPTIONS のみ認証を bypass するため origin 側で厳密に Origin・method・header を検証する必要がある。未認証の実 API 本体は拒否する。新規 app は eager redirect cookie が既定で有効との公式仕様だが、provider v5.27 の schema には設定属性がない。実効値と二つの具体的 hostname への cookie 発行を実環境で検証し、更新後も確認する。
5. 保護と rollback の準備が確認できてから非機密 canary を投入し、Google + TOTP の許可メンバー、非メンバー、未認証を実ブラウザで検証する。空 project での応答だけでは実 deployment の保護を証明できない。

## 通信境界

`dev.m3usick.com` → `api-dev.m3usick.com` は同一サイトであり、Access の multi-host eager cookie とアプリ固有 host-only cookie の役割は別。`pages.dev` preview → `m3usick.com` API は cross-site なので、既存 `SameSite=Strict` のアプリ session cookie は送られない。preview に API CORS を全開にせず、SameSite も緩めない。API 連携を必要とする preview は別途設計・判断する。allowed Origin の preflight と credential 付き本体、別 Origin の拒否、認証なし本体の拒否を試験する。Access はアプリ自身の session cookie を発行しない。

## 一次資料

- https://developers.cloudflare.com/pages/platform/known-issues/
- https://developers.cloudflare.com/pages/configuration/preview-deployments/
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/
- https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/applications/methods/create/
- https://github.com/cloudflare/terraform-provider-cloudflare/blob/v5.27.0/docs/resources/zero_trust_access_application.md

mock-provider の test/validate は Terraform の構造と条件の検証であり、実際の provider 権限、Pages route、cookie、CORS、ログインの成功の証拠ではない。
