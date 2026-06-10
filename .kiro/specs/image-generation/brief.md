# Brief: image-generation

## Problem

個人開発者として、自然言語プロンプト（必要に応じてポーズ参照画像）からチャット内で画像を生成したい。クラウド画像生成サービスはコスト・プライバシー面で制約があり、ローカルで完結させたい。

## Current State

`dify-integration` SpecによりDifyワークフロー基盤は構築済みだが、ComfyUIコンテナおよび画像生成ワークフローは未構築。

## Desired Outcome

- ユーザーがプロンプトを入力すると、LLM（Ollama）がプロンプトを翻訳・拡張・整形し、DifyのComfyUIプラグインがAPI Format形式のワークフローを呼び出して画像を生成する
- 必要に応じてポーズ参照画像を入力し、ControlNetでポーズ制御した画像生成ができる
- 生成画像（URL or base64）がOpen WebUIにMarkdown形式で表示される

## Approach

`docker-compose.yml` にComfyUI（Dev Mode有効化）を追加し、`comfyui-workflows/text_to_image.json` と `comfyui-workflows/image_to_image_controlnet.json` をAPI Format形式で作成。Difyワークフロー（`workflows/image_generation.yml`）でプロンプト拡張（Ollama）→ ComfyUI呼び出し→結果のMarkdown整形を行う。

## Scope

- **In**:
  - `docker-compose.yml` へのComfyUIサービス追加（Dev Mode有効化）
  - `comfyui-workflows/text_to_image.json`（テキスト→画像）
  - `comfyui-workflows/image_to_image_controlnet.json`（画像＋ポーズ→画像、ControlNet）
  - `workflows/image_generation.yml`（プロンプト拡張→ComfyUI呼び出し→Markdown整形）
  - 生成画像のOpen WebUIへのMarkdown表示確認
- **Out**:
  - 動画生成（`video-generation` Specが担当、本Specのワークフロー資産を再利用する前提）
  - 生成画像のナレッジベース自動登録（`multimodal-rag` の今後の検討事項、本Specでは対象外）

## Boundary Candidates

- ComfyUIコンテナ定義・Dev Mode設定
- API Formatワークフロー資産（`comfyui-workflows/`）
- 画像生成Difyワークフロー（`workflows/image_generation.yml`）

## Out of Boundary

- 動画生成ワークフロー（AnimateDiff・WAN系等）は対象外
- 逆画像検索やマルチモーダルRAGとの連携は対象外（将来検討事項）

## Upstream / Downstream

- **Upstream**: `dify-integration`
- **Downstream**: `video-generation`（ComfyUI連携パターンを再利用）、`ui-customization`

## Existing Spec Touchpoints

- **Extends**: なし
- **Adjacent**: `reverse-image-search`、`multimodal-rag`（いずれも画像を扱うが用途が異なる）

## Constraints

- ComfyUIワークフローはAPI Format形式で固定保存し、互換性リスクに備える
- VRAM要件（最低12GB、推奨24GB）を考慮したワークフロー設計
- 利用LLMはVision Encoder搭載モデル（Qwen系/Gemma系）、リリース遅延時は既存版で代替
