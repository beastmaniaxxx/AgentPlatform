# Brief: ui-customization

## Problem

個人開発者として、Web検索・逆画像検索・Instagram検索・マルチモーダルRAG・画像生成・動画生成の各機能を、統一感のあるチャット体験として利用したい。各機能Specは個別に実装されるため、出力フォーマットや操作感にばらつきが生じる可能性がある。

## Current State

本PR時点ではブリーフのみ追加されており、各機能Specは未完了。横断的なUI/UX（Functions/Custom CSS）調整は未着手であり、依存Spec完了後に着手する。
## Desired Outcome

- 全機能を統一的なチャット体験で利用できる（Phase9完了基準）
- Open WebUIのFunctions/Custom CSSにより、各機能の出力（検索結果、生成画像/動画、引用元等）の表示形式が統一されている
- 各ワークフローの呼び出し方法（モデルセレクタ、コマンド等）に一貫性がある

## Approach

Open WebUIのFunctions（カスタム関数）とCustom CSSを用いて、各機能Specが出力するMarkdown形式・引用形式・画像/動画埋め込み形式を統一する。必要に応じて各 `workflows/*.yml` の出力整形部分を本Specから横断的に調整する。

## Scope

- **In**:
  - Open WebUI Functions/Custom CSSの実装
  - 各機能ワークフローの出力フォーマット統一（Markdown形式、引用表示、画像/動画埋め込み）
  - 操作感（モデルセレクタ切り替え、コマンド体系）の一貫性確認
  - 全機能を通したE2E動作確認
- **Out**:
  - 各機能のコアロジック変更（出力フォーマット調整以外は対象外）
  - 新規機能の追加

## Boundary Candidates

- Open WebUI Functions/Custom CSS
- 既存ワークフローの出力整形部分（横断的な軽微修正）

## Out of Boundary

- 各機能のバックエンドロジック（SearXNG、SerpAPI、ComfyUI呼び出し等）の変更

## Upstream / Downstream

- **Upstream**: `web-search`、`image-generation`、`reverse-image-search`、`instagram-search`、`multimodal-rag`、`video-generation`（すべて完了していることが前提）
- **Downstream**: なし（最終Spec）

## Existing Spec Touchpoints

- **Extends**: 上記6Specすべて（出力フォーマットの軽微な統一調整）
- **Adjacent**: なし

## Constraints

- 既存ファイルへの変更は必要最小限に留める
- 各Spec完了時にmainへマージ済みであることが前提（依存Specの完了が必須）
