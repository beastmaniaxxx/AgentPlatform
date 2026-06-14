# Brief: image-generation

## Problem

個人開発者として、自然言語プロンプト（必要に応じてポーズ参照画像）からチャット内で画像を生成したい。また、既存の画像をアップロードし、テキスト指示（例：「ポーズを変更して」）でその画像を編集（I2I）したい。クラウド画像生成・編集サービスはコスト・プライバシー面で制約があり、ローカルで完結させたい。

## Current State

本PR時点ではブリーフのみ追加されており、ComfyUIコンテナおよび画像生成/I2I編集ワークフローは未構築。まず `dify-integration` 完了後に着手する。

## Desired Outcome

- ユーザーがプロンプトを入力すると、LLM（Ollama）がプロンプトを翻訳・拡張・整形し、DifyのComfyUIプラグインがAPI Format形式のワークフローを呼び出して画像を生成する
- 必要に応じてポーズ参照画像を入力し、ControlNetでポーズ制御した画像生成ができる
- ユーザーが参照画像＋テキストでの変更指示（例：「ポーズを変更して」「背景を変えて」）を入力すると、LLMが指示内容をComfyUIのI2I（img2img）ワークフロー用パラメータに変換し、参照画像を基にした編集後画像を生成する
- 生成・編集画像（URL or base64）がOpen WebUIにMarkdown形式で表示される

## Approach

`docker-compose.yml` にComfyUI（Dev Mode有効化）を追加し、`comfyui-workflows/text_to_image.json` と `comfyui-workflows/image_to_image_controlnet.json` をAPI Format形式で作成。Difyワークフロー（`workflows/image_generation.yml`）でプロンプト拡張（Ollama）→ ComfyUI呼び出し→結果のMarkdown整形を行う。

I2I編集（参照画像＋テキスト指示による画像変更）は、`comfyui-workflows/image_to_image_edit.json`（img2img/IP-Adapter等を用いた画像編集ワークフロー）を追加し、同じ `workflows/image_generation.yml` 内でモード分岐（テキスト→画像 / ポーズ参照→画像 / 参照画像＋指示→編集画像）させる想定。LLMは編集指示テキストをComfyUIワークフローのパラメータ（denoise strength、プロンプト差分等）に変換する役割を担う。

## Scope

- **In**:
  - `docker-compose.yml` へのComfyUIサービス追加（Dev Mode有効化）
  - `comfyui-workflows/text_to_image.json`（テキスト→画像）
  - `comfyui-workflows/image_to_image_controlnet.json`（画像＋ポーズ→画像、ControlNet）
  - `comfyui-workflows/image_to_image_edit.json`（参照画像＋テキスト指示→編集画像、I2I）
  - `workflows/image_generation.yml`（プロンプト拡張→モード分岐（text-to-image / pose-ControlNet / I2I編集）→ComfyUI呼び出し→Markdown整形）
  - 生成・編集画像のOpen WebUIへのMarkdown表示確認
- **Out**:
  - 動画生成（`video-generation` Specが担当、本Specのワークフロー資産を再利用する前提）
  - 生成画像のナレッジベース自動登録（`multimodal-rag` の今後の検討事項、本Specでは対象外）
  - 編集履歴の保存・バージョン管理（対象外）

## Boundary Candidates

- ComfyUIコンテナ定義・Dev Mode設定
- API Formatワークフロー資産（`comfyui-workflows/`、text-to-image / pose-ControlNet / I2I編集の3種）
- 画像生成・編集Difyワークフロー（`workflows/image_generation.yml`、モード分岐ロジック）

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
- I2I編集には参照画像のアップロード（Open WebUI→Dify）が必要。base64受け渡しの仕組みは `dify-integration` のPipeline基盤を利用する
- I2I編集に必要な追加モデル/拡張（IP-Adapter等のチェックポイント）はComfyUIへの導入手順としてdocs化する
