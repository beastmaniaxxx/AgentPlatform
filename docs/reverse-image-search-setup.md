# 逆画像検索（Reverse Image Search）セットアップ手順

`reverse-image-search` Specで追加した逆画像検索機能（`reverse_image_search`）のセットアップ手順をまとめる。本手順は、`docs/dify-integration-setup.md` のセットアップが完了し、全サービスが `docker compose up -d` で起動済みであることを前提とする。

> **プライバシーに関する注意**: 逆画像検索では、アップロードされた画像が一時的に外部から参照可能なURLとして公開され、第三者の検索サービス（SerpAPI）へ送信される。ユーザーがチャットで画像を送信するたびに imgpush サーバー上に画像ファイルが蓄積されるため、定期的な削除またはストレージ管理の運用を検討すること。

対象環境: `docker/.env` の以下の変数、および Dify 管理画面で設定する環境変数を使用する。

| 変数 | 設定場所 | 用途 |
|------|----------|------|
| `IMGPUSH_PORT` | `docker/.env` | imgpush のホスト公開ポート（既定: `5100`） |
| `IMGPUSH_INTERNAL_URL` | `docker/.env` | Pipeline コンテナが imgpush にアップロードするための内部URL（既定: `http://imgpush:5000`） |
| `IMGPUSH_PUBLIC_BASE_URL` | `docker/.env` | SerpAPI から到達可能な imgpush の公開ベースURL（末尾スラッシュなし）。手順1で設定する |
| `DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY` | `docker/.env` | 逆画像検索ワークフロー（`reverse_image_search`）のアプリAPIキー。手順2で設定する |
| `REQUEST_TIMEOUT_SECONDS` | `docker/.env` | Dify ワークフローへの HTTP リクエストタイムアウト秒数（既定: `60`）。LLM ノードを含むワークフローではモデルの推論時間に応じて延長が必要になる場合がある |
| `SERPAPI_KEY` | Dify 管理画面 > Secret 環境変数 | SerpAPI の API キー。手順3で設定する（`docker/.env` には記載しない） |
| `REVERSE_IMAGE_ENGINE` | Dify 管理画面 > 環境変数 | 逆画像検索エンジン（`google_lens` / `yandex_images` / `bing_reverse_image`、既定: `google_lens`）。手順3で設定する |
| `DIFY_WEB_PORT` | `docker/.env` | Dify 管理画面（`dify-web`）のホスト公開ポート（既定: `3001`） |
| `PIPELINES_PORT` | `docker/.env` | Open WebUI Pipelines のホスト公開ポート（既定: `9099`） |
| `OPEN_WEBUI_PORT` | `docker/.env` | Open WebUI のホスト公開ポート（既定: `3000`） |

## 1. imgpush を外部公開する

SerpAPI は公開URLにアクセスして逆画像検索を実行する。`localhost` や LAN 内のプライベートアドレスは到達できないため、imgpush を外部から到達可能な URL で公開し、その URL を `IMGPUSH_PUBLIC_BASE_URL` に設定する。

### 1-1. Cloudflare Tunnel を使った公開（推奨例）

[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) を使うと、ルータのポート開放なしに imgpush を HTTPS で公開できる。**Zero Trust Free プランで運用可能**（Cloudflare Tunnel は無料プランに含まれる）。

1. Cloudflare ダッシュボードにログインし、左側メニューの「Zero Trust」セクションを開く。
2. Zero Trust 内の「Networks」>「Tunnels」（または「Access」>「Tunnels」）に移動し、「+ Create a tunnel」を選択する。
3. トンネルタイプとして「Cloudflared」を選択し、トンネル名（例: `imgpush`）を入力して「Save tunnel」をクリックする。
4. 表示されたインストールコマンドを使って `cloudflared` をインストールし、トークン付きのコマンドでサービスとして起動する（Windows の場合は管理者権限の PowerShell で実行する）。
5. 「Public Hostname」タブで以下を設定してトンネルを保存する。

   | フィールド | 値 |
   |------------|-----|
   | Subdomain | 任意の文字列（例: `imgpush`） |
   | Domain | Cloudflare に登録済みのドメイン（またはサブドメインなしで `trycloudflare.com` を使う場合は不要） |
   | Type | `HTTP` |
   | URL | `localhost:5100`（`${IMGPUSH_PORT}` の値） |

6. 公開URLは手順5で入力したサブドメインとドメインの組み合わせで決まる（`https://{Subdomain}.{Domain}`）。別途確認ページへの移動は不要。例: Subdomain=`imgpush`、Domain=`example.com` であれば `https://imgpush.example.com`。

### 1-2. ngrok を使った公開（一時的なテスト用）

本番運用には向かないが、動作確認目的には ngrok も使える。

```bash
ngrok http 5100
```

表示された `https://xxxx.ngrok-free.app` を公開ベースURLとして使用する。

> ngrok の無料プランではセッションごとにURLが変わる。`IMGPUSH_PUBLIC_BASE_URL` の再設定と Pipelines コンテナの再起動が毎回必要になる。

### 1-3. `IMGPUSH_PUBLIC_BASE_URL` の設定

公開URLを確認したら `docker/.env` の `IMGPUSH_PUBLIC_BASE_URL` に設定する（末尾スラッシュなし）。

```
IMGPUSH_PUBLIC_BASE_URL=https://your-tunnel-domain.example.com
```

## 2. Dify ワークフローのインポート・公開・APIキー発行

### 2-1. ワークフローのインポート

1. Dify 管理画面（`http://localhost:${DIFY_WEB_PORT}`、既定: `http://localhost:3001`）にログインし、「スタジオ」を開く。
2. 「DSLファイルをインポート」（Import from DSL file）を選択し、リポジトリの `workflows/reverse_image_search.yml` をアップロードする。

### 2-2. LLM ノードのモデル設定

1. インポートされた「reverse_image_search」アプリを開き、ワークフローエディタで **「要約生成」ノード**（LLMノード）を選択する。
   - 画面に全ノードが表示されない場合は「画面に合わせる」ボタンやズームアウトで全体を表示する。
2. 「要約生成」ノードの「モデル」フィールドに、Dify に追加済みの Ollama モデル（`docs/dify-integration-setup.md` 手順2で追加したモデル）を設定する。

   > **重要**: モデルが未設定のまま公開するとワークフロー実行時にエラーになる。必ず Ollama モデルを設定してから公開すること。

### 2-3. ワークフローの公開とAPIキー発行

1. 画面右上の「公開する」（Publish）を実行してワークフローを公開状態にする。
2. アプリ画面左側のメニューから「APIアクセス」（API Access）を開き、「APIキー」セクションで「新しいAPIキーを作成」を実行する。
3. 発行されたAPIキー（`app-` から始まる文字列）をコピーし、`docker/.env` の `DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY` に設定する。

   ```
   DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY=app-xxxxxxxxxxxxxxxxxxxxxxxx
   ```

## 3. Dify 管理画面での環境変数設定

逆画像検索ワークフローは SerpAPI キーと検索エンジン名を Dify 環境変数から取得する。これらを Dify 管理画面で設定する（`docker/.env` には値を置かない）。

### 3-1. `SERPAPI_KEY`（Secret 環境変数）の設定

1. Dify 管理画面で「reverse_image_search」アプリを開き、「プロセスの構成」（または「アプリ設定」）の「環境変数」セクションを開く。
2. 「変数を追加」で以下を追加する。

   | 変数名 | タイプ | 値 |
   |--------|--------|-----|
   | `SERPAPI_KEY` | Secret | SerpAPI の API キー（[serpapi.com](https://serpapi.com/)で発行） |

   > **Secret 変数はワークフロー実行ログに値が表示されない**。API キーは必ず Secret タイプで設定すること。

### 3-2. `REVERSE_IMAGE_ENGINE`（通常環境変数）の設定

同じ「環境変数」セクションで以下を追加する。

| 変数名 | タイプ | 値（選択肢） |
|--------|--------|-------------|
| `REVERSE_IMAGE_ENGINE` | String | `google_lens`（既定）、`yandex_images`、または `bing_reverse_image` |

エンジンを切り替える場合は `REVERSE_IMAGE_ENGINE` の値を変更してワークフローを再公開する。コードの変更は不要である。

| エンジン | 特徴 |
|----------|------|
| `google_lens` | Google Lens。類似画像・ビジュアルマッチングに強い。SerpAPI 応答の `visual_matches` を使用 |
| `yandex_images` | Yandex Images。人物・ランドマーク検索に有効な場合がある。SerpAPI 応答の `image_results` を使用 |
| `bing_reverse_image` | Bing 逆画像検索。`image_results` / `inline_images` を使用 |

## 4. pipelines コンテナの再起動と Open WebUI でのモデル確認

`docker/.env` の設定変更（`IMGPUSH_PUBLIC_BASE_URL`・`DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY`）を `pipelines` コンテナに反映するため、再起動する。

```bash
docker compose restart pipelines
```

再起動後、以下のコマンドで `reverse_image_search` モデルが Pipelines ランタイムに登録されていることを確認する。

```bash
curl http://localhost:${PIPELINES_PORT}/models
```

レスポンスの JSON に `"id": "reverse_image_search"` が含まれていれば正常に登録されている。

次に、Open WebUI でモデルが選択可能であることを確認する。

1. ブラウザで `http://localhost:${OPEN_WEBUI_PORT}`（既定: `http://localhost:3000`）にアクセスし、Open WebUI にログインする。
2. チャット画面のモデル選択ドロップダウンに **Reverse Image Search**（モデルID: `reverse_image_search`）が表示されることを確認する。

   > Open WebUI の Pipelines 接続が未設定の場合は、`docs/dify-integration-setup.md` の手順4を先に実施すること（API Base URL: `http://pipelines:9099`、API Key: `0p3n-w3bu!`）。すでに設定済みの場合は再設定不要である。

## 5. imgpush の疎通確認

imgpush サービスが正常に起動し、公開URLからアクセスできることを確認する。

### 5-1. ヘルスチェック（内部ネットワーク）

ホストから内部ポートへのアクセスで imgpush が起動していることを確認する。

```bash
curl http://localhost:${IMGPUSH_PORT}/liveness
```

`200 OK` が返れば imgpush が正常に起動している。

### 5-2. 画像のアップロードとダウンロード確認

サンプル画像をアップロードし、`filename` フィールドから公開URLでアクセスできることを確認する。

```bash
# 1×1 ピクセルの PNG をアップロード
curl -F "file=@/dev/stdin;filename=test.png;type=image/png" \
     http://localhost:${IMGPUSH_PORT}/ \
     < /dev/zero | head -c 67 | base64 -d | head -c 0
```

実際には任意の画像ファイルを使って確認する。

```bash
# 例: test.jpg をアップロード
curl -F "file=@test.jpg" http://localhost:${IMGPUSH_PORT}/
# 応答例: {"filename": "aBcDeFgH.jpg"}
```

応答の `filename` を使って公開URLで画像が取得できることを確認する。

```bash
# 公開URLからダウンロード確認
curl -I ${IMGPUSH_PUBLIC_BASE_URL}/aBcDeFgH.jpg
# HTTP/2 200 が返れば SerpAPI からも到達可能
```

> 公開URLへのアクセスが `200` でなければ、手順1のトンネル設定を再確認すること。

### 5-3. 動作確認チェックリスト

すべての確認が完了したら、Open WebUI でエンドツーエンドの動作を確認する。

- [ ] モデル選択で `reverse_image_search` が選択できる
- [ ] 画像を添付して送信すると、プライバシー通知 + 類似画像サムネイル（Markdown）+ 出典 + 要約が表示される
- [ ] 類似画像が見つからない場合に「再検索を促す通知」が表示される
- [ ] 画像を添付せず送信すると「画像を添付してください」メッセージが表示される
