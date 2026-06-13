# Brief: reverse-image-search

## Problem

個人開発者として、手元の画像と類似する画像をWeb上から探したい。Open WebUIにアップロードした画像をそのまま外部の逆画像検索APIに渡す手段がない。

## Current State

本PR時点ではブリーフのみ追加されており、Dify基盤・画像のbase64→URL変換（imgpush）・SerpAPI連携は未実装。まず `dify-integration` 完了後に着手する。

## Desired Outcome

- Open WebUIにアップロードされた画像（base64）をPipelineスクリプトが受け取り、imgpushへPOSTして公開URLを取得する
- DifyのHTTPノードから当該URLをSerpAPI（`engine=google_reverse_image` または `engine=google_lens`）へ送信する
- 類似画像URLリスト・出典サイトをLLMが要約し、サムネイル＋出典サイト一覧として返却する
- 画像URLが第三者サーバー（SerpAPI）へ送信される旨をUI上で通知する

## Approach

`docker-compose.yml` にimgpushを追加。`pipelines/image_uploader.py`（base64→imgpush変換）を実装し、`pipelines/dify_bridge.py` から呼び出せるようにする。Difyワークフロー（`workflows/reverse_image_search.yml`）でimgpush URL取得→SerpAPI呼び出し→LLM要約を行う。

## Scope

- **In**:
  - `docker-compose.yml` へのimgpushサービス追加
  - `pipelines/image_uploader.py`（base64→imgpush URL変換）の実装
  - `workflows/reverse_image_search.yml`（SerpAPI連携、`engine=google_reverse_image`/`google_lens`）
  - SerpAPIキーの環境変数管理（`.env`）
  - 外部送信に関するUI通知文言の検討
- **Out**:
  - ストレージ内画像検索（`multimodal-rag` Specが担当。本Specの結果が0件/不十分な場合のフォールバック先として連携想定だが、フォールバック制御自体は `multimodal-rag` 側で扱う）
  - Instagram連携（`instagram-search` Specが担当）

## Boundary Candidates

- imgpushサービス定義・接続設定
- `pipelines/image_uploader.py`（base64→URL変換、共通利用される可能性あり）
- 逆画像検索Difyワークフロー（SerpAPI連携）

## Out of Boundary

- マルチモーダルRAGによる自鯖内検索ロジック自体
- TinEye等への切り替え（外部送信ポリシーの更新が必要な可能性があるため将来検討。本Specでは対象外）

## Upstream / Downstream

- **Upstream**: `dify-integration`
- **Downstream**: `multimodal-rag`（本Specの結果を受けてフォールバック判定を行う想定）

## Existing Spec Touchpoints

- **Extends**: なし
- **Adjacent**: `multimodal-rag`（自鯖内検索が逆画像検索のフォールバック先として位置づけられる。`pipelines/image_uploader.py` のインターフェースは将来の共有を見据えて設計する）

## Constraints

- SerpAPIは月100検索まで無料、以降有料プラン（コスト要件3.6を考慮）
- 画像URLが外部（SerpAPI）へ送信される旨をユーザーに通知する必要がある（セキュリティ要件3.4）
- SerpAPI料金プラン変更リスクへの対策としてTinEye経由のSearXNG運用への切替可能性を念頭に置く（本Spec内では実装しない）
