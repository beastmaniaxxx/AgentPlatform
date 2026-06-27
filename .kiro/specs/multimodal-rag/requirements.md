# Requirements Document

## Project Description (Input)

個人開発者として、自鯖（セルフホスト環境）内に保存済みの画像から類似画像・関連情報を検索したい。Web上の逆画像検索を行う前に、まず自鯖内に該当画像が存在するかを確認できるようにする。

Dify v1.11.0以降のマルチモーダル埋め込みモデルを用いてナレッジベースを構築し、Difyワークフロー（`workflows/multimodal_rag.yml`）でクロスモーダル検索（テキスト→画像・画像→テキスト・画像→画像）＋マルチモーダルRerankingを実装する。事前にDifyナレッジベースへ登録した画像（JPG/PNG/GIF、最大2MB）を対象とし、自鯖内検索で十分な結果が得られない場合は `reverse-image-search`（Web検索）ワークフローへフォールバックする導線を設ける。

- **対象範囲（In）**: Difyナレッジベースへのマルチモーダル埋め込みモデル設定、`workflows/multimodal_rag.yml`（クロスモーダル検索＋マルチモーダルReranking）、自鯖内検索結果が不十分な場合の `reverse-image-search` へのフォールバック分岐、画像登録フロー（JPG/PNG/GIF・最大2MB制約のバリデーション）
- **対象外（Out）**: 画像生成結果の自動ナレッジベース登録、Web上の逆画像検索ロジック自体（`reverse-image-search` Specが担当）
- **上流依存**: `dify-integration`、`reverse-image-search`（フォールバック先）
- **下流**: `ui-customization`
- **制約**: Dify v1.11.0以降のマルチモーダルRAG対応版が必要、画像形式はJPG/PNG/GIF・最大2MB、入力はテキストまたは画像（Markdownリンク経由）

## Requirements
<!-- Will be generated in /kiro-spec-requirements phase -->
