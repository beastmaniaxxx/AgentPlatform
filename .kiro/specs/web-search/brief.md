# Brief: web-search

## Problem

個人開発者として、チャットUIから最新情報を取得したい。LLMの知識カットオフにより最新ニュースやWeb上の情報に回答できないという課題がある。また、キーワードに基づくWeb画像の取得もチャットから行いたい。

## Current State

`infrastructure` SpecによりOpen WebUI・Ollama・SearXNGのコンテナは起動しているが、検索クエリをSearXNGへ中継しLLMが要約する仕組みは未実装。

## Desired Outcome

- ユーザーがOpen WebUIにテキストクエリを入力すると、SearXNG（複数エンジン: Google・Bing・DuckDuckGo・Brave等）でJSON検索し、上位5件をLLMが要約・引用元URL付きで返却する
- 検索結果0件の場合はその旨を通知し再検索を促す
- キーワードに基づく画像検索（SearXNGの `!images` カテゴリ）を行い、結果をMarkdown形式（`![](url)`）でチャット内に表示する

## Approach

Difyワークフロー内でSearXNGプラグイン（HTTPノード）を呼び出し、JSON形式の検索結果を取得。ローカルLLM（Ollama）が要約・整形してOpen WebUIへ返却する。画像検索は `!images` カテゴリへのクエリ送信結果をDifyワークフローでMarkdown整形する。

## Scope

- **In**:
  - ワード検索: SearXNG複数エンジン検索 → 上位5件要約 → 引用元URL付き返却（REQ-WS-001, 002, 003）
  - 画像検索: SearXNG `!images` カテゴリ検索 → Markdown画像埋め込み表示
  - 検索結果0件時のユーザー通知
  - `workflows/web_search.yml`、`workflows/image_search.yml` の作成
- **Out**:
  - 逆画像検索（`reverse-image-search` Specが担当）
  - Instagram検索（`instagram-search` Specが担当）
  - Dify-Open WebUI間のPipeline基盤自体の構築（`dify-integration` Specに依存）

## Boundary Candidates

- ワード検索ワークフロー（`workflows/web_search.yml`）
- 画像検索ワークフロー（`workflows/image_search.yml`）
- SearXNGエンジン設定（必要に応じて `docker/searxng/settings.yml` の追記）

## Out of Boundary

- 画像アップロードを伴う検索（逆画像検索）はこのSpecの対象外
- SNS（Instagram）特化の検索は対象外

## Upstream / Downstream

- **Upstream**: `infrastructure`（SearXNGコンテナ）、`dify-integration`（Dify-Open WebUI Pipeline基盤）
- **Downstream**: `ui-customization`（出力フォーマットの横断調整）

## Existing Spec Touchpoints

- **Extends**: なし
- **Adjacent**: `reverse-image-search`、`instagram-search`（いずれも検索系だが入力・連携先が異なる）

## Constraints

- SearXNGはJSON出力を有効化済みであること（`infrastructure` Spec完了が前提）
- 対応エンジン: Google Images、Bing Images、DuckDuckGo Images、Yandex Images（手動有効化）
- テキスト検索・キーワード画像検索は完全匿名（SearXNG経由）であること
