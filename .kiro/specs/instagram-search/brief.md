# Brief: instagram-search

## Problem

個人開発者として、特定ハッシュタグのInstagram投稿（画像）をチャットから検索したい。Instagram Graph APIには利用条件・取得可能フィールドの制約があり、これを踏まえた連携実装が必要。

## Current State

`dify-integration` SpecによりDify基盤は構築済みだが、Instagram Graph API連携は未実装。

## Desired Outcome

- ユーザーがハッシュタグまたは自然言語でリクエストすると、LLMがハッシュタグを抽出する
- Instagram Graph APIの `/ig_hashtag_search` でハッシュタグIDを取得し、`/{hashtag-id}/recent_media` で投稿一覧（`id`、`media_type`、`caption`、`permalink`）を取得する
- キャプション・permalinkをLLMが整形し、投稿一覧として返却する

## Approach

DifyワークフローのHTTPノードからInstagram Graph APIを呼び出す（`workflows/instagram_search.yml`）。LLM（Ollama）でハッシュタグ抽出・キャプション整形を行う。APIの制約（取得可能フィールド、レート制限）をワークフロー設計とエラーハンドリングに反映する。

## Scope

- **In**:
  - `workflows/instagram_search.yml`（ハッシュタグ抽出→`/ig_hashtag_search`→`/recent_media`→整形）
  - Instagram Graph APIの認証情報管理（`.env`）
  - 取得可能フィールド制約（`media_url`取得不可等）を踏まえたUI表示設計
  - レート制限（週30ユニークハッシュタグ）超過時のエラーハンドリング
- **Out**:
  - 個人アカウントへの対応（API仕様上不可、対象外）
  - ハッシュタグ検索結果のローカルストレージへの保存・RAG登録（`multimodal-rag` の対象外、本Specでも扱わない）

## Boundary Candidates

- Instagram Graph API連携ワークフロー（`workflows/instagram_search.yml`）
- ハッシュタグ抽出（LLMプロンプト設計）

## Out of Boundary

- 投稿画像本体の取得・表示（`media_url`が取得不可のため、permalinkのみの提示となる点を要件として明記）
- Instagram以外のSNS連携

## Upstream / Downstream

- **Upstream**: `dify-integration`
- **Downstream**: `ui-customization`（permalink表示等のUI調整）

## Existing Spec Touchpoints

- **Extends**: なし
- **Adjacent**: `web-search`（検索系という点で類似するが、連携先・制約が大きく異なるため独立Specとする）

## Constraints

- ビジネス／クリエイターアカウントが必要（個人アカウント不可）
- 1週間あたり30ユニークハッシュタグまで
- 他者投稿の `media_url`（画像URL）は取得不可、取得可能フィールドは `id`・`media_type`・`caption`・`permalink` 等に限定
- API仕様変更リスクへの対策（機能限定／代替手段の検討）は影響発生時に別途対応
