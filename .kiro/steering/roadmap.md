# Roadmap

## Overview

完全セルフホスト型のマルチモーダルAIエージェントを構築する。Open WebUIを唯一のユーザー接点とし、Pipeline経由でDifyへ中継、Difyワークフローが各バックエンド（SearXNG、ComfyUI、Ollama、imgpush、SerpAPI、Instagram Graph API）を呼び出すオーケストレーション構成を採る。`docs/requirements_definition_v1.md` の8フェーズ・`docs/project_structure_proposal_v1.md` の9Spec分解案をそのまま採用し、依存順に段階実装する。

## Approach Decision

- **Chosen**: Docker Compose上にOpen WebUI / Ollama / SearXNG / Dify / ComfyUI / imgpushを構築し、Difyワークフローをハブとして各機能（Web検索・逆画像検索・SNS検索・マルチモーダルRAG・画像生成・動画生成）を統合する構成
- **Why**: すべてOSSのセルフホストでプライバシー・コストの非機能要件を満たしつつ、Difyのワークフロー機能により拡張性を確保できる。要件定義書で既に技術選定・アーキテクチャが確定しており、追加の方式検討は不要
- **Rejected alternatives**: Dify以外のオーケストレーター（n8n等）は「7. 今後の検討事項」で将来比較対象として記録のみ。現フェーズでは不採用

## Scope

- **In**: Docker基盤構築、Open WebUI/Dify連携Pipeline、Web検索（ワード/画像）、逆画像検索、Instagram画像検索、マルチモーダルRAG（ストレージ内画像検索）、画像生成（ControlNet含む）、動画生成、UI/ワークフロー最終調整
- **Out**: マルチテナント対応、SLA保証、商用展開、本番運用レベルの監視・冗長化、音声入出力（STT/TTS）、Dify以外のオーケストレーターへの移行

## Constraints

- Windows 11 + WSL2 + Docker Compose環境が前提
- NVIDIA GPU（CUDA対応、最低12GB VRAM、推奨24GB）が必要
- APIキー等は `.env` で管理しリポジトリにコミットしない
- Instagram Graph APIはビジネス/クリエイターアカウント必須、週30ユニークハッシュタグ制限あり
- 動画生成はVRAM・処理時間要件が大きく、ハードウェア次第でオプション扱い

## Boundary Strategy

- **Why this split**: 要件定義書のPhase 1〜9と1:1対応させ、各Specが独立した「動作確認可能な単位」になるよう分解。`infrastructure` と `dify-integration` を共通基盤として先行させ、以降の機能Specはこれらに依存する形にすることで、機能追加時の影響範囲を局所化する。下記の依存順は要件定義書のPhase 1〜9の順序と一致している
- **Shared seams to watch**:
  - `pipelines/dify_bridge.py`（Open WebUI ↔ Dify中継）は複数Specから参照される共通コンポーネントのため、変更時は依存する全Specへの影響を確認する
  - `imgpush` は `reverse-image-search` と将来の `multimodal-rag` 拡張の両方で使われる可能性があるため、インターフェースを安定させる
  - Difyワークフロー（`workflows/`）の命名・入出力フォーマットは `ui-customization` で横断的に調整されるため、各機能Specは出力フォーマット（Markdown形式の画像/動画埋め込み等）を統一しておく

## Specs (dependency order)

- [ ] infrastructure -- Docker基盤・ネットワーク・ボリューム構築（Open WebUI / Ollama / SearXNG）。Dependencies: none
- [ ] dify-integration -- DifyとOpen WebUIのPipeline中継基盤構築。Dependencies: infrastructure
- [ ] web-search -- SearXNG経由のワード検索・画像検索（要約＋引用付き回答、画像Markdown表示）。Dependencies: infrastructure, dify-integration
- [ ] image-generation -- ComfyUIによるテキスト→画像生成（ControlNetによるポーズ制御含む）。Dependencies: dify-integration
- [ ] reverse-image-search -- imgpush + SerpAPI（Google Lens）による逆画像検索。Dependencies: dify-integration
- [ ] instagram-search -- Instagram Graph APIによるハッシュタグ画像検索。Dependencies: dify-integration
- [ ] multimodal-rag -- Difyナレッジベースによるストレージ内マルチモーダル検索（逆画像検索のフォールバック先）。Dependencies: dify-integration, reverse-image-search
- [ ] video-generation -- ComfyUIによるテキスト→動画生成。Dependencies: image-generation
- [ ] ui-customization -- Open WebUI Functions/Custom CSSによる全機能横断のUX調整・ワークフロー最適化。Dependencies: web-search, image-generation, reverse-image-search, instagram-search, multimodal-rag, video-generation
