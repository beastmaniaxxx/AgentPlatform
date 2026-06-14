# Brief: video-generation

## Problem

個人開発者として、自然言語プロンプトから短尺動画を生成したい（Text to Video）。また、参照画像を開始フレームまたは終了フレームとして指定し、その画像を起点・終点とする動画を生成したい（Image to Video）。動画生成はVRAM・処理時間の要件が大きく、ハードウェアによっては実行不可なため、オプション機能として位置づける必要がある。

## Current State

本PR時点ではブリーフのみ追加されており、ComfyUI連携・プロンプト拡張パターンおよび動画生成ワークフローは未構築。まず `image-generation` 完了後に着手する。
## Desired Outcome

- ユーザーがプロンプトを入力すると、LLMがプロンプトを拡張し、ComfyUIの動画生成ワークフロー（AnimateDiff・WAN系等）を呼び出して短尺動画を生成する（Text to Video）
- ユーザーが参照画像をアップロードし「開始フレーム」または「終了フレーム」を指定すると、その画像を起点・終点としてComfyUIが動画を生成する（Image to Video）
- 生成動画ファイルがOpen WebUI上で確認できる
- VRAM不足等によりハードウェアで実行不可の場合、その旨が分かる

## Approach

`comfyui-workflows/text_to_video.json`（API Format）を作成し、`image-generation` Specで確立したプロンプト拡張→ComfyUI呼び出しパターンを再利用した `workflows/video_generation.yml` を実装する。

Image to Videoは `comfyui-workflows/image_to_video.json`（参照画像を開始/終了フレームとして受け取るAnimateDiff・WAN系等のAPI Formatワークフロー）を追加し、同じ `workflows/video_generation.yml` 内でモード分岐（Text to Video / Image to Video）させる。参照画像のアップロード（base64）は `image-generation` のI2I編集と同様、`dify-integration` のPipeline基盤を通じてDifyへ渡す。開始/終了フレーム指定はLLMまたはUI入力からワークフローパラメータ（`frame_position: start|end`等）に変換する。

## Scope

- **In**:
  - `comfyui-workflows/text_to_video.json`（AnimateDiff・WAN系等のAPI Formatワークフロー、Text to Video）
  - `comfyui-workflows/image_to_video.json`（参照画像を開始/終了フレームとするAPI Formatワークフロー、Image to Video）
  - `workflows/video_generation.yml`（プロンプト拡張→モード分岐（Text to Video / Image to Video）→ComfyUI動画生成→結果返却）
  - 開始/終了フレーム指定のためのパラメータ設計（`frame_position: start|end`等）
  - 生成動画ファイルのOpen WebUIでの表示・ダウンロード確認
  - VRAM不足時の挙動確認・ドキュメント化（オプション機能である旨の明示）
- **Out**:
  - 画像生成・ControlNet・I2I編集（`image-generation` Specで実装済みのものを再利用するのみ）
  - 開始フレームと終了フレームを同時に指定する補間動画生成（将来検討、本Specでは対象外）
  - 動画のナレッジベース登録等の高度な活用（対象外）

## Boundary Candidates

- 動画生成ComfyUIワークフロー資産（`comfyui-workflows/text_to_video.json`、`comfyui-workflows/image_to_video.json`）
- 動画生成Difyワークフロー（`workflows/video_generation.yml`、モード分岐ロジック）
- 参照画像アップロード連携（`dify-integration` のPipeline基盤の利用方法）

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

- VRAM 12GB以上必須、24GB以上推奨（動画生成考慮）。Image to Videoは参照画像のエンコードが加わるため、Text to Videoよりさらに高いVRAM消費が想定される
- ComfyUIワークフローはAPI Format形式で固定保存
- ハードウェア要件を満たさない場合はオプション機能として扱い、必須要件としない
- Image to Videoに必要な追加モデル/拡張（画像条件付き動画生成モデル等）はComfyUIへの導入手順としてdocs化する
