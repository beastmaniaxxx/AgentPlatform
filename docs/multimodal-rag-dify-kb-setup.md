# multimodal-rag DifyテキストKBセットアップ手順

`multimodal-rag` task 2 では、画像キャプションを登録するDifyテキストKBと、OllamaモデルのDifyプロバイダー設定を用意する。これはDify管理画面での操作とDataset APIキー発行を含むため、コードだけでは完了しない。

前提:
- `docs/dify-integration-setup.md` のDify初期セットアップが完了している
- `docker compose up -d` で `dify-web`、`dify-api`、`ollama` が起動している
- `docker/.env` が存在し、`DIFY_WEB_PORT` と `DIFY_API_PORT` が設定されている

## 1. Ollamaでモデルを用意する

ホストまたはコンテナ内で、利用するモデルをOllamaに用意する。

```powershell
docker exec agentplatform-ollama-1 ollama list
```

不足している場合は、利用するモデル名に置き換えて取得する。

```powershell
docker exec agentplatform-ollama-1 ollama pull <vision-model>
docker exec agentplatform-ollama-1 ollama pull <embedding-model>
docker exec agentplatform-ollama-1 ollama pull <chat-model>
```

役割:
- キャプション用Visionモデル: 登録画像とクエリ画像を日本語説明文に変換する
- テキスト埋め込みモデル: DifyテキストKBの索引に使う
- 要約用チャットモデル: 検索結果の要約に使う

## 2. Dify管理画面でOllamaモデルを登録する

1. Dify管理画面 `http://localhost:${DIFY_WEB_PORT}` を開く。
2. 「設定」→「モデルプロバイダー」を開く。
3. Ollamaプロバイダーでモデルを追加する。
4. Base URL はコンテナ間通信のため `http://ollama:11434` を指定する。
5. それぞれのモデル種別を用途に合わせて登録する。
   - Vision/LLM: キャプション生成用
   - Text Embedding: テキストKB索引用
   - LLM: 要約用
6. 保存後、各モデルがDifyのモデル選択候補に表示されることを確認する。

## 3. DifyテキストKBを作成する

1. Dify管理画面で「ナレッジ」または「Knowledge」を開く。
2. 新しいテキストKBを作成する。
3. 埋め込みモデルに、手順2で登録したOllamaのText Embeddingモデルを選択する。
4. 検索設定で hybrid search を有効化し、weighted score による関連度並べ替えを使う。
5. 空KBのままでよいので保存する。

このKBには後続taskの `scripts/register_multimodal_kb.py` が、画像1件につき1ドキュメントとしてキャプション本文とimgpush filenameを登録する。

## 4. Dataset APIキーとdataset idを控える

1. Dify管理画面でDataset APIキーを発行する。
2. 作成したテキストKBの dataset id を確認する。
3. `docker/.env` に以下を設定する。

```env
DIFY_DATASET_API_KEY=<dataset-api-key>
MULTIMODAL_RAG_DATASET_ID=<dataset-id>
MULTIMODAL_RAG_CAPTION_MODEL=<vision-model>
```

`MULTIMODAL_RAG_CAPTION_MODEL` は、手順2でDifyに登録したキャプション用Ollama Visionモデル名と一致させる。

## 5. Dataset API疎通を確認する

リポジトリルートで以下を実行する。

```powershell
python scripts/check_multimodal_rag_setup.py
```

`docker/.env` の `DIFY_API_BASE_URL` がコンテナ内URL `http://dify-api:5001/v1` の場合、この検証CLIはホストから到達できる `http://127.0.0.1:${DIFY_API_PORT}/v1` を自動で使う。明示したい場合は次のように指定する。

```powershell
python scripts/check_multimodal_rag_setup.py --api-base-url http://127.0.0.1:5001/v1
```

成功条件:
- 必須環境変数 `DIFY_DATASET_API_KEY`、`MULTIMODAL_RAG_DATASET_ID`、`MULTIMODAL_RAG_CAPTION_MODEL` が未入力ではない
- Dataset APIキーで `MULTIMODAL_RAG_DATASET_ID` のKBへアクセスできる
- Difyデバッグ画面で、空KBに対するテキストクエリがエラーなく実行できる

CLIが `OK: multimodal-rag のDify Dataset API設定に疎通しました。` を出力すれば、task 2 のAPI疎通条件を満たしている。
