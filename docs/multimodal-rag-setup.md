# multimodal-rag セットアップ & エンドツーエンド配線ガイド

`multimodal-rag` を、クリーンな環境から自鯖内マルチモーダル検索（ローカルのハッシュ照合＋caption方式テキストKB検索）とWeb逆画像検索フォールバックまで疎通させるための総合手順。Dify管理画面での操作やAPIキー発行を含むため、コードだけでは完了しない技術セットアップである。

## アーキテクチャ概要

検索は2系統をローカルで併走させる。

- **ハッシュ照合（完全一致・視覚酷似）**: 登録画像の SHA-256（完全一致）と知覚ハッシュ pHash/dHash（準一致）を副インデックスに保持し、画像クエリで最上位に提示する。GPU・Dify・外部送信は不要。
- **caption方式テキストKB（意味的関連）**: 画像を Ollama Vision で日本語キャプション化し、Ollama テキスト埋め込みで Dify テキストKB に索引。テキスト/画像から内容関連を意味検索する。

自鯖内で `total = ハッシュ一致 + KB件数` が 0 のときだけ、画像を公開URL経由で `reverse_image_search`（Web逆画像検索）へフォールバックし、フォールバック通知＋外部送信通知を前置する。

```
Open WebUI → multimodal_rag Pipeline
                 ├─ ImageHashIndex（完全/準一致, /app/pipelines 配下の副インデックス）
                 ├─ multimodal_rag workflow → Dify テキストKB → Ollama（Vision/埋め込み/要約）
                 └─（0件時のみ）reverse_image_search → SerpAPI（外部送信・通知あり）
```

## 前提条件

- `docs/dify-integration-setup.md` のDify初期セットアップが完了している。
- `docs/reverse-image-search-setup.md` の imgpush とフォールバック先 `reverse_image_search` アプリが利用可能である（`DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY`・`IMGPUSH_PUBLIC_BASE_URL` を含む）。
- `docker compose up -d` で `dify-web`・`dify-api`・`ollama`・`imgpush`・`pipelines` が起動している。
- `docker/.env` が存在する（`docker/.env.example` をコピーして編集）。

## 1. Ollamaモデルと DifyテキストKB（task2手順を実施）

Ollama への Vision/埋め込み/要約モデル用意、Dify での Ollama プロバイダー登録、テキストKB作成（hybrid search + weighted score）、Dataset APIキー発行までは **`docs/multimodal-rag-dify-kb-setup.md`** に従って実施する（重複記載を避けるため本ガイドでは繰り返さない）。

完了後、`docker/.env` に以下が設定されていること。

```env
DIFY_DATASET_API_KEY=<dataset-api-key>
MULTIMODAL_RAG_DATASET_ID=<dataset-id>
MULTIMODAL_RAG_CAPTION_MODEL=<vision-model>
```

疎通確認:

```powershell
python scripts/check_multimodal_rag_setup.py
```

## 2. ハッシュ副インデックスの共有パス設定

ハッシュ副インデックスは **登録スクリプト（書き込み）** と **pipelines コンテナ（読み込み）** で共有する。既定パスは pipelines のバインドマウント（`../pipelines:/app/pipelines`）配下に置き、compose 変更なしで双方から到達できるようにする。

```env
MULTIMODAL_RAG_HASH_INDEX_PATH=/app/pipelines/data/multimodal_rag_hash_index.json
MULTIMODAL_RAG_PHASH_MAX_DISTANCE=8
```

- `MULTIMODAL_RAG_PHASH_MAX_DISTANCE` は準一致（視覚酷似）と判定する pHash のハミング距離上限。小さいほど厳密、大きいほど緩い。既定 `8` を基準に、少数サンプルで誤検出/取りこぼしを見て調整する。
- 上記 `/app/pipelines/data/...` は **pipelines コンテナ内のパス**であり、`docker/.env` にはこの値を設定する（Pipelineが参照する）。バインドマウント `../pipelines:/app/pipelines` により、同じ物理ファイルはホスト側では `pipelines/data/multimodal_rag_hash_index.json` に対応する。
- **登録スクリプトをホストから実行する場合**（手順4）、`MULTIMODAL_RAG_HASH_INDEX_PATH` はコンテナ内パスのままだとホストで解決できない。実行時にホスト側パスへ上書きすると、登録した索引を pipelines コンテナが `/app/pipelines/data/...` として読める。

  ```powershell
  $env:MULTIMODAL_RAG_HASH_INDEX_PATH = "pipelines/data/multimodal_rag_hash_index.json"
  ```

## 3. ワークフロー `multimodal_rag.yml` のインポートと配線

1. Dify管理画面で「アプリを作成」→「DSLファイルをインポート」から `workflows/multimodal_rag.yml` をインポートする。これは **workflowモード**アプリ（`/v1/workflows/run`）である。
2. インポート後、各ノードにモデル/KBを割り当てる。
   - `caption_query_image`（Vision LLM）: キャプション用 Ollama Vision モデル
   - `retrieve_caption_kb` / `retrieve_caption_kb_text`（Knowledge Retrieval）: 手順1で作成したテキストKB、hybrid search + weighted score
   - `summarize_results` / `summarize_results_text`（LLM）: 要約用 Ollama チャットモデル
3. アプリを公開し、発行された **アプリAPIキー** を `docker/.env` に設定する。

```env
DIFY_MULTIMODAL_RAG_APP_API_KEY=<workflow-app-api-key>
```

> リクエストにユーザー識別情報を含めない（`sys.user_id`/`sys.email` を参照しない）。入出力契約は Start `query_text`/`query_image`、End `count`/`items`/`summary`。

## 4. 画像の登録（ハッシュ＋キャプション）

`Pillow`・`imagehash` は pipelines ランタイムの依存（`pipelines/requirements.txt`）に含まれる。登録スクリプトを実行し、ディレクトリ内画像を検証→ハッシュ算出→imgpush(internal)アップロード→Ollama Visionキャプション→Dify Dataset API登録→副インデックス追記する（冪等）。ホスト実行時は手順2のとおり `MULTIMODAL_RAG_HASH_INDEX_PATH` をホスト側パスへ上書きしてから実行する。

```powershell
$env:MULTIMODAL_RAG_HASH_INDEX_PATH = "pipelines/data/multimodal_rag_hash_index.json"
python scripts/register_multimodal_kb.py <画像ディレクトリ>
```

- 不正形式（JPG/PNG/GIF以外）・2MB超はスキップし、他画像の登録は継続する。
- 同一 SHA-256 は登録済みとしてスキップされ、再実行で未登録分のみ処理する。
- 完了後、`MULTIMODAL_RAG_HASH_INDEX_PATH` にエントリ（`filename`/`sha256`/`phash`/`title`）が追記される。

## 5. Pipeline の登録確認

`pipelines/multimodal_rag_bridge.py` は `../pipelines:/app/pipelines` バインドマウントにより自動列挙される。反映のため再起動する。

```powershell
docker compose restart pipelines
```

確認: pipelines ランタイムの `GET /models`（ホスト公開 `http://localhost:${PIPELINES_PORT}`）の一覧に `multimodal_rag` が含まれること。Open WebUI のモデルセレクタにも `Multimodal RAG` が表示される。

## 6. フォールバック（Web逆画像検索）の配線

自鯖内0件かつ画像入力時のみ、公開URL経由で `reverse_image_search` を発火する。以下が設定済みであること（`reverse-image-search` Spec 由来）。

```env
DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY=<reverse-image-search-app-api-key>
IMGPUSH_INTERNAL_URL=http://imgpush:5000
IMGPUSH_BROWSER_BASE_URL=http://localhost:5100
IMGPUSH_PUBLIC_BASE_URL=<外部から到達できる imgpush ベースURL>
```

- `IMGPUSH_PUBLIC_BASE_URL` 未設定時はフォールバックできず、自鯖内0件は「見つからなかった」応答になる。
- フォールバック時のみ画像が外部（SerpAPI）へ送信される。Pipeline がフォールバック通知＋外部送信通知を応答先頭に前置する。

## 7. エンドツーエンド確認

Open WebUI で `Multimodal RAG` を選択し、以下を確認する。

1. **意味的関連（テキスト→画像）**: 登録画像に関するテキストで検索 → サムネイル＋関連情報＋要約が表示され、**外部送信通知が出ない**（要件2.1, 2.3）。
2. **完全一致（画像→画像）**: 登録済み画像そのものを送信 → 当該画像が**完全一致**として最上位に表示され、Webフォールバックしない（要件2.5）。
3. **準一致（画像→画像）**: 登録画像をリサイズ/再圧縮した版を送信 → **準一致**として表示される（要件2.5）。
4. **画像→関連情報**: 画像送信で関連情報（キャプション由来）が併記される（要件2.2, 2.3）。
5. **フォールバック**: 自鯖内に無い画像を送信 → **フォールバック通知＋外部送信通知＋Web逆画像検索結果**が表示される（要件4.5）。
6. **登録の疎通**: `scripts/register_multimodal_kb.py` 実行後に上記1〜4の対象が検索できる（要件1.3）。

自鯖内で充足するケース（1〜4）では `reverse_image_search`（外部送信）が呼ばれないこと（外部送信ゼロ）を併せて確認する。
