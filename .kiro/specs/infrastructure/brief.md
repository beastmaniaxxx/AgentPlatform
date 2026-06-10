# Brief: infrastructure

## Problem

個人開発者として、ローカル環境で完結するマルチモーダルAIエージェントの基盤を構築したい。各サービス（Open WebUI、Ollama、SearXNG等、後続フェーズではDify、ComfyUI、imgpush）をDocker上で連携動作させる土台がないと、以降のどの機能も着手できない。

## Current State

リポジトリには `docs/requirements_definition_v1.md`（要件定義）と `docs/project_structure_proposal_v1.md`（構成提案）のみが存在し、`docker/` 等の実装ディレクトリ・Compose定義は未作成。

## Desired Outcome

`docker compose up` でOpen WebUI・Ollama・SearXNGが同一Dockerネットワーク上で起動し、Open WebUIのチャットからWeb検索（SearXNG経由）が動作する状態（Phase1完了基準）。後続Spec（dify-integration等）が追加するサービスを受け入れられるネットワーク・ボリューム構成になっていること。

## Approach

`docker-compose.yml`（全サービス統合定義）+ `docker-compose.override.yml`（開発用オーバーライド）構成で、Open WebUI・Ollama・SearXNGをまず構築する。SearXNGは `settings.yml` でJSON出力を有効化する。`.env.example` で必要な環境変数を定義し、`.env` はGit管理外とする。

## Scope

- **In**:
  - `docker-compose.yml` / `docker-compose.override.yml` の作成
  - Open WebUI、Ollama、SearXNGコンテナの定義とネットワーク構成
  - SearXNG `settings.yml` でのJSON出力有効化
  - `.env.example` の作成、`.gitignore` への機密情報除外設定
  - 起動確認（Open WebUIからチャット可能、SearXNGの `/search?format=json` が応答する）
- **Out**:
  - Dify、ComfyUI、imgpush等の後続フェーズで追加されるサービス定義（各Specで追加）
  - LLMモデルのダウンロード・チューニング（Ollamaモデル選定は運用時に実施）
  - バックアップ・更新スクリプト（scripts/配下、将来的に検討）

## Boundary Candidates

- Docker Compose定義（`docker/docker-compose.yml`、ネットワーク・ボリューム設計）
- SearXNG設定（JSON出力有効化、検索エンジン設定）
- 環境変数管理（`.env.example`、Git除外設定）

## Out of Boundary

- Difyを含むAIオーケストレーション層（`dify-integration` Specが担当）
- ComfyUI、imgpush等の生成・画像処理サービス（各機能Specが担当）
- アプリケーションロジック（Pipelineスクリプト等）

## Upstream / Downstream

- **Upstream**: なし（最初のSpec）
- **Downstream**: `web-search`（SearXNGに依存）、`dify-integration`（このネットワーク上にDifyを追加）、以降すべてのSpec

## Existing Spec Touchpoints

- **Extends**: なし
- **Adjacent**: `dify-integration`（同じDocker network上にサービスを追加するため、ネットワーク命名規則を共有）

## Constraints

- Windows 11 + WSL2 + Docker Composeで動作すること
- NVIDIA GPU（CUDA対応）が利用可能であること
- 外部接続はSearXNGの検索プロバイダへのアウトバウンドのみ（この段階では他の外部APIは不要）
