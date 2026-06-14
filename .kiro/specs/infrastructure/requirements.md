# Requirements Document

## Project Description (Input)
個人開発者として、ローカル環境で完結するマルチモーダルAIエージェントの基盤を構築したい。

現状、`.kiro/`（steering/specs）および `docs/`（要件定義・構成提案）の仕様ドキュメントのみが存在し、`docker/` 等の実装ディレクトリ・Compose定義は未作成のため、Open WebUI・Ollama・SearXNG等の各サービスをDocker上で連携動作させる土台がなく、後続のどの機能（Dify、ComfyUI、imgpush等）も着手できない。

これを解消するため、`docker-compose.yml`（全サービス統合定義）と `docker-compose.override.yml`（開発用オーバーライド）を中心とした構成で、Open WebUI・Ollama・SearXNGを同一Dockerネットワーク上に構築する。SearXNGは `settings.yml` でJSON出力（`/search?format=json`）を有効化し、`.env.example` で必要な環境変数を定義（`.env` はGit管理外）する。

`docker compose up` でOpen WebUI・Ollama・SearXNGが起動し、Open WebUIからチャット可能、SearXNGの `/search?format=json` が応答する状態をPhase1完了基準とする。後続Spec（dify-integration等）が追加するサービスを受け入れられるネットワーク・ボリューム構成であることも求められる。

なお、LLM要約付きのWeb検索機能自体は `web-search` Spec（Phase3、`dify-integration` 完了後）で実現するため、本Specのスコープには含まない。

## Requirements
<!-- Will be generated in /kiro-spec-requirements phase -->

