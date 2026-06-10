# Brief: video-generation

## Problem

個人開発者として、自然言語プロンプトから短尺動画を生成したい。動画生成はVRAM・処理時間の要件が大きく、ハードウェアによっては実行不可なため、オプション機能として位置づける必要がある。

## Current State

`image-generation` SpecによりComfyUI連携・プロンプト拡張パターンは確立済み。動画生成ワークフロー（AnimateDiff・WAN系等）は未構築。

## Desired Outcome

- ユーザーがプロンプトを入力すると、LLMがプロンプトを拡張し、ComfyUIの動画生成ワークフロー（AnimateDiff・WAN系等）を呼び出して短尺動画を生成する
- 生成動画ファイルがOpen WebUI上で確認できる
- VRAM不足等によりハードウェアで実行不可の場合、その旨が分かる

## Approach

`comfyui-workflows/text_to_video.json`（API Format）を作成し、`image-generation` Specで確立したプロンプト拡張→ComfyUI呼び出しパターンを再利用した `workflows/video_generation.yml` を実装する。

## Scope

- **In**:
  - `comfyui-workflows/text_to_video.json`（AnimateDiff・WAN系等のAPI Formatワークフロー）
  - `workflows/video_generation.yml`（プロンプト拡張→ComfyUI動画生成→結果返却）
  - 生成動画ファイルのOpen WebUIでの表示・ダウンロード確認
  - VRAM不足時の挙動確認・ドキュメント化（オプション機能である旨の明示）
- **Out**:
  - 画像生成・ControlNet（`image-generation` Specで実装済みのものを再利用するのみ）
  - 動画のナレッジベース登録等の高度な活用（対象外）

## Boundary Candidates

- 動画生成ComfyUIワークフロー資産（`comfyui-workflows/text_to_video.json`）
- 動画生成Difyワークフロー（`workflows/video_generation.yml`）

## Out of Boundary

- 画像生成ロジック自体（`image-generation` Specに依存）
- ストレージ内検索・RAGとの連携

## Upstream / Downstream

- **Upstream**: `image-generation`（ComfyUI連携パターン・プロンプト拡張ロジックを再利用）
- **Downstream**: `ui-customization`

## Existing Spec Touchpoints

- **Extends**: `image-generation`（ComfyUI連携パターンの再利用、新規ワークフロー追加という形）
- **Adjacent**: なし

## Constraints

- VRAM 12GB以上必須、24GB以上推奨（動画生成考慮）
- ComfyUIワークフローはAPI Format形式で固定保存
- ハードウェア要件を満たさない場合はオプション機能として扱い、必須要件としない
