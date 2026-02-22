# Concourse Pipeline 用 SealedSecret の作り方

このドキュメントでは、Concourse Pipeline で使う機密情報（ID や Secret Key など）を、安全に Kubernetes 上で管理する方法を解説します。

---

## 🔰 まず「SealedSecret」とは？

通常、Kubernetes で機密情報は `Secret` というリソースで管理します。

しかし…

* ❌ Secret をそのまま Git にコミットすると危険
* ❌ チーム開発では平文管理はNG

そこで登場するのが **SealedSecret** です。

## SealedSecret の仕組み

```
Secret（平文）
    ↓ kubeseal で暗号化（公開鍵を使用）
SealedSecret（安全にGit管理可能）
    ↓ Argo CD が適用
Kubernetes上の SealedSecrets Controller が復号（秘密鍵を使用）
    ↓
Secret に復元
```

---

### 🔓 SealedSecrets Controller

Kubernetes クラスタ内には、 **SealedSecrets Controller** というコンポーネントが動いています。

この Controller がやっていることは：

* SealedSecret を監視する
* 暗号化されたデータを復号する
* 通常の Secret を自動生成する

という役割です。

---

### 🔑 鍵の仕組み（公開鍵と秘密鍵）

SealedSecret の安全性は「公開鍵暗号」によって成り立っています。

クラスタ内の SealedSecrets Controller は：

* 🔐 秘密鍵（クラスタ内だけに存在）
* 🔓 公開鍵（外部に配布可能）

のペアを持っています。

---

#### 暗号化の流れ

1. あなたのPCで `kubeseal` を実行
2. `kubeseal` はクラスタから **公開鍵** を取得
3. その公開鍵で Secret を暗号化
4. 暗号化済みデータ（SealedSecret）を生成

---

#### 復号の流れ

1. SealedSecret が Kubernetes に apply される
2. SealedSecrets Controller が検知
3. Controller が **秘密鍵** で復号
4. 通常の Secret を作成

---

## 🎯 まとめ

| 役割         | どこにある？      | 何をする？       |
| ---------- | ----------- | ----------- |
| kubeseal   | あなたのPC      | 公開鍵で暗号化     |
| 公開鍵        | クラスタから取得    | 暗号化用        |
| 秘密鍵        | クラスタ内のみ     | 復号用         |
| Controller | Kubernetes内 | 自動でSecret生成 |

この「公開鍵で暗号化・秘密鍵で復号」という仕組みがあるからこそ、SealedSecret は Git で安全に管理できるのです。

---

# 全体の流れ

1. kubeseal をインストール
2. 平文 Secret を作る（gitignore）
3. SealedSecret に変換
4. Git push（Argo CD が自動適用）
5. Concourse pipeline から参照

---

# 1️⃣ kubeseal をインストール

`kubeseal` は Secret を暗号化するための CLI ツールです。

```bash
KUBESEAL_VERSION="0.27.0"
curl -sL "https://github.com/bitnami-labs/sealed-secrets/releases/download/v${KUBESEAL_VERSION}/kubeseal-${KUBESEAL_VERSION}-linux-amd64.tar.gz" \
  | tar -xz kubeseal && sudo install -m 755 kubeseal /usr/local/bin/
```

### 💡 ポイント

* `k8s-home` がセットアップされ、 `kube-system` namespace に SealedSecrets controller がインストール済みであることが前提

確認方法
```bash
$ kubectl get deploy -A | grep sealed
kube-system     sealed-secrets-controller          1/1     1            1           11d
```

---

# 2️⃣ Secret YAML を作成する

まずは「平文」の Secret を作ります。

⚠️ これは Git にコミットしません（必ず `.gitignore` する）

`k8s-home` では、 `secrets/` 配下のファイルは全て ignore されます。

---

### 📁 ディレクトリ構成

```
secrets/
  your-credential-name-secret.yaml   ← これはgitignore
infra/
  secrets/
    your-credential-name-sealed.yaml ← これはコミット
```

---

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

---

## 🧠 各項目の意味

| 項目         | 意味                           |
| ---------- | ---------------------------- |
| name       | Secret の名前（後で pipeline から参照） |
| namespace  | Concourse が動いている namespace   |
| stringData | 実際の機密情報                      |

---

# 3️⃣ SealedSecret に変換する

ここが重要ステップです。

```bash
kubeseal --format yaml \
  --controller-namespace kube-system \
  --controller-name sealed-secrets-controller \
  < ./secrets/your-credential-name-secret.yaml \
  > ./infra/secrets/your-credential-name-sealed.yaml
```

---

## 🔍 何をしているの？

* `secrets/*.yaml`（平文）を入力
* 暗号化された SealedSecret を出力
* `infra/secrets/` に保存

出力された `*-sealed.yaml` は **Git にコミットしてOK**

---

## 🧠 controller-namespace / controller-name とは？

これは k8s-home 側でインストールした

* SealedSecrets Controller の namespace
* Controller 名

を指定しています。

通常：

```
namespace: kube-system
name: sealed-secrets-controller
```

になっています。

---

# 4️⃣ Git Push して適用

```bash
git add infra/secrets/your-credential-name-sealed.yaml
git commit -m "add sealed secret"
git push
```

すると：

* Argo CD が変更を検知
* SealedSecret を適用
* Kubernetes 内で Secret に復元

になります。

---

# 5️⃣ Concourse Pipeline に注入する

次に、Concourse の `pipeline.yml` で変数として使います。

---

## pipeline.yml

```yaml
params:
  SOME_ID: ((your-credential-name.some_id))
  SOME_SECRET_KEY: ((your-credential-name.some_secret_key))
```

---

## 🔎 参照形式の意味

```
((secret-name.key-name))
```

つまり：

```
((your-credential-name.some_id))
```

は、

* Secret 名：your-credential-name
* キー名：some_id

を意味します。

---

# 最後に pipeline を反映

```bash
fly -t home set-pipeline -p web-app-template -c /path/to/your/pipeline.yml
```

---

## 💡 各オプションの意味

| オプション               | 意味              |
| ------------------- | --------------- |
| -t home             | Concourse ターゲット |
| -p web-app-template | パイプライン名         |
| -c                  | pipeline ファイル   |


これで、 pipeline から secret を使えるようになりました。お疲れさまでした！

---


# 🚨 よくあるミス

* namespace が間違っている
* controller-name が違う
* 平文ファイルを commit してしまう
* pipeline の Secret 名を間違える

---
