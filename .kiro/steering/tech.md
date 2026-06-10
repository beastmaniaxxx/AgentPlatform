# 技術スタック

## アーキテクチャ概要

全コンポーネントをDocker Compose上のコンテナとして構築し、同一Dockerネットワーク内でコンテナ名による名前解決を行う。Open WebUIを唯一のユーザー接点とし、Pipeline（Python拡張）経由でDifyへリクエストを中継、Difyのワークフローが各バックエンドサービス（SearXNG、ComfyUI、Ollama、外部API等）を呼び出すオーケストレーション構成を取る。

```
[Open WebUI] → [Pipeline(Python)] → [Dify Workflow] → 各バックエンド（SearXNG / ComfyUI / Ollama / SerpAPI / Instagram Graph API）
```

## 基盤

- OS: Windows 11 + WSL2
- コンテナ: Docker Compose（`docker-compose.yml` + `docker-compose.override.yml`）

## サービス層

- フロントエンド: Open WebUI（公式イメージ）
- LLMサーバ: Ollama（OpenAI互換APIを公開）
- LLMモデル: Vision Encoder搭載モデル（Qwen系 / Gemma系）。チャット単位でモデル切り替え可能
- メタ検索: SearXNG（JSON出力を有効化必須）
- AIオーケストレーター: Dify v1.11以降（マルチモーダルRAG対応版）
- 画像/動画生成: ComfyUI（Dev Mode有効化、API Format形式でワークフローを保存）
- 一時画像ホスト: imgpush（base64画像をURL化し、SerpAPI等の外部APIに渡すために使用）
- 外部API: SerpAPI（逆画像検索）、Instagram Graph API（ハッシュタグ検索）

## ネットワーク方針

- 全コンポーネントは同一Dockerネットワーク上に配置し、コンテナ名でURL解決する
- ホスト→コンテナ通信が必要な箇所は `host.docker.internal` を利用
- 外部接続はSearXNGの検索プロバイダ・SerpAPI・Instagram Graph APIへのアウトバウンドのみに限定

## コード規約

- Python: PEP8準拠、型ヒント必須
- YAML: 2スペースインデント
- 環境変数: SCREAMING_SNAKE_CASE（例: `SERPAPI_KEY`）
- ファイル名: kebab-case（ドキュメント）、snake_case（Python）

## セキュリティ・プライバシー方針

- APIキー等の機密情報は `.env` で管理し、リポジトリにはコミットしない
- LLM推論はすべてローカル（Ollama）で実行し、外部送信なし
- 逆画像検索など、画像URLを外部APIへ送信する処理ではユーザーへの通知が必要

## 開発環境

### 必須ツール

- Docker / Docker Compose
- NVIDIA GPU（CUDA対応、最低12GB VRAM）

---
_実装が進むにつれ、共通の起動・テストコマンドや主要な技術的決定をここに追記する_
