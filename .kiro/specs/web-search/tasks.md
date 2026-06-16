# Implementation Plan

- [ ] 1. Foundation: 環境変数・SearXNGエンジン設定・Dify中継共有ヘルパーの準備
- [x] 1.1 docker/.env.exampleへのDify Appキー環境変数の追加
  - `docker/.env.example`に`DIFY_WEB_SEARCH_APP_API_KEY`・`DIFY_IMAGE_SEARCH_APP_API_KEY`（各ワークフローのAPIキー、初期値は空欄）をコメント付きで追加する
  - 観測可能完了: `docker/.env.example`をコピーして作成した`docker/.env`に両変数が存在し、`git status`で`docker/.env`が追跡対象外であることが確認できる
  - _Requirements: 1.4, 2.4_

- [ ] 1.2 SearXNGエンジン有効化設定の追加
  - `docker/searxng/settings.yml.example`の`engines:`セクションに、ワード検索向け（Google・Bing・DuckDuckGo・Brave）と画像検索向け（Google Images・Bing Images・DuckDuckGo Images・Yandex Images）のエンジンを`disabled: false`で有効化する設定を追加する
  - 認証情報やAPIキーを必要とするエンジンは追加しない
  - 観測可能完了: `settings.yml.example`を`settings.yml`としてコピーし`docker compose restart searxng`後、`curl "http://localhost:${SEARXNG_PORT}/search?format=json&q=test"`および`&categories=images&q=test`の応答に対象エンジンの結果が含まれる
  - _Requirements: 1.1, 1.5, 2.1, 2.5_

- [ ] 1.3 Dify中継共有ヘルパーの実装
  - `pipelines/_dify_search_bridge.py`に`DifyChatBridge`クラスを実装し、`ask(query, user_id)`が`POST /v1/chat-messages`（テキストクエリのみ、`response_mode: blocking`）を呼び出して`answer`を返す
  - 接続エラー・タイムアウト・非2xx応答時は`requests.exceptions.RequestException`を発生させ、エラーメッセージへの変換は呼び出し元（各Pipeline）に委ねる
  - `dify_bridge.py`の`_resolve_user_id`と同様のユーザー識別子解決ロジックを実装する
  - 観測可能完了: モックしたDify応答に対し`DifyChatBridge.ask()`が`answer`の値を返すこと、接続エラーをシミュレートした場合に`RequestException`が発生することをユニットテストで確認できる
  - _Requirements: 1.4, 2.4_

- [ ] 2. Core: ワード検索ワークフローとPipelineの実装
- [ ] 2.1 (P) web_searchワークフローの作成
  - `workflows/web_search.yml`に、Start→HTTP Request（`{SEARXNG_BASE_URL}/search?format=json&q={query}`）→Code node（`results`配列から上位5件の`title`/`url`/`content`を抽出し件数を算出）→If-Else（0件分岐）→LLM node（Ollama接続済みモデルによる上位5件の要約・各要約への引用元URL付与）/Answer（0件時の再検索を促す通知文）という構成のDify advanced-chat DSLを作成する
  - SearXNGへのHTTPリクエストにユーザー識別情報を含めない
  - 観測可能完了: `workflows/web_search.yml`をDifyにインポートし、SearXNGのモック/実応答に対するデバッグ実行で、1件以上時に要約+引用元URL付き応答、0件時に再検索を促す通知文が返ることを確認できる
  - _Requirements: 1.1, 1.2, 1.3, 1.5_
  - _Boundary: Web Search Workflow_

- [ ] 2.2 (P) WebSearchBridge Pipelineの実装
  - `pipelines/web_search_bridge.py`に`Pipeline`クラス（`self.id = "web_search"`、`Valves`に`DIFY_API_BASE_URL`・`DIFY_WEB_SEARCH_APP_API_KEY`・`REQUEST_TIMEOUT_SECONDS`）を実装し、`pipe()`が`_dify_search_bridge.DifyChatBridge.ask()`を呼び出してテキストクエリを中継する
  - `DifyChatBridge.ask()`が例外を発生させた場合、`pipe()`は例外を再raiseせず「⚠️ Web検索の実行に失敗しました」等のエラーメッセージ文字列を返す
  - 観測可能完了: `docker compose restart pipelines`後、`curl http://localhost:${PIPELINES_PORT}/models`のレスポンスに`web_search`が含まれる。モックしたDify応答に対し`pipe()`が`answer`の値を返し、接続エラーをシミュレートした場合は例外を発生させずエラーメッセージ文字列を返すことをユニットテストで確認できる
  - _Requirements: 1.2, 1.4_
  - _Boundary: WebSearchBridge Pipeline_
  - _Depends: 1.3_

- [ ] 3. Core: 画像検索ワークフローとPipelineの実装
- [ ] 3.1 (P) image_searchワークフローの作成
  - `workflows/image_search.yml`に、Start→HTTP Request（`{SEARXNG_BASE_URL}/search?format=json&categories=images&q={query}`）→Code node（`results`配列から`img_src`等を抽出し`![](url)`形式のMarkdown文字列と件数を算出、`img_src`が欠落した結果はスキップ）→If-Else（0件分岐）→Answer（Markdown画像一覧 / 0件時の再検索を促す通知文）という構成のDify advanced-chat DSLを作成する
  - SearXNGへのHTTPリクエストにユーザー識別情報を含めない
  - 観測可能完了: `workflows/image_search.yml`をDifyにインポートし、SearXNGのモック/実応答に対するデバッグ実行で、1件以上時にMarkdown画像一覧、0件時に再検索を促す通知文が返ることを確認できる
  - _Requirements: 2.1, 2.2, 2.3, 2.5_
  - _Boundary: Image Search Workflow_

- [ ] 3.2 (P) ImageSearchBridge Pipelineの実装
  - `pipelines/image_search_bridge.py`に`Pipeline`クラス（`self.id = "image_search"`、`Valves`に`DIFY_API_BASE_URL`・`DIFY_IMAGE_SEARCH_APP_API_KEY`・`REQUEST_TIMEOUT_SECONDS`）を実装し、`pipe()`が`_dify_search_bridge.DifyChatBridge.ask()`を呼び出してテキストクエリを中継する
  - `DifyChatBridge.ask()`が例外を発生させた場合、`pipe()`は例外を再raiseせず「⚠️ 画像検索の実行に失敗しました」等のエラーメッセージ文字列を返す
  - 観測可能完了: `docker compose restart pipelines`後、`curl http://localhost:${PIPELINES_PORT}/models`のレスポンスに`image_search`が含まれる。モックしたDify応答に対し`pipe()`が`answer`の値を返し、接続エラーをシミュレートした場合は例外を発生させずエラーメッセージ文字列を返すことをユニットテストで確認できる
  - _Requirements: 2.2, 2.4_
  - _Boundary: ImageSearchBridge Pipeline_
  - _Depends: 1.3_

- [ ] 4. Integration & Validation: セットアップ手順とEnd-to-End確認
- [ ] 4.1 セットアップ手順書の作成
  - `docs/web-search-setup.md`に、(1) `workflows/web_search.yml`・`workflows/image_search.yml`のDifyへのインポート・公開・APIキー発行手順（発行したキーを`docker/.env`の`DIFY_WEB_SEARCH_APP_API_KEY`/`DIFY_IMAGE_SEARCH_APP_API_KEY`へ設定する手順を含む）、(2) `pipelines`コンテナの再起動手順、(3) Open WebUI管理画面での`web_search`/`image_search`モデル登録手順、(4) SearXNGエンジン有効化設定の反映確認手順（`curl`コマンド）を記載する
  - 観測可能完了: `docs/web-search-setup.md`が作成され、上記4手順が`docker/.env`の対応する変数名を明記した形で記載されている
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5_
  - _Depends: 1.2, 2.1, 2.2, 3.1, 3.2_

- [ ] 4.2 ワード検索End-to-End確認
  - `docs/web-search-setup.md`の手順に従い、Open WebUIのチャットで`web_search`モデルを選択し、(a) テキストクエリを送信して要約+引用元URL付き応答が表示されること、(b) 0件になるクエリを送信して再検索を促す通知が表示されること、(c) `dify-api`コンテナを停止した状態でクエリを送信してエラーメッセージが表示されることを確認する
  - 観測可能完了: Open WebUIのチャット画面で、要約+引用元URL付き応答・0件時の通知・接続エラーメッセージの3パターンがそれぞれ表示される
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  - _Depends: 4.1_

- [ ] 4.3 画像検索End-to-End確認
  - `docs/web-search-setup.md`の手順に従い、Open WebUIのチャットで`image_search`モデルを選択し、(a) キーワードクエリを送信して画像がMarkdown形式で表示されること、(b) 0件になるクエリを送信して再検索を促す通知が表示されること、(c) `dify-api`コンテナを停止した状態でクエリを送信してエラーメッセージが表示されることを確認する
  - 観測可能完了: Open WebUIのチャット画面で、画像一覧表示・0件時の通知・接続エラーメッセージの3パターンがそれぞれ表示される
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - _Depends: 4.1_
