# Research & Design Decisions Template

## Summary
- **Feature**: `dify-integration`
- **Discovery Scope**: Extension（既存`infrastructure`基盤への統合）+ 新規外部サービス（Dify, Open WebUI Pipelines）の組み込み
- **Key Findings**:
  - 公式Dify Docker Compose（v1.11以降）はnginx/certbot等を含む15サービス規模の構成だが、個人ローカル利用では`nginx`を省略し`api`/`web`を直接ポート公開する簡略構成が成立する
  - Dify Chat/Workflow APIはbase64画像を直接受け付けず、`/v1/files/upload`でファイルアップロード後に`upload_file_id`を`chat-messages`の`files`配列で参照する2段階フローが必要
  - Open WebUIのPipelinesは別コンテナ（`ghcr.io/open-webui/pipelines`）として動作し、OpenAI互換APIとしてOpen WebUIから接続される。画像付きメッセージは`messages[-1]["content"]`がOpenAI Vision形式のリスト（`image_url.url`にdata URI）になる

## Research Log

### Dify公式Docker Compose構成（v1.11+）
- **Context**: `docker-compose.yml`にDifyサービス群を追加する必要があるが、公式構成の全体像と個人利用での簡略化可否を確認する
- **Sources Consulted**: [langgenius/dify docker-compose.yaml](https://github.com/langgenius/dify/blob/main/docker/docker-compose.yaml), [.env.example](https://github.com/langgenius/dify/blob/main/docker/.env.example), [Self-host Docker Compose docs](https://docs.dify.ai/en/self-host/quick-start/docker-compose)
- **Findings**:
  - 公式構成のサービス: `api`（mode=api）, `worker`（mode=worker, Celery）, `worker_beat`（mode=beat）, `web`（Next.jsフロントエンド）, `db`（postgres）, `redis`, `nginx`（リバースプロキシ、Web UI/APIの公開窓口）, `ssrf_proxy`（squid, sandboxの送信制限）, `sandbox`（Code Node実行環境）, `plugin_daemon`（プラグインランタイム、モデルプロバイダー等がプラグイン化されている）, ベクトルストア（weaviate/qdrant/pgvector等から選択）
  - `nginx`は外部公開・TLS終端用途が中心で、コンテナ間通信のみであれば`api`（内部5001）・`web`（内部3000）を直接`agentplatform-net`上に公開すれば代替可能
  - 必須環境変数: `SECRET_KEY`（32文字以上のランダム値）、`DB_USERNAME`/`DB_PASSWORD`/`DB_DATABASE`、`REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD`、ベクトルストア接続情報、`CONSOLE_API_URL`/`APP_API_URL`/`SERVICE_API_URL`
- **Implications**: `nginx`・`certbot`は本Specの範囲では不要と判断し省略する。`ssrf_proxy`はsandboxの送信制御に必要なため、squid設定ファイル（`squid.conf.template`、`docker-entrypoint.sh`）を最小限vendorする。ベクトルストアは追加コンテナ最小化のため`pgvector`（`db`のPostgreSQL拡張として動作）を選択する

### Dify Chat/Workflow API（外部からのワークフロー呼び出し）
- **Context**: `pipelines/dify_bridge.py`がOpen WebUIからのメッセージをDifyワークフローへ転送する際のAPI契約を確認する
- **Sources Consulted**: langgenius/dify-docs リポジトリの `openapi_chat.json` / `openapi_workflow.json`（`en/api-reference/`配下）, [File Upload docs](https://docs.dify.ai/api-reference/files/file-upload)
- **Findings**:
  - 認証: `Authorization: Bearer <APP_API_KEY>`（アプリ単位で発行されるAPIキー）
  - テキスト送信: `POST /v1/chat-messages`、body例: `{"query": "...", "inputs": {}, "response_mode": "blocking", "user": "<user-id>"}`
  - 画像送信: base64の直接送信は非対応（Issue #9430/#9471として要望段階）。`POST /v1/files/upload`（`multipart/form-data`、フィールド`file`+`user`）で`upload_file_id`を取得し、`chat-messages`の`files`配列に`{"type": "image", "transfer_method": "local_file", "upload_file_id": "..."}`を含めて送信する
  - blockingレスポンスの主要フィールド: `answer`（応答テキスト）、`conversation_id`、`message_id`、`metadata`
  - `response_mode`は`blocking`/`streaming`の両方をサポート。blockingはタイムアウト上限（プロキシ経由で約100秒）に注意
- **Implications**: `dify_bridge.py`は`response_mode: blocking`を採用し、画像を含む場合は「アップロード→chat-messages」の2段階呼び出しを行う。`answer`フィールドをOpen WebUIへの応答として返す

### DifyのOllamaモデルプロバイダー設定
- **Context**: Requirement 4（DifyからOllamaへのモデル接続）の設定手順を確認する
- **Sources Consulted**: [Private AI Ollama+DeepSeek+Dify guide](https://docs.dify.ai/en/learn-more/use-cases/private-ai-ollama-deepseek-dify), [Ollama plugin (marketplace)](https://marketplace.dify.ai/plugin/langgenius/ollama)
- **Findings**:
  - Dify管理画面の「設定 → モデルプロバイダー」からOllamaプラグインを追加し、モデル名（`ollama pull`で取得した名前と一致させる）・Base URL・Vision対応有無等を設定する
  - Base URLはコンテナ名でのアクセス（`http://ollama:11434`）が必要。`localhost`はDifyコンテナ自身を指すため不可
  - 同一Dockerネットワーク上にDifyの`api`/`worker`/`plugin_daemon`と`ollama`が存在することが前提
- **Implications**: Dify側の追加サービス（`api`, `worker`, `plugin_daemon`等）を`agentplatform-net`に接続し、設定手順を`docs/`にOperator向け手順として記録する（GUI操作は自動化対象外）

### Open WebUI Pipelinesフレームワーク
- **Context**: `pipelines/dify_bridge.py`の実装形式・配置・マルチモーダル入力の受け取り方を確認する
- **Sources Consulted**: [Pipelines docs](https://docs.openwebui.com/features/extensibility/pipelines/), [open-webui/pipelines repo](https://github.com/open-webui/pipelines), [example_pipeline_scaffold.py](https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/example_pipeline_scaffold.py), [google_manifold_pipeline.py](https://github.com/open-webui/pipelines/blob/main/examples/pipelines/providers/google_manifold_pipeline.py)
- **Findings**:
  - Pipelinesは`ghcr.io/open-webui/pipelines:main`という別コンテナとして動作し、Open WebUIの管理画面（接続設定）からOpenAI互換APIエンドポイント（`http://pipelines:9099`）として登録する
  - `/app/pipelines`にマウントしたPythonファイルが起動時に自動ロードされる
  - Pipelineクラスは`Valves`（Pydantic、環境変数で初期値を設定可能な設定項目）と`pipe(user_message, model_id, messages, body)`を実装する。文字列を返せば非ストリーミング応答になる
  - 画像付きメッセージでは`messages[-1]["content"]`がリストになり、`{"type": "image_url", "image_url": {"url": "data:image/...;base64,..."}}`形式で渡される
- **Implications**: `pipelines`コンテナを`docker-compose.yml`に追加し、`agentplatform-net`上で`open-webui`・Dify`api`の双方に到達できるようにする。`dify_bridge.py`は`Valves`で`DIFY_API_BASE_URL`/`DIFY_API_KEY`/検証用ワークフローの`DIFY_APP_API_KEY`を環境変数経由で受け取る

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| 公式Dify Compose全体をvendor | nginx/certbot含む全構成をそのまま追加 | 公式サポート構成と差異が無い | 個人ローカル用途には過剰、TLS証明書管理など不要な複雑性が増す | 不採用 |
| 簡略構成（nginx省略・直接ポート公開） | `api`/`web`を直接公開し、ssrf_proxy/sandboxのみ最小vendor | 既存サービス（open-webui等）と同じ「直接ポートマッピング」パターンに統一でき、構成がシンプル | 将来の外部公開時にはnginx/TLSの追加検討が必要（本Specの範囲外として明記） | 採用 |

## Design Decisions

### Decision: Dify Docker Compose構成の簡略化（nginx/certbot省略）
- **Context**: 個人ローカル利用で、既存の`agentplatform-net`上の`open-webui`/`ollama`/`searxng`と同じ「直接ポートマッピング」パターンに揃えたい
- **Alternatives Considered**:
  1. 公式`docker/docker-compose.yaml`をそのままvendorし`nginx`経由でアクセス
  2. `nginx`/`certbot`を省略し、`api`・`web`を`127.0.0.1`へ直接ポート公開
- **Selected Approach**: 2を採用。`db`・`redis`・ベクトルストア（pgvector）・`sandbox`・`ssrf_proxy`・`plugin_daemon`・`api`・`worker`・`worker_beat`・`web`を`docker-compose.yml`に追加し、すべて`agentplatform-net`に接続する
- **Rationale**: `infrastructure` Specの既存パターン（`docker-compose.yml`に直接サービス追加、`127.0.0.1:${PORT}`での公開）と一貫性を保ち、個人利用に不要なTLS/証明書管理の複雑性を避ける
- **Trade-offs**: 将来的に外部公開やマルチユーザー対応が必要になった場合はnginx等の追加が別途必要（roadmap.mdのOut of Scopeと整合）
- **Follow-up**: 実装時にDifyの安定タグ（1.11以降の特定バージョン）を選定し、`docker-compose.yml`にピン留めする

### Decision: ベクトルストアはpgvectorを採用
- **Context**: Difyはベクトルストアを必須とするが、追加コンテナ数を最小化したい
- **Alternatives Considered**:
  1. weaviate専用コンテナを追加
  2. `db`（postgres）にpgvector拡張を有効化し、Difyの`VECTOR_STORE=pgvector`設定で利用
- **Selected Approach**: 2を採用
- **Rationale**: 既存の`db`コンテナを流用でき、追加コンテナ・追加ボリュームが不要
- **Trade-offs**: pgvector拡張対応のPostgreSQLイメージ（`pgvector/pgvector:pg15`等）への切り替えが必要
- **Follow-up**: 実装時に画像生成・マルチモーダルRAG Specでのベクトル検索性能要件を確認し、必要であれば専用ベクトルストアへの移行を検討する

### Decision: Dify Chat APIの画像送信は「アップロード→chat-messages」の2段階で実装
- **Context**: `dify_bridge.py`が画像付きメッセージをDifyへ中継する方法を決定する
- **Alternatives Considered**:
  1. base64を直接`chat-messages`に含める（Dify未対応のため不可）
  2. `/v1/files/upload`でアップロードし、`upload_file_id`を`files`配列で参照
- **Selected Approach**: 2を採用
- **Rationale**: Dify公式APIで唯一サポートされる方式
- **Trade-offs**: 1メッセージあたりAPI呼び出しが2回になる（アップロード成功後にchat-messages実行）。アップロード失敗時はchat-messagesを実行せずエラー応答する
- **Follow-up**: 後続Spec（reverse-image-search等）が独自に画像をDifyへ渡す場合も同様の2段階パターンを再利用できることを設計に反映する

## Risks & Mitigations
- DifyのDocker Compose構成は公式リポジトリで頻繁にバージョンアップされる — 実装時に固定バージョンのタグを選定し、`docs/`に記録することで再現性を確保する
- `plugin_daemon`を含むDifyのプラグインアーキテクチャは比較的新しく、Ollamaプラグインの設定が再起動後に保持されない既知issueがある — 検証用ワークフローによるE2E確認（Requirement 6）でこれを早期検知する
- Dify起動には`db`/`redis`/`sandbox`等の複数コンテナのヘルスチェック完了が必要で、起動順序・待機時間が長くなる — `depends_on`の`condition: service_healthy`を活用する

## References
- [Dify Docker Compose Self-Host Guide](https://docs.dify.ai/en/self-host/quick-start/docker-compose)
- [langgenius/dify docker-compose.yaml](https://github.com/langgenius/dify/blob/main/docker/docker-compose.yaml)
- [Dify Chat Messages API](https://docs.dify.ai/api-reference/chat/chat-messages)
- [Dify File Upload API](https://docs.dify.ai/api-reference/files/file-upload)
- [Open WebUI Pipelines](https://docs.openwebui.com/features/extensibility/pipelines/)
- [open-webui/pipelines examples](https://github.com/open-webui/pipelines/tree/main/examples)
