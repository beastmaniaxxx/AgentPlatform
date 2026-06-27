# Web検索・画像検索セットアップ手順

`web-search` Specで追加したワード検索（`web_search`）・画像検索（`image_search`）機能のセットアップ手順をまとめる。本手順は、`docs/dify-integration-setup.md` のセットアップが完了し、全サービスが`docker compose up -d`で起動済みであることを前提とする。

対象環境: `docker/.env`の以下の変数を使用する。

| 変数 | 用途 |
|------|------|
| `DIFY_WEB_PORT` | Dify管理画面（`dify-web`）のホスト公開ポート（既定: `3001`） |
| `OPEN_WEBUI_PORT` | Open WebUIのホスト公開ポート（既定: `3000`） |
| `PIPELINES_PORT` | Open WebUI Pipelinesのホスト公開ポート（既定: `9099`） |
| `SEARXNG_PORT` | SearXNGのホスト公開ポート（既定: `8080`） |
| `DIFY_WEB_SEARCH_APP_API_KEY` | ワード検索ワークフロー（`web_search`）のアプリAPIキーを設定する変数 |
| `DIFY_IMAGE_SEARCH_APP_API_KEY` | 画像検索ワークフロー（`image_search`）のアプリAPIキーを設定する変数 |

## 1. Difyワークフローのインポート・公開・APIキー発行

### 1-1. ワード検索ワークフロー（web_search）

1. Dify管理画面（`http://localhost:${DIFY_WEB_PORT}`、既定: `http://localhost:3001`）にログインし、「スタジオ」を開く。
2. 「DSLファイルをインポート」（Import from DSL file）を選択し、リポジトリの `workflows/web_search.yml` をアップロードする。
3. インポートされた「web_search」アプリを開き、ワークフローエディタで **「要約生成」ノード**（LLMノード。画面に全ノードが表示されない場合は「画面に合わせる」ボタンやズームアウトで全体を表示する）を選択する。
4. 「要約生成」ノードの「モデル」フィールドに、Difyに追加済みのOllamaモデル（`docs/dify-integration-setup.md` 手順2で追加したモデル）を設定する。

   > **重要**: モデルが未設定のまま公開するとワークフロー実行時にエラーになる。必ずOllamaモデルを設定してから公開すること。

5. 画面右上の「公開する」（Publish）を実行してワークフローを公開状態にする。
6. アプリ画面左側のメニューから「APIアクセス」（API Access）を開き、「APIキー」セクションで「新しいAPIキーを作成」を実行する。
7. 発行されたAPIキー（`app-`から始まる文字列）をコピーし、`docker/.env`の`DIFY_WEB_SEARCH_APP_API_KEY`に設定する。

   ```
   DIFY_WEB_SEARCH_APP_API_KEY=app-xxxxxxxxxxxxxxxxxxxxxxxx
   ```

### 1-2. 画像検索ワークフロー（image_search）

1. Dify管理画面の「スタジオ」で「DSLファイルをインポート」を選択し、リポジトリの `workflows/image_search.yml` をアップロードする。
2. インポートされた「image_search」アプリを開き、画面右上の「公開する」（Publish）を実行する。

   > 補足: 画像検索ワークフローはLLMノードを使用しない。モデル設定は不要である。

3. アプリ画面左側のメニューから「APIアクセス」（API Access）を開き、「新しいAPIキーを作成」を実行する。
4. 発行されたAPIキー（`app-`から始まる文字列）をコピーし、`docker/.env`の`DIFY_IMAGE_SEARCH_APP_API_KEY`に設定する。

   ```
   DIFY_IMAGE_SEARCH_APP_API_KEY=app-xxxxxxxxxxxxxxxxxxxxxxxx
   ```

## 2. pipelinesコンテナの再起動

`docker/.env`の設定変更（`DIFY_WEB_SEARCH_APP_API_KEY`・`DIFY_IMAGE_SEARCH_APP_API_KEY`）を`pipelines`コンテナに反映するため、再起動する。

```
docker compose restart pipelines
```

再起動後、以下のコマンドで`web_search`・`image_search`の2モデルがPipelinesランタイムに登録されていることを確認する。

```
curl http://localhost:${PIPELINES_PORT}/models
```

レスポンスのJSONに`"id": "web_search"`および`"id": "image_search"`が含まれていれば正常に登録されている。

## 3. Open WebUI管理画面でのモデル確認

1. ブラウザで`http://localhost:${OPEN_WEBUI_PORT}`（既定: `http://localhost:3000`）にアクセスし、Open WebUIにログインする。
2. チャット画面のモデル選択ドロップダウンに以下の2モデルが表示されることを確認する。
   - **Web Search**（モデルID: `web_search`）
   - **Image Search**（モデルID: `image_search`）

   > 補足: Open WebUIのPipelines接続が未設定の場合は、`docs/dify-integration-setup.md`の手順4を先に実施すること（API Base URL: `http://pipelines:9099`、API Key: `0p3n-w3bu!`）。すでに設定済みの場合は再設定不要である。

## 4. SearXNGエンジン有効化設定の反映確認

SearXNGのエンジン設定（`docker/searxng/settings.yml`の`engines:`セクション）が正しく反映されていることを`curl`で確認する。

`docker/searxng/settings.yml`が存在しない場合は、テンプレートからコピーしてSearXNGを再起動した後に確認する。

```
cp docker/searxng/settings.yml.example docker/searxng/settings.yml
docker compose restart searxng
```

**ワード検索エンジンの確認:**

```
curl "http://localhost:${SEARXNG_PORT}/search?format=json&q=test"
```

レスポンスJSONの`results`配列に`"engine": "google"`・`"engine": "bing"`・`"engine": "duckduckgo"`等のエントリが含まれていれば、ワード検索エンジンが有効化されている。

**画像検索エンジンの確認:**

```
curl "http://localhost:${SEARXNG_PORT}/search?format=json&categories=images&q=cat"
```

レスポンスJSONの`results`配列に`"img_src"`キーを持つエントリが含まれていれば、画像検索エンジンが有効化されている。

> 既知の制約: Yandex ImagesはDockerコンテナの実行環境やネットワーク条件によりタイムアウトするケースがある。Google Images・Bing Images・DuckDuckGo Imagesのいずれかが動作していれば画像検索機能は利用可能である。
