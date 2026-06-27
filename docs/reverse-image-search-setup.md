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

## 0. imgpush サービスの起動

imgpush は本 Spec で新規追加されたサービスである。既存環境を `docker compose up -d` で起動済みでも、compose ファイル更新後に未起動の場合があるため、以降の手順の前に `docker/` ディレクトリで明示的に起動しておく（手順1のトンネルは起動中の imgpush を指すため、ここで先に立ち上げる）。

```powershell
docker compose up -d imgpush
docker compose ps imgpush
```

`STATUS` が `Up`（`healthy` または `health: starting`）であればよい。詳細な疎通確認は手順5で行う。

## 1. imgpush を外部公開する

SerpAPI は公開URLにアクセスして逆画像検索を実行する。`localhost` や LAN 内のプライベートアドレスは到達できないため、imgpush を外部から到達可能な URL で公開し、その URL を `IMGPUSH_PUBLIC_BASE_URL` に設定する。

公開方法は複数あるが、**独自ドメイン不要で最も手軽な Cloudflare クイックトンネル**（1-1）を推奨する。独自ドメインを持っている場合は名前付きトンネル（1-2）で固定URLを使える。ngrok（1-3）も利用できる。1-1〜1-3 のいずれか1つを選ぶ。

### 1-1. Cloudflare クイックトンネル（推奨・独自ドメイン不要）

`cloudflared` をコマンドラインで起動するだけで、Cloudflare がランダムな公開HTTPS URLを自動発行する。Cloudflare アカウントや独自ドメインは不要。**Zero Trust Free プランの範囲で利用可能**。

#### cloudflared のインストール（初回のみ）

Windows では winget でインストールできる。

```powershell
winget install --id Cloudflare.cloudflared
```

インストール後、新しい PowerShell で `cloudflared` コマンドが認識されない場合は PATH が通っていない。実行ファイルは通常 `C:\Program Files (x86)\cloudflared\cloudflared.exe` にある。以下のいずれかで対応する。

- フルパスで実行する: `& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:5100`
- PATH に恒久追加する（**管理者権限の PowerShell** で実行し、追加後に PowerShell を再起動）:

  ```powershell
  [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Program Files (x86)\cloudflared", [EnvironmentVariableTarget]::Machine)
  ```

#### トンネルの起動

imgpush のホストポート（`5100`）に向けてクイックトンネルを起動する。

```powershell
cloudflared tunnel --url http://localhost:5100
```

起動ログに以下のような行が表示される。表示された `https://xxxx-xxxx-xxxx.trycloudflare.com` が公開URLである。

```
Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):
https://random-words-1234.trycloudflare.com
```

> **注意**:
> - このコマンドを実行している PowerShell ウィンドウは**開いたままにする**（閉じるとトンネルが切れる）。
> - クイックトンネルのURLは起動するたびに変わる。URLが変わったら `IMGPUSH_PUBLIC_BASE_URL` を再設定し、`docker compose restart pipelines` を実行する。
> - Zero Trust ダッシュボードの「Public Hostname」で `trycloudflare.com` を**手入力しても機能しない**（`trycloudflare.com` は自分で選べず、上記コマンドが自動発行するURLのみ有効）。固定サブドメインが必要な場合は 1-2 を使う。

### 1-2. Cloudflare 名前付きトンネル（独自ドメインで固定URL）

Cloudflare に登録済みの独自ドメイン（例: `example.com`）を持っている場合は、Zero Trust ダッシュボードで名前付きトンネルを作成すると `https://imgpush.example.com` のような固定URLを使える。

1. Cloudflare ダッシュボード >「Zero Trust」>「Networks」>「Tunnels」>「+ Create a tunnel」を選択する。
2. 「Cloudflared」を選択し、トンネル名（例: `imgpush`）を入力して保存する。
3. 表示されるコマンドで `cloudflared` をサービスとしてインストール・起動する。
4. 「Public Hostname」タブで以下を設定して保存する。

   | フィールド | 値 |
   |------------|-----|
   | Subdomain | 任意（例: `imgpush`） |
   | Domain | **登録済みの独自ドメインを選択**（手入力不可。`trycloudflare.com` は選べない） |
   | Type | `HTTP` |
   | URL | `localhost:5100` |

5. 公開URLは `https://{Subdomain}.{Domain}`（例: `https://imgpush.example.com`）になる。

### 1-3. ngrok（代替手段）

```powershell
ngrok http 5100
```

表示された `https://xxxx.ngrok-free.app` を公開URLとして使用する。無料プランではセッションごとにURLが変わるため、変わるたびに `IMGPUSH_PUBLIC_BASE_URL` の再設定と Pipelines コンテナの再起動が必要になる。

### 1-4. `IMGPUSH_PUBLIC_BASE_URL` の設定

公開URLが決まったら `docker/.env` の `IMGPUSH_PUBLIC_BASE_URL` に設定する（末尾スラッシュなし）。

```
IMGPUSH_PUBLIC_BASE_URL=https://random-words-1234.trycloudflare.com
```

設定後、Pipeline コンテナへ反映するため再起動する（手順4で詳述）。

## 2. Dify ワークフローのインポート・公開・APIキー発行

### 2-1. ワークフローのインポート

1. Dify 管理画面（`http://localhost:3001`、`DIFY_WEB_PORT` の既定値）にログインし、「スタジオ」を開く。
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

`docker/.env` の設定変更（`IMGPUSH_PUBLIC_BASE_URL`・`DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY`）を `pipelines` コンテナに反映するため、`docker/` ディレクトリで再起動する。

```powershell
docker compose restart pipelines
```

再起動後、以下のコマンドで `reverse_image_search` モデルが Pipelines ランタイムに登録されていることを確認する（`9099` は `PIPELINES_PORT` の既定値。`0p3n-w3bu!` は Pipelines の既定APIキー）。

```powershell
curl.exe http://localhost:9099/models -H "Authorization: Bearer 0p3n-w3bu!"
```

レスポンスの JSON に `"id":"reverse_image_search"` が含まれていれば正常に登録されている。

次に、Open WebUI でモデルが選択可能であることを確認する。

1. ブラウザで `http://localhost:3000`（`OPEN_WEBUI_PORT` の既定値）にアクセスし、Open WebUI にログインする。
2. チャット画面のモデル選択ドロップダウンに **Reverse Image Search**（モデルID: `reverse_image_search`）が表示されることを確認する。

   > Open WebUI の Pipelines 接続が未設定の場合は、`docs/dify-integration-setup.md` の手順4を先に実施すること（API Base URL: `http://pipelines:9099`、API Key: `0p3n-w3bu!`）。すでに設定済みの場合は再設定不要である。

## 5. imgpush の疎通確認

imgpush サービスが正常に起動し、公開URLからアクセスできることを確認する（imgpush 自体の起動は手順0で実施済みの前提）。

### 5-1. ヘルスチェック（内部ネットワーク）

ホストから内部ポートへのアクセスで imgpush が起動していることを確認する（`5100` は `IMGPUSH_PORT` の既定値）。

```powershell
curl.exe http://localhost:5100/liveness
```

`{"status":"ok"}` が返れば imgpush が正常に起動している。

### 5-2. 画像のアップロードとダウンロード確認

任意の画像ファイル（JPG または PNG、なんでもよい）を1つ用意し、imgpush にアップロードして、返ってきた `filename` で画像が取得できることを確認する。

> 以下は **Windows PowerShell** での実行例である。PowerShell では `curl` がエイリアスとして別コマンド（`Invoke-WebRequest`）に割り当てられているため、必ず `curl.exe` と明示的に拡張子付きで実行すること。

#### 手順 A: テスト画像を用意する

手元にある画像ファイルのフルパスを確認する。新規に用意する場合は、例えば `docker/` フォルダ直下に `test.jpg` という名前で画像を1つ置く。以下の例では `test.jpg` をこのフォルダに置いた前提で記載する。

```powershell
# 例: カレントディレクトリ（docker/）に test.jpg がある場合のフルパス確認
Resolve-Path .\test.jpg
```

#### 手順 B: imgpush にアップロードする

`curl.exe` の `-F` オプションで画像をアップロードする。`@` の後にはアップロードする画像ファイルのパスを指定する（フルパスでも、カレントディレクトリからの相対パスでもよい）。

```powershell
# .\test.jpg をアップロード（5100 は IMGPUSH_PORT の既定値）
curl.exe -F "file=@.\test.jpg" http://localhost:5100/
```

成功すると、以下のように保存されたファイル名が JSON で返る。

```json
{"filename": "aBcDeFgH.jpg"}
```

この `filename` の値（上記例では `aBcDeFgH.jpg`）を次の手順で使う。

#### 手順 C: 内部URLでダウンロードできることを確認する

まず、トンネルを介さない内部URL（`localhost`）で画像が取得できることを確認する。`aBcDeFgH.jpg` の部分は手順 B で返ってきた実際のファイル名に置き換える。

imgpush の画像エンドポイントは HEAD リクエストを許可していないため、`-I` は使わず、**GETリクエストでステータスコードのみ**を取得する。`-o NUL` でレスポンスボディ（画像データ）を Windows の null デバイスへ捨て、`-w "%{http_code}"` でHTTPステータスコードを表示する。

> PowerShell で `-o $null` と書くと `$null` が空文字に展開されて失敗するため、必ず Windows の null デバイス名 `NUL` を使うこと。

```powershell
curl.exe -s -o NUL -w "%{http_code}" http://localhost:5100/aBcDeFgH.jpg
```

`200` が返れば、imgpush への保存と取得は正常である。

#### 手順 D: 公開URLでダウンロードできることを確認する

次に、SerpAPI が実際にアクセスする公開URL（`IMGPUSH_PUBLIC_BASE_URL` + ファイル名）で画像が取得できることを確認する。`https://your-tunnel-domain.example.com` の部分は手順1で設定した実際の公開ベースURLに置き換える。

```powershell
curl.exe -s -o NUL -w "%{http_code}" https://your-tunnel-domain.example.com/aBcDeFgH.jpg
```

`200` が返れば、SerpAPI からも到達可能な状態になっている。`000` が返る場合は、URLのホスト名が DNS 解決できていない（公開URLが間違っている／トンネルが起動していない）。手順1で発行された正しい公開URLを使っているか、トンネル用の PowerShell ウィンドウが開いたままかを確認すること。

> 手順 C は成功するが手順 D が `200` 以外（タイムアウト・404・502 等）になる場合は、imgpush 自体は正常で、手順1のトンネル設定（公開URLの向き先が `localhost:5100` になっているか）に問題がある。手順1を再確認すること。

### 5-3. 動作確認チェックリスト

すべての確認が完了したら、Open WebUI でエンドツーエンドの動作を確認する。

- [x] モデル選択で `reverse_image_search` が選択できる
- [x] 画像を添付して送信すると、プライバシー通知 + 類似画像サムネイル（Markdown）+ 出典 + 要約が表示される
- [x] 類似画像が見つからない場合に「再検索を促す通知」が表示される
- [x] 画像を添付せず送信すると「画像を添付してください」メッセージが表示される
