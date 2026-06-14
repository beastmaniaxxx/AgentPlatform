# Requirements Document

## Project Description (Input)
個人開発者として、Open WebUIのチャット入力をDifyワークフローへ中継し、Difyが各種バックエンド（SearXNG、ComfyUI、外部API等）をオーケストレーションできるようにしたい。

現状、`infrastructure` SpecによりOpen WebUI・Ollama・SearXNGがDocker Compose上で連携動作する基盤は構築済みだが、DifyコンテナおよびOpen WebUI ↔ Dify のPipeline中継は未構築であり、後続のすべての機能Spec（web-search、image-generation、reverse-image-search、instagram-search、multimodal-rag）が着手できない状態にある。

これを解消するため、`docker-compose.yml` にDifyサービス群（v1.11以降、マルチモーダルRAG対応版）を追加し、`pipelines/dify_bridge.py`（Open WebUI ↔ Dify中継）を実装する。`DIFY_BASE_URL` と `DIFY_KEY` を環境変数化し、DifyからOllama（OpenAI互換API）への接続をGUI設定で完了させ、Open WebUI管理画面からPipelineをアップロードして疎通確認を行う。また、base64画像をOpen WebUIから受け取り、後続Spec（逆画像検索等）で使えるようPipeline側で前処理できる構成とする。

個別の機能ワークフロー（web_search.yml等）やComfyUI/imgpush等の追加サービスは各機能Specの範囲とし、本Specには含まない。

## Requirements
<!-- Will be generated in /kiro-spec-requirements phase -->
