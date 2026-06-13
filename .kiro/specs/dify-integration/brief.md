# Brief: dify-integration

## Problem

個人開発者として、Open WebUIのチャット入力をDifyワークフローへ中継し、Difyが各種バックエンド（SearXNG、ComfyUI、外部API等）をオーケストレーションできるようにしたい。現状、Open WebUIとDifyを繋ぐ仕組みがなく、後続のすべての機能Specが着手できない。

## Current State

本PR時点ではブリーフのみ追加されており、DifyコンテナおよびOpen WebUI ↔ Dify のPipeline中継は未構築。まず `infrastructure` 完了後に着手する。

## Desired Outcome

- Difyコンテナ（v1.11以降）がDocker network上で稼働し、Open WebUI管理画面からPipeline経由でDifyワークフローを呼び出せる
- DifyからOllama（OpenAI互換API）への接続がGUI設定で完了している
- base64画像をOpenWebUIから受け取り、後続Spec（逆画像検索等）で使えるようPipeline側で前処理できる構成になっている

## Approach

`docker-compose.yml` にDifyサービス群を追加し、`pipelines/dify_bridge.py`（OpenWebUI ↔ Dify中継）を実装する。`DIFY_BASE_URL` と `DIFY_KEY` を環境変数化し、Open WebUI管理画面からPipelineをアップロードして接続を確認する。

## Scope

- **In**:
  - `docker-compose.yml` へのDify関連サービス追加
  - `pipelines/dify_bridge.py` の実装（DIFY_BASE_URL, DIFY_KEY を環境変数から読込）
  - DifyのOllama接続設定（GUI操作の手順をdocsに記録）
  - Open WebUIからのPipelineアップロード・疎通確認
- **Out**:
  - 個別の機能ワークフロー（web_search.yml等、各機能Specが作成）
  - ComfyUI/imgpush等の追加サービス（各機能Specが必要に応じて追加）

## Boundary Candidates

- Difyコンテナ群のDocker Compose定義
- `pipelines/dify_bridge.py`（共通中継スクリプト、複数Specから参照される）
- Dify-Ollama接続設定

## Out of Boundary

- 各機能固有のDifyワークフロー作成（各機能Specが担当）
- 画像のbase64→URL変換そのもの（`image_uploader.py` は `reverse-image-search` Spec等で詳細化）

## Upstream / Downstream

- **Upstream**: `infrastructure`
- **Downstream**: `web-search`、`image-generation`、`reverse-image-search`、`instagram-search`、`multimodal-rag`（すべてDifyワークフロー経由で実装される）

## Existing Spec Touchpoints

- **Extends**: なし
- **Adjacent**: `infrastructure`（同一Docker network構成を共有）

## Constraints

- Dify v1.11以降（マルチモーダルRAG対応版）を使用
- `pipelines/` はOpen WebUI拡張のみとし、Difyのロジックを含めない（structure.md準拠）
- 依存方向 `docker ← pipelines ← workflows` を遵守
