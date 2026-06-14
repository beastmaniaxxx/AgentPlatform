# Requirements Document

## Project Description (Input)
個人開発者として、ローカル環境で完結するマルチモーダルAIエージェントの基盤を構築したい。

現状、`.kiro/`（steering/specs）および `docs/`（要件定義・構成提案）の仕様ドキュメントのみが存在し、`docker/` 等の実装ディレクトリ・Compose定義は未作成のため、Open WebUI・Ollama・SearXNG等の各サービスをDocker上で連携動作させる土台がなく、後続のどの機能（Dify、ComfyUI、imgpush等）も着手できない。

これを解消するため、`docker-compose.yml`（全サービス統合定義）と `docker-compose.override.yml`（開発用オーバーライド）を中心とした構成で、Open WebUI・Ollama・SearXNGを同一Dockerネットワーク上に構築する。SearXNGは `settings.yml` でJSON出力（`/search?format=json`）を有効化し、`.env.example` で必要な環境変数を定義（`.env` はGit管理外）する。

`docker compose up` でOpen WebUI・Ollama・SearXNGが起動し、Open WebUIからチャット可能、SearXNGの `/search?format=json` が応答する状態をPhase1完了基準とする。後続Spec（dify-integration等）が追加するサービスを受け入れられるネットワーク・ボリューム構成であることも求められる。

なお、LLM要約付きのWeb検索機能自体は `web-search` Spec（Phase3、`dify-integration` 完了後）で実現するため、本Specのスコープには含まない。

## Requirements

## Boundary Context

- **In scope**: `docker-compose.yml` / `docker-compose.override.yml` によるOpen WebUI・Ollama・SearXNGコンテナの起動、3サービスが同一Dockerネットワーク上で名前解決できるネットワーク構成、`.env.example` の提供と `.env` のGit除外、SearXNGのJSON出力（`/search?format=json`）有効化、Open WebUIからのチャット動作確認、SearXNGの `/search?format=json` 応答確認
- **Out of scope**: Dify・ComfyUI・imgpush等、後続フェーズで追加されるサービスの定義（各Specで対応）。OllamaにロードするLLMモデルの選定・ダウンロード・チューニング。バックアップ・更新スクリプト（`scripts/`配下）。LLM要約付きのWeb検索機能（`web-search` Specで対応）
- **Adjacent expectations**: 後続Spec（`dify-integration` 等）は本Specが構築したDockerネットワーク・ボリューム構成にサービスを追加できることを前提とする。`web-search` Specは本Specが有効化したSearXNGの `/search?format=json` エンドポイントに依存する

### Requirement 1: Docker Compose基盤とネットワーク構成

**Objective:** 個人開発者として、Open WebUI・Ollama・SearXNGを単一のDocker Compose構成で起動・連携させたい。それにより、後続フェーズの各サービスを同じ基盤の上に追加していける。

#### Acceptance Criteria

1. When 個人開発者がDocker Compose環境で起動コマンドを実行したとき、the Infrastructure基盤 shall Open WebUI・Ollama・SearXNGの3コンテナを起動する。
2. The Infrastructure基盤 shall Open WebUI・Ollama・SearXNGの各コンテナが同一Dockerネットワーク上でコンテナ名による名前解決で相互通信できる状態を提供する。
3. Where 開発環境向けの設定上書きが必要な場合、the Infrastructure基盤 shall 開発用オーバーライド設定によって本体設定を上書きできる構成を提供する。
4. The Infrastructure基盤 shall 後続Specが追加するサービスを同一のネットワーク・ボリューム構成に追加できる状態で提供する。

### Requirement 2: Open WebUIによるチャット動作

**Objective:** 個人開発者として、Open WebUIからローカルLLM（Ollama）とチャットできる状態にしたい。それにより、基盤が正しく連携していることを確認できる。

#### Acceptance Criteria

1. When 個人開発者がOpen WebUIにブラウザでアクセスしたとき、the Open WebUIサービス shall チャット操作可能な画面を表示する。
2. When 個人開発者がOpen WebUI上でチャットメッセージを送信したとき、the Open WebUIサービス shall Ollamaサービスに接続されたモデルからの応答をチャット画面に表示する。
3. If Ollamaサービスへの接続に失敗した場合、then the Open WebUIサービス shall チャット画面にエラー状態を表示する。

### Requirement 3: SearXNGのJSON検索応答

**Objective:** 個人開発者として、SearXNGがJSON形式で検索結果を返す状態にしたい。それにより、後続の`web-search` Specがこのエンドポイントを利用できる。

#### Acceptance Criteria

1. The SearXNGサービス shall JSON形式での検索結果出力を有効化した状態で起動する。
2. When クライアントがSearXNGの `/search?format=json` エンドポイントに検索クエリ付きでリクエストを送信したとき、the SearXNGサービス shall JSON形式の検索結果を応答する。

### Requirement 4: 環境変数・機密情報の管理

**Objective:** 個人開発者として、APIキー等の機密情報をリポジトリにコミットせずに各サービスへ設定できるようにしたい。それにより、安全にリポジトリを公開・共有できる。

#### Acceptance Criteria

1. The Infrastructure基盤 shall 各サービスに必要な環境変数の項目を一覧化したテンプレートファイルをリポジトリに含める。
2. The Infrastructure基盤 shall 実際の値を含む環境変数ファイルをGit管理対象から除外する設定を提供する。
3. While 環境変数ファイルに値が設定されている場合、the Infrastructure基盤 shall 起動時に各コンテナがその値を設定として読み込む状態を提供する。

### Requirement 5: 実行環境制約への適合

**Objective:** 個人開発者として、Windows 11 + WSL2 + NVIDIA GPU環境で本基盤を動作させたい。それにより、ローカルLLM推論を実用的な速度で実行できる。

#### Acceptance Criteria

1. The Infrastructure基盤 shall Windows 11 + WSL2上のDocker Compose環境で起動できる構成を提供する。
2. Where NVIDIA GPU（CUDA対応）が利用可能な場合、the Ollamaサービス shall そのGPUを使用してLLM推論を実行できる状態で構成される。
3. The Infrastructure基盤 shall SearXNGの検索プロバイダへのアウトバウンド接続以外の外部ネットワーク接続を必要としない。
