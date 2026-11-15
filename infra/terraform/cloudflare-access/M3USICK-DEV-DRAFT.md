# m3usick 開発環境 Access 実施案（未承認）

**これは ADR ではなく、検討中の作業案です。ADR 本文は未レビューであり、必ず人間のレビュー・承認が必要です。承認前に Access 設定、グループ作成、DNS、Tunnel、Pages 公開設定を変更しません。** 既存 dev/prod 配信は維持します。

## 今回の Terraform の範囲

`enable_m3usick_dev_policy_draft` は既定 false。true の場合のみ `app-m3usick-dev-users` を名前で参照し、専用グループを allow とする独立した再利用ポリシーを plan します。TOTP 必須、セッション 720h は既存方針に合わせた案です。**このポリシーはどのアプリにも接続しておらず、ホストを保護しません。** Google のみに制限する設定は将来のアプリ側で必要です。グループ本体やメンバーを Terraform で作成・管理しません。既存グループ、Launcher、組織、既存 SaaS アプリを変更しません。明示的な人間の承認と以下の全ゲートが整うまで true による apply 禁止。

## 未決定事項・必要な入力

- `m3usick-dev` の Pages プロジェクトから **実際の** production alias を取得する。プロジェクト名から仮定しない。preview の wildcard はその実 alias から特定する。値は未取得で、架空値を Terraform に与えない。prod 側は対象外。
- グループはユーザー本人が Cloudflare GUI の Access controls → Policies → Rule groups で `app-m3usick-dev-users` を新設し、メンバーを登録・管理する。存在と必要なメンバー登録を本人が確認するまで apply 禁止。Terraform のデータ参照はグループの存在確認にすぎず、適切なメンバー登録の証明にはならない。メールアドレスは Git やログに書かない。
- 対象は `dev.m3usick.com`、`api-dev.m3usick.com`、実際の Pages production alias とすべての preview（ハッシュ/ブランチ alias）。Pages の preview Access 有効化だけでは production alias と custom domain を保護しない。公式 Known issues は production alias と wildcard preview の別 Access 設定、custom domain の別途保護を指示する。一方、Pages native が作る Access アプリと Terraform の二重所有を避けるため、生成後のアプリ ID・host・policy の読み戻しと管理主体/import 手順の確認まで実装未確定。競合する重複リソースを作らない。
- `dev.m3usick.com` は、Access 未設定で Pages custom domain に追加してから Access を設定する必要がある。既存 dev DNS の維持と切戻しを保証できるまでは追加しない。空 project でも公開の可能性があるため upload しない。

## 空 project での保護順序（未実施、要人間承認）

1. 実 alias、専用グループとメンバー、現在の dev DNS/Tunnel と復旧手順を確認し、deployment と upload を停止する。Pages の custom domain 手順では Cloudflare zone の CNAME が確認後に自動追加されるため、既存 DNS への影響を未確認のまま実行しない。
2. 空の `m3usick-dev` で、Pages > Settings > General > Enable access policy を選ぶ。生成された preview policy の Manage > Access > Applications > 対象アプリ > Configure で Public hostname の Subdomain の `*` を除去し、必要なら名前を変えて Save。Pages > Settings > General に戻り Enable access policy を再選択する。公式手順に従い production alias 用と `*.<実 alias>` preview 用の 2 アプリを確認する。途中で preview が未保護となるので、この全工程中に upload しない。
3. 2 アプリの実際の hostname、policy、IdP、MFA、session を読み戻し、Google のみ・専用グループ・TOTP・720h の承認済み方針と一致させる。初期 policy がその方針に一致するとは仮定しない。両方を個別に検証する。
4. `dev.m3usick.com` に既存 Access がないことを確認し、空 Pages project に custom domain として追加、証明書と DNS を読み戻す。既存 dev 配信の維持・復旧を確保できない場合は追加前に停止。既存 Access を外してよいという意味ではない。ACME 検証の経路を確保し、全リクエストを bypass しない。
5. 登録後 custom domain に self-hosted Access を設定し、API も保護する。多 hostname アプリと eager cookie の組合せは候補であり、Pages 側アプリの hostname と重複させない。upload 前に設定・read-back と各入口の未認証拒否を可能な範囲で実証する。空 project では実 deployment の配信、非メンバーと許可メンバーの認証、cookie/CORS を完全に証明できない。初回 upload の可否と非機密 canary を人間が別途承認し、upload 後にそれらを実証する。失敗時は停止し、承認済み復旧手順だけを用いる。

## Pages native と Terraform の所有権

- Cloudflare は production alias と preview 両方の保護に上記の Pages native GUI 手順を示している。provider v5.27.0 の `cloudflare_pages_project` schema には native Access 有効化の属性がない。一方、通常の `cloudflare_zero_trust_access_application` には domain/destinations と policy 参照があるが、第三者所有の `pages.dev` を通常 API だけで新規保護できるとは確認できない。GUI 不要とは断定せず、未公開 API は使わない。
- GUI 作成後は Access API の `GET /accounts/{account_id}/access/apps` と `GET /accounts/{account_id}/access/apps/{app_id}` および policy read-back で、実 app ID・hostname・policy・IdP・MFA・session を照合する。ページネーションを考慮し、メール、token、生レスポンスをログへ出さない。hostname の重複所有はしない。Terraform 管理へ移す場合、実物に一致する resource と state backup を準備し、承認後に provider 公式の `terraform import <resource_address> 'accounts/<account_id>/<app_id>'` を app ごとに実行し、差分をレビューする。import は state を変更するため今は実行禁止。import 後に Pages native を再操作した際の挙動は未確認。
- v5.27.0 の application schema に multi-domain destinations と `options_preflight_bypass` はあるが、eager redirect cookie の設定属性は見当たらない。公式文書では新規 app の eager cookie は既定で有効だが、生成された app の実効値や Terraform 更新時の保持は未検証。候補として GUI の Access controls > Applications > 対象 Edit > Advanced settings > Cookie settings > Eager redirect cookie を確認し、実 browser と read-back で検証する。wildcard hostname には事前発行されない。
- フロントと API を同一 self-hosted アプリの具体的 hostname と eager redirect にまとめることは**候補**であり、動作や Pages native との競合は未検証。wildcard hostname は eager cookie の事前発行対象にならず、フロントのログインだけで API 用 cookie があると仮定しない。API hostname への明示的なブラウザ訪問も代替候補として検証する。
- OPTIONS は Access に cookie が届かないため、候補は OPTIONS のみ origin へ bypass し、origin が厳密な Origin・method・header を検証する方法。実際の API リクエストに bypass を与えず、認証なしの本体を拒否する。`credentials: include`、正確な許可 Origin、credentials の応答を実環境で検証する。`dev.m3usick.com` → `api-dev.m3usick.com` は同一サイトで host-only cookie を使える一方、`pages.dev` preview → API は cross-site で `SameSite=Strict` の `m3appsession` を送れない。Access eager cookie はアプリ自身の session cookie を発行・置換しない。preview に API CORS を無差別開放したり SameSite を弱めたりせず、API 連携を必要とする preview の正式な取扱いを別途決定する。

## 適用前 plan の手順・ゲート

1. 人間が日本語 ADR と本案をレビュー・承認。ユーザーが専用グループとメンバー登録を確認。実 alias と Pages native 所有権、app の構成、CORS、既存アクセス維持・復旧順序を確定する。別途、変更対象と適用実行を承認する。
2. 親担当が確認した現 main の credentialed baseline plan は 0 add / 1 change / 0 destroy、唯一 `launcher.landing_page_design` の `{}` → `null` cosmetic drift。既存 root・グループ・IdP の read は成功しているが、これを新規 Pages/Access 操作の書込権限の証明にはしない。以降の plan でも同差分とその他の想定外差分を精査し、全 ignore は禁止。
3. 現 CI は main の手動 plan/apply のみで、この draft 変数を指定する入力はない。draft の real plan は未実行。信頼できる環境で権限・state lock・機密保護を確保した別途レビュー済みの read-only plan 経路を用意するか、明示的にレビューした CI 変更後に実施する。CI の token 値を取得しない。ローカル既存 token の 403 は CI token の権限不足を意味しない。
4. draft 変数 true での plan は独立ポリシーの作成だけを示すはずであり、まだ実際の認証設定の全体 plan ではない。後続のアプリ・Pages native 管理案と実 alias を反映した完全な plan が必要。secret を出力せず、saved plan や state は機密扱い。plan の全 create/update/delete/replace、権限、ホスト、ポリシー、既存 baseline 差分を人間が確認し、想定外差分は停止。現 CI の delete/replace 防止だけでは十分ではない。
5. 明示承認後の個別適用に限り、対象と順番を再検証し、都度正確な read-back を行う。旧 dev Tunnel と本番 `m3usick.com` / `api.m3usick.com` は変更しない。失敗時に旧 dev 配信へ戻す具体的手順も事前承認する。

## 切替後に必要な実証（現時点では未実施）

- 正規メンバーは Google + TOTP で各対象にアクセスでき、非メンバー・未認証は拒否。実 production alias、ハッシュ preview、branch preview、custom domain、API の全てを確認する。
- browser の新規プロファイルで frontend → API の cookie 設定・送信とログイン連携を確認する。cookie 値やトークンは採取しない。許可 Origin の preflight と credential 付き本体の成功、別 Origin の拒否、未認証 API 本体の拒否を確認する。CLI/自動処理は別途認証経路を設計する。
- 外部から各 hostname の応答と想定外公開がないこと、既存 dev/prod の動作維持、Cloudflare のアプリ/ポリシーと state の所有関係を照合する。失敗時は承認した復旧順で戻し、再度読み戻す。

## 一次資料

- https://developers.cloudflare.com/pages/platform/known-issues/
- https://developers.cloudflare.com/pages/configuration/preview-deployments/
- https://developers.cloudflare.com/pages/configuration/custom-domains/
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/cors/
- https://github.com/cloudflare/terraform-provider-cloudflare/blob/v5.27.0/docs/resources/zero_trust_access_application.md

ローカルの mock-provider テストは Terraform の条件と policy 形状のみを確認し、Cloudflare の実権限、Pages、ブラウザ、CORS、ユーザーのログイン成功を証明しません。
