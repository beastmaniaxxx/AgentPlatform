# Research & Design Decisions

## Summary
- **Feature**: `web-search`
- **Discovery Scope**: Extension（`infrastructure`・`dify-integration`の既存基盤上に検索・要約フローを追加）
- **Key Findings**:
  - `pipelines/dify_bridge.py`は1ファイル=1 Dify App（単一`DIFY_APP_API_KEY`）の構成であり、複数のDifyワークフロー（`web_search`/`image_search`）を別モデルとして公開するには、同パターンの新規Pipelineファイルを追加する必要がある
  - `docker/.env.example`の`SEARXNG_BASE_URL=http://searxng:8080`は、まさに本Specの後続Difyワークフローがコンテナ名でSearXNGに到達するための値として既に用意されている
  - SearXNGはデフォルトで269エンジン中84エンジンのみ有効。Brave・Yandex Images等は`engines:`セクションで`disabled: false`の明示的な上書きが必要になる可能性が高い

## Research Log

### dify_bridge.pyのPipeline構成パターン
- **Context**: `web_search`/`image_search`の2つのDifyワークフローをOpen WebUIから別モデルとして選択可能にする方法を確認するため、既存`pipelines/dify_bridge.py`を調査した
- **Sources Consulted**: `pipelines/dify_bridge.py`（リポジトリ内）
- **Findings**:
  - `Pipeline.__init__`で`self.id`・`self.name`・`Valves`（`DIFY_API_BASE_URL`, `DIFY_APP_API_KEY`, `REQUEST_TIMEOUT_SECONDS`）を設定し、Open WebUI Pipelinesフレームワークが1ファイル=1モデルとして認識する
  - `pipe()`はテキスト/画像メッセージを判定し`POST /v1/chat-messages`（必要なら`/v1/files/upload`）へ中継し、接続エラー時は例外を再raiseせずエラーメッセージ文字列を返す
- **Implications**: 本Specでは`pipelines/dify_bridge.py`自体は変更せず（`dify-integration`の所有物）、同パターンに従う新規Pipelineファイルを2つ追加する。テキストクエリのみの中継であり画像アップロード処理は不要なため、共通のリレー処理を小さな共有ヘルパーに切り出し、2ファイル間の重複を避ける

### SearXNGエンジン設定（infrastructure既存設定）
- **Context**: ワード検索（Google/Bing/DuckDuckGo/Brave）・画像検索（Google Images/Bing Images/DuckDuckGo Images/Yandex Images）に必要なエンジンが`use_default_settings: true`の状態でどこまで有効かを確認した
- **Sources Consulted**: `docker/searxng/settings.yml`（リポジトリ内）、SearXNG公式ドキュメント（Configured Engines, settings_engines）
- **Findings**:
  - 現状の`settings.yml`は`engines:`セクションを持たず、SearXNG公式デフォルトの有効/無効設定がそのまま適用される
  - SearXNGはデフォルトで269エンジン中84エンジンのみ有効。Brave・Yandex Images等の一部エンジンはデフォルト無効であり、`engines:`セクションへの`disabled: false`の明示的な追記が必要
- **Implications**: 本Specで`docker/searxng/settings.yml`に`engines:`セクションを追加し、対象エンジン（Google/Bing/DuckDuckGo/Brave、Google Images/Bing Images/DuckDuckGo Images/Yandex Images）が有効になるよう明示的に設定する。実装時に各エンジンの実際の動作（クレデンシャル不要でアクセス可能か等）を確認し、`docker/searxng/settings.yml`へのコメントまたは`docs/web-search-setup.md`に記録する

### Dify HTTP Request/Code/LLMノードによるSearXNG連携
- **Context**: SearXNGのJSON検索結果を取得し、上位5件の要約（ワード検索）またはMarkdown画像埋め込み（画像検索）に変換するDifyワークフロー構成を検討した
- **Sources Consulted**: `workflows/echo_workflow.yml`（Dify DSL構造の参考）、`docker/dify/README.md`（dify-sandbox/Code node実行環境が`dify-integration`で既に構築済みであることの確認）
- **Findings**:
  - `dify-integration`によりCode node（Python3、dify-sandbox経由）の実行環境は既に整っている
  - HTTP Request nodeの呼び出し失敗（タイムアウト・非2xx）はワークフロー実行自体を失敗させ、`chat-messages` APIはエラー応答を返す。これは既存`dify_bridge.py`が`requests.exceptions.RequestException`/`raise_for_status()`で捕捉する構造と同じパターンで、Pipeline側のエラーメッセージ応答に帰着できる
- **Implications**: ワークフロー内で個別にHTTP失敗時の分岐を設けず、「0件」判定のみをワークフロー内のif-else分岐とし、HTTP/接続エラーはPipeline側の例外処理（Requirement 1.4, 2.4）に委ねることで設計を単純化する

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| 2つの独立Pipelineファイル（採用） | `web_search_bridge.py`/`image_search_bridge.py`をそれぞれ独立したPipelineとして追加し、共有ヘルパーで重複を削減 | Open WebUIのモデル選択でユーザーが明示的に検索種別を選べる。`dify_bridge.py`を変更しない | Pipelineファイルが増える | 既存`dify_bridge.py`パターンを踏襲 |
| 単一ワークフロー内で意図分類（不採用） | 1つのDifyワークフロー内でQuestion Classifierノードによりワード検索/画像検索を振り分け、`dify_bridge.py`を再利用 | Pipelineファイル追加が不要 | 意図分類の精度に依存し誤判定リスクがある。`workflows/web_search.yml`/`workflows/image_search.yml`という2ファイル構成のBoundary Candidatesと不整合 | 不採用 |

## Design Decisions

### Decision: Pipeline構成を機能ごとに分離する
- **Context**: `web_search`/`image_search`の2ワークフローをOpen WebUIから利用可能にする方法
- **Alternatives Considered**:
  1. 単一ワークフロー+意図分類（Question Classifier）で`dify_bridge.py`を再利用
  2. 機能ごとに独立したPipelineファイル（`web_search_bridge.py`/`image_search_bridge.py`）を追加
- **Selected Approach**: 2を採用。共通のリレー処理（`POST /v1/chat-messages`、エラーハンドリング）は`pipelines/_dify_search_bridge.py`の共有ヘルパーに切り出し、各Pipelineファイルはモデル識別子・APIキー・エラーメッセージ文言のみを定義する
- **Rationale**: brief.mdのBoundary Candidatesが`workflows/web_search.yml`/`workflows/image_search.yml`の2ファイル構成を前提としており、ユーザーが明示的にモデルを選択する既存UXパターン（`dify_bridge`）と一貫する。意図分類の誤判定リスクを排除できる
- **Trade-offs**: Pipelineファイル数が増えるが、各ファイルは薄いラッパーとなり保守コストは小さい
- **Follow-up**: 後続Spec（image-generation等）でも同じ共有ヘルパーパターンを再利用できるか、実装時に確認する

### Decision: HTTP/接続エラーはワークフロー分岐ではなくPipeline側で処理する
- **Context**: SearXNG接続失敗時のエラーハンドリング方式
- **Alternatives Considered**:
  1. ワークフロー内にHTTPエラー用のif-else分岐を追加
  2. HTTP Request nodeの失敗をワークフロー実行エラーとして伝播させ、Pipeline側（既存`dify_bridge.py`と同じ例外処理パターン）でエラーメッセージに変換する
- **Selected Approach**: 2を採用
- **Rationale**: `dify_bridge.py`の既存パターン（`requests.exceptions.RequestException`捕捉→エラーメッセージ文字列）と一貫し、ワークフロー側は「0件」判定のみのシンプルな分岐に限定できる
- **Trade-offs**: エラーメッセージの文言はワークフロー側でカスタマイズできないが、Pipeline側で機能ごとの文言を設定可能なため実用上問題ない
- **Follow-up**: 実装時に`chat-messages`のエラー応答形式（HTTPステータス・エラーボディ）を確認し、`_dify_search_bridge.py`の例外処理が正しく機能することを検証する

## Risks & Mitigations
- SearXNGの一部エンジン（Google/Bing等）がbot対策により不安定な結果を返す可能性 — 複数エンジンの集約により単一エンジン障害の影響を緩和し、0件時のユーザー通知（1.3, 2.3）でフォールバックする
- Yandex ImagesがSearXNG側で正しく機能しない場合 — `docs/web-search-setup.md`に動作確認結果を記録し、機能しない場合は対象エンジンから除外する
- Dify Code node（dify-sandbox経由）のJSON解析・Markdown整形処理のパフォーマンス — 上位5件程度の小規模データのため性能リスクは低いと判断

## References
- [Configured Engines - SearXNG Documentation](https://docs.searxng.org/user/configured_engines.html) — SearXNGの有効/無効エンジン一覧の確認方法
- [engines: - SearXNG Documentation](https://docs.searxng.org/admin/settings/settings_engines.html) — `engines:`セクションでの個別エンジン設定方法
