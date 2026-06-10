# Brief: multimodal-rag

## Problem

個人開発者として、自鯖内に保存済みの画像から類似画像・関連情報を検索したい。逆画像検索（Web上）を行う前に、まず自鯖内に該当画像が存在するかを確認できるようにしたい。

## Current State

`dify-integration` Specにより基盤は構築済みだが、Difyのナレッジベース・マルチモーダル埋め込み・Rerankingは未設定。`reverse-image-search` Specは実装済みであることを前提とする（フォールバック先として連携）。

## Desired Outcome

- 事前にDifyナレッジベースへ登録した画像（JPG/PNG/GIF、最大2MB）に対し、テキスト→画像・画像→テキスト・画像→画像のクロスモーダル検索ができる
- マルチモーダルRerankingにより関連度の高い結果が上位に提示される
- 自鯖内検索で十分な結果が得られない場合、`reverse-image-search`（Web検索）へフォールバックする導線がある

## Approach

Dify v1.11.0以降のマルチモーダル埋め込みモデルを用いてナレッジベースを構築し、Difyワークフロー（`workflows/multimodal_rag.yml`）でクロスモーダル検索＋Rerankingを実装。検索結果が不十分な場合に `reverse-image-search` ワークフローへ分岐する条件分岐ロジックを設計する。

## Scope

- **In**:
  - Difyナレッジベースへのマルチモーダル埋め込みモデル設定
  - `workflows/multimodal_rag.yml`（クロスモーダル検索＋マルチモーダルReranking）
  - 自鯖内検索結果が不十分な場合の `reverse-image-search` へのフォールバック分岐
  - 画像登録フロー（JPG/PNG/GIF、最大2MB制約のバリデーション）
- **Out**:
  - 画像生成結果の自動ナレッジベース登録（「7. 今後の検討事項」、対象外）
  - Web上の逆画像検索ロジック自体（`reverse-image-search` Specが担当）

## Boundary Candidates

- Difyナレッジベース設定（マルチモーダル埋め込み、Reranking）
- マルチモーダルRAGワークフロー（`workflows/multimodal_rag.yml`）
- フォールバック分岐ロジック（自鯖内→Web検索）

## Out of Boundary

- 画像生成・動画生成パイプライン
- Instagram連携

## Upstream / Downstream

- **Upstream**: `dify-integration`、`reverse-image-search`（フォールバック先として依存）
- **Downstream**: `ui-customization`

## Existing Spec Touchpoints

- **Extends**: なし
- **Adjacent**: `reverse-image-search`（自鯖内検索→Web検索のフォールバック関係。入出力フォーマットを揃える）

## Constraints

- Dify v1.11.0以降のマルチモーダルRAG対応版が必要
- 画像形式: JPG/PNG/GIF、最大2MB
- 入力はテキストまたは画像（Markdownリンク経由）
