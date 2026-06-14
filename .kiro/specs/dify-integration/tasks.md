# Implementation Plan

- [x] 1. Foundation: 環境変数テンプレートとDify Sandbox設定のvendor
- [x] 1.1 docker/.env.exampleへのDify/Pipelines関連環境変数の追加
  - `docker/.env.example`に`DIFY_SECRET_KEY`・`DIFY_DB_USERNAME`/`DIFY_DB_PASSWORD`/`DIFY_DB_DATABASE`・`DIFY_REDIS_*`・`DIFY_WEB_PORT`・`DIFY_API_PORT`・`PIPELINES_PORT`・`DIFY_API_BASE_URL`（例: `http://dify-api:5001/v1`）・`DIFY_APP_API_KEY`（検証用ワークフローのAPIキー、初期値は空欄）をコメント付きで追加する
  - 既存の`.gitignore`に`docker/.env`が含まれていることを確認し、Dify関連の機密情報も同ファイル経由で管理されることをコメントで明記する
  - 観測可能完了: `docker/.env.example`をコピーして作成した`docker/.env`に追加した全変数が存在し、`git status`で`docker/.env`が追跡対象外であることが確認できる
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 1.2 Dify Sandbox用ssrf_proxy設定のvendorとバージョン方針メモの作成
  - `docker/dify/ssrf_proxy/squid.conf.template`と`docker/dify/ssrf_proxy/docker-entrypoint.sh`を、Dify公式リポジトリの`docker/ssrf_proxy/`配下から実装時点の安定タグに対応するバージョンでvendorする
  - `docker/dify/README.md`に、vendor元のリポジトリURL・取得時のDifyバージョン（v1.11以降の安定タグ）・以降のDify関連サービスで使用するイメージタグの方針を記録する
  - 観測可能完了: `docker/dify/ssrf_proxy/squid.conf.template`・`docker/dify/ssrf_proxy/docker-entrypoint.sh`・`docker/dify/README.md`が存在し、READMEに採用したDifyバージョンタグが明記されている
  - _Requirements: 1.1_

- [ ] 2. Core: Difyサービス群のdocker-compose追加
- [x] 2.1 Difyデータストア（PostgreSQL+pgvector, Redis）サービスの追加
  - `docker-compose.yml`に`dify-db`（`pgvector/pgvector`イメージ、`docker/.env`の`DIFY_DB_*`を使用）と`dify-redis`サービスを追加し、両方を`agentplatform-net`に接続する
  - `dify-db`・`dify-redis`それぞれに名前付きボリュームを定義し、トップレベル`volumes:`に追加する
  - 観測可能完了: `docker compose up -d dify-db dify-redis`でコンテナが起動し、`docker compose exec dify-db pg_isready`が成功を返す。`docker compose restart dify-db`後もデータが保持される（ボリュームがマウントされている）
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2.2 Dify Sandbox・SSRF Proxyサービスの追加
  - `docker-compose.yml`に`dify-ssrf-proxy`（squid、1.2でvendorした`docker/dify/ssrf_proxy/`をマウント）と`dify-sandbox`サービスを追加し、`agentplatform-net`に接続する
  - `dify-sandbox`が`dify-ssrf-proxy`経由でのみ外部送信を行う構成（公式構成のネットワーク・環境変数設定）とする
  - 観測可能完了: `docker compose up -d dify-ssrf-proxy dify-sandbox`で両コンテナが起動し、`docker compose logs dify-sandbox`にvendorしたsquid設定の読み込みエラーが出力されない
  - _Requirements: 1.1, 1.2_
  - _Depends: 1.2_

- [x] 2.3 Dify Plugin Daemonサービスの追加
  - `docker-compose.yml`に`dify-plugin-daemon`サービスを追加し、`dify-db`・`dify-redis`への接続環境変数を設定して`agentplatform-net`に接続する
  - プラグインストレージ用の名前付きボリュームを定義する
  - 観測可能完了: `docker compose up -d dify-plugin-daemon`でコンテナが起動し、`docker compose exec dify-plugin-daemon`からプロセスがリスニング状態であることを確認できる
  - _Requirements: 1.1, 1.2_
  - _Depends: 2.1_

- [x] 2.4 Dify API/Worker/Worker Beatサービスの追加
  - `docker-compose.yml`に`dify-api`（mode=api）・`dify-worker`（mode=worker）・`dify-worker-beat`（mode=beat）サービスを追加し、`docker/.env`の`DIFY_SECRET_KEY`・`DIFY_DB_*`・`DIFY_REDIS_*`・`VECTOR_STORE=pgvector`設定・Plugin Daemon接続先を環境変数として設定する
  - 3サービスを`agentplatform-net`に接続し、`depends_on`で`dify-db`・`dify-redis`・`dify-sandbox`・`dify-plugin-daemon`の起動完了を待機する設定を行う
  - `dify-api`を`127.0.0.1:${DIFY_API_PORT}:5001`でホストに公開する
  - 観測可能完了: `docker compose up -d`実行後、`curl http://localhost:${DIFY_API_PORT}/`がHTTPレスポンス（404を含む）を返し、`dify-api`コンテナが`agentplatform-net`上で起動していることが`docker compose ps`で確認できる
  - _Requirements: 1.1, 1.2, 1.3_
  - _Depends: 2.1, 2.2, 2.3_

- [x] 2.5 Dify Webサービスの追加
  - `docker-compose.yml`に`dify-web`サービスを追加し、`CONSOLE_API_URL`/`APP_API_URL`を`dify-api`のコンテナ名URLに設定して`agentplatform-net`に接続する
  - `127.0.0.1:${DIFY_WEB_PORT}:3000`でホストに公開する
  - 観測可能完了: `docker compose up -d dify-web`後、ブラウザまたは`curl http://localhost:${DIFY_WEB_PORT}`でDifyの初期セットアップ/ログイン画面が表示される
  - _Requirements: 1.1, 1.2_
  - _Depends: 2.4_

- [ ] 3. Core: Open WebUI Pipelinesランタイムの追加
- [ ] 3.1 pipelinesサービスのdocker-compose追加
  - `docker-compose.yml`に`pipelines`サービス（`ghcr.io/open-webui/pipelines:main`）を追加し、リポジトリの`pipelines/`ディレクトリをコンテナの`/app/pipelines`にマウントする
  - `agentplatform-net`に接続し、`127.0.0.1:${PIPELINES_PORT}:9099`でホストに公開する
  - 観測可能完了: `docker compose up -d pipelines`後、`curl http://localhost:${PIPELINES_PORT}/models`がHTTP 200とJSON配列（空配列でよい）を返す
  - _Requirements: 6.2_

- [ ] 4. Core: DifyBridge Pipelineの実装
- [ ] 4.1 テキストメッセージ中継とエラーハンドリングの実装
  - `pipelines/dify_bridge.py`を作成し、`Valves`（`DIFY_API_BASE_URL`・`DIFY_APP_API_KEY`・`REQUEST_TIMEOUT_SECONDS`を環境変数から読み込む）と`Pipe`クラスを実装する
  - `pipe()`がテキストメッセージを`POST /v1/chat-messages`（`response_mode: blocking`、`user`にOpen WebUIのユーザー識別子を設定）でDifyへ転送し、`answer`を戻り値として返す
  - Dify API呼び出し中であることを示す中間状態（処理中表示）を返す処理と、接続エラー・タイムアウト発生時に例外を発生させずユーザー向けエラーメッセージ文字列を返す処理を実装する
  - 観測可能完了: `docker compose restart pipelines`後、`curl http://localhost:${PIPELINES_PORT}/models`のレスポンスに`dify_bridge`が含まれる。モックしたDify応答に対して`pipe()`が`answer`の値を返し、接続エラーをシミュレートした場合は例外を発生させずエラーメッセージ文字列を返す
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1_
  - _Depends: 3.1_

- [ ] 4.2 画像メッセージ中継の実装
  - `pipelines/dify_bridge.py`の`pipe()`を拡張し、`messages[-1]["content"]`がリストで`image_url`（`data:image/...;base64,...`）を含む場合に、base64データを抽出して`POST /v1/files/upload`を呼び出し、取得した`upload_file_id`を`files`配列に含めて`POST /v1/chat-messages`を実行する
  - 画像を含まないテキストのみのメッセージでは`/v1/files/upload`を呼び出さない（4.1の挙動を維持）
  - `/v1/files/upload`または画像付き`chat-messages`が失敗した場合、`chat-messages`を実行せず（または結果を返さず）ユーザー向けエラーメッセージ文字列を返す
  - 観測可能完了: 画像付きメッセージを渡した場合に`/v1/files/upload`→`/v1/chat-messages`の順で呼び出しが行われ`answer`が返る一方、テキストのみのメッセージでは`/v1/files/upload`が呼び出されないことをユニットテストで確認できる。アップロード失敗をシミュレートした場合、`chat-messages`が呼び出されずエラーメッセージ文字列が返る
  - _Requirements: 5.1, 5.2, 5.3_
  - _Depends: 4.1_

- [ ] 5. Core: Echo検証用ワークフローの作成
- [ ] 5.1 (P) echo_workflow.ymlの作成
  - `workflows/echo_workflow.yml`に、受信した`query`テキストとファイル添付の有無をそのまま応答メッセージとして返す最小構成のDify DSL（Start/End構成のChatflow）を作成する
  - 観測可能完了: `workflows/echo_workflow.yml`がDify DSLのスキーマ（`version`・`kind`・`graph`の`start`/`end`ノード等）に準拠したYAMLとして記述されている
  - _Requirements: 6.1_
  - _Boundary: Echo Verification Workflow_

- [ ] 6. Integration & Validation: 統合起動確認とEnd-to-End検証
- [ ] 6.1 Difyサービス群を含む統合起動確認
  - `docker compose up -d`で既存サービス（`open-webui`/`ollama`/`searxng`）とDifyサービス群・`pipelines`を含む全コンテナを起動し、`docker compose ps`で全サービスが`Up`/healthyであることを確認する
  - `dify-api`コンテナ内から`curl http://ollama:11434`（またはOllama API）を実行し、`agentplatform-net`上で`ollama`サービスにコンテナ名で到達できることを確認する
  - 観測可能完了: `docker compose ps`で`dify-db`/`dify-redis`/`dify-sandbox`/`dify-ssrf-proxy`/`dify-plugin-daemon`/`dify-api`/`dify-worker`/`dify-worker-beat`/`dify-web`/`pipelines`/既存3サービスすべてが起動状態であり、`dify-api`コンテナから`ollama`への接続が成功する
  - _Requirements: 1.1, 1.2, 1.3_
  - _Depends: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1_

- [ ] 6.2 Dify初期化・Ollama接続・Pipelines接続手順書の作成
  - `docs/dify-integration-setup.md`に、(1) Difyの初回管理者アカウント作成手順、(2) Dify管理画面でのOllamaモデルプロバイダー設定手順（Base URL `http://ollama:11434`）、(3) `workflows/echo_workflow.yml`のインポート・公開・アプリAPIキー発行手順（発行したキーを`docker/.env`の`DIFY_APP_API_KEY`に設定する手順を含む）、(4) Open WebUI管理画面でのPipelines接続設定手順（`http://pipelines:9099`の登録）を記載する
  - 観測可能完了: `docs/dify-integration-setup.md`が作成され、上記4手順が`docker/.env`の対応する変数名（`DIFY_APP_API_KEY`等）を明記した形で記載されている
  - _Requirements: 3.2, 4.1, 6.1, 6.2_
  - _Depends: 6.1, 5.1_

- [ ] 6.3 Dify-Ollamaモデル接続のEnd-to-End確認
  - `docs/dify-integration-setup.md`の手順に従いDify管理画面でOllamaモデルプロバイダーを設定し、Ollama上のモデルがDifyのモデル選択候補に表示されることを確認する
  - Ollama接続済みモデルを使用するワークフロー（`echo_workflow.yml`のデバッグ実行等）を実行し、Ollamaからの応答が処理結果として得られることを確認する
  - 観測可能完了: Dify管理画面のモデル選択ドロップダウンにOllama提供モデルが表示され、該当モデルを使用したワークフローのデバッグ実行がOllamaからの非空の応答を返す
  - _Requirements: 4.2, 4.3_
  - _Depends: 6.2_

- [ ] 6.4 Open WebUI ↔ Dify中継のEnd-to-End確認
  - `docs/dify-integration-setup.md`の手順に従い、`echo_workflow.yml`のAPIキーを`docker/.env`の`DIFY_APP_API_KEY`に設定して`pipelines`コンテナを再起動し、Open WebUI管理画面でPipelines接続（`dify_bridge`モデル）を登録する
  - Open WebUIのチャットで`dify_bridge`モデルを選択し、(a) テキストメッセージを送信して応答が表示されること、(b) 画像を含むメッセージを送信して画像受信を示す応答が表示されること、(c) `dify-api`コンテナを停止した状態でメッセージを送信し、接続エラーメッセージが表示されることを確認する
  - 観測可能完了: Open WebUIのチャット画面で、テキスト応答・画像受信確認応答・（`dify-api`停止時の）接続エラーメッセージの3パターンがそれぞれ表示される
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 5.1, 5.2, 5.3, 6.2, 6.3, 6.4_
  - _Depends: 6.3, 4.1, 4.2_

## Implementation Notes
- 2.1: `docker compose down -v`は本プロジェクトの全ボリューム（`agentplatform_open-webui-data`/`agentplatform_ollama-data`/`agentplatform_searxng-data`を含む既存データ）を削除する。検証作業で特定サービスのみ起動・確認した後の後片付けは、`docker compose down`（`-v`なし）または`docker volume rm <個別のボリューム名>`を使用し、`-v`付きの`down`はプロジェクト全体のボリュームを削除する破壊的操作であるため使用しないこと。本タスクの検証作業中に誤って`down -v`を実行し、`infrastructure` Spec検証時に作成したOllamaモデル（`qwen3vl-test`等）・Open WebUIデータ・SearXNGデータが失われた（リカバリ不可、再構築で対応）。
