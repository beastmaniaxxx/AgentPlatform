# multimodal-rag 互換性スパイク手順

この手順は `multimodal-rag` タスク2の手動検証ゲートである。目的は、Xinference が提供するローカルのマルチモーダル埋め込みモデルと vision rerank モデルを Dify の Visionタグ付きマルチモーダルKBで利用できるかを確認すること。

完了後は `.kiro/specs/multimodal-rag/research.md` の「Phase 0 互換性スパイク結果」に結果を記録する。3方向の検索と Rerank が確認できるまで、タスク2は完了扱いにしない。

## 前提

- `docker/` で `docker compose up -d xinference dify-api dify-web imgpush` が実行済みであること
- `http://127.0.0.1:${XINFERENCE_PORT}/` が HTTP 200 を返すこと
- Dify 管理画面へログインできること
- Dify から Xinference へは `http://xinference:9997` で到達させること
- サンプル画像は JPG/PNG/GIF、最大2MBに収めること

## 1. Xinference でモデルをロードする

Xinference の管理画面または CLI で、以下の2種類のモデルをロードする。

| 用途 | 例 | 記録する値 |
|------|----|------------|
| マルチモーダル埋め込み | CLIP / SigLIP / Jina CLIP 系 | embedding model id |
| vision rerank | Jina reranker 系など Vision タグ対応候補 | rerank model id |

ロード後、モデル名、モデルタイプ、エンドポイント、VRAM使用量の概算を控える。

## 2. Dify に Xinference プロバイダを登録する

1. Dify 管理画面で「設定」→「モデルプロバイダー」を開く。
2. Xinference または OpenAI互換のプロバイダ設定を追加する。
3. Base URL に `http://xinference:9997` を設定する。
4. タスク2でロードした埋め込みモデルと rerank モデルを Dify 側で選択できるか確認する。

Dify のモデル一覧で Vision タグ付きマルチモーダルKBに利用できない場合は、その時点で非互換候補として記録する。

## 3. Visionタグ付きマルチモーダルKBを作成する

1. Dify 管理画面で新しい Knowledge Base を作成する。
2. マルチモーダル検索が有効な設定を選ぶ。
3. 埋め込みモデルに Xinference 側のマルチモーダル埋め込みモデルを指定する。
4. Rerank に Xinference 側の vision rerank モデルを指定する。
5. Visionタグ付きマルチモーダルKBとして保存できることを確認する。

## 4. サンプル画像を登録する

少数の画像を imgpush にアップロードし、MarkdownリンクとしてKBに登録する。

```powershell
curl.exe -F "file=@.\sample.jpg" http://localhost:5100/
```

返却された `filename` を使い、KB文書本文に以下の形式で登録する。

```markdown
# sample-1

![sample-1](http://imgpush:5000/<filename>)

説明: 画像の内容を短く記載する。
ファイル名: <filename>
```

登録後、Dify 側でインデックス作成が完了することを確認する。

## 5. Dify デバッグで3方向検索を確認する

Dify のデバッグ実行で以下を確認する。

| ケース | 入力 | 合格条件 |
|--------|------|----------|
| text→image | 画像内容を表すテキスト | 関連画像が取得され、画像が結果に含まれる |
| image→image | 登録済み画像または類似画像 | 類似画像が上位に返る |
| image→text | 画像入力のみ | 画像に紐づく説明テキストが取得される |
| Rerank | 複数候補が出る入力 | 関連度の高い候補が上位に並ぶ |

各ケースについて、検索結果件数、上位結果、score、エラー有無を記録する。

## 6. Dataset API キーと Dataset ID を記録する

Dify 管理画面で Dataset API キーを発行し、作成したKBの dataset id と合わせて `docker/.env` に設定する。

```env
DIFY_DATASET_API_KEY=<dataset-api-key>
MULTIMODAL_RAG_DATASET_ID=<dataset-id>
```

値そのものはリポジトリにコミットしない。`research.md` には値ではなく、発行済みかどうかと保存場所だけを記録する。

## 7. research.md へ結果を追記する

`.kiro/specs/multimodal-rag/research.md` の「Phase 0 互換性スパイク結果」に以下を記録する。

- 実施日
- 実施状態
- 採用モデルID
- text→image / image→image / image→text / Rerank の成否
- Dataset API キーと Dataset ID の発行有無
- 代替判断
- 次アクション

3方向検索または Rerank のいずれかが失敗した場合は、タスク4以降へ進まず、design/requirements に戻って代替案を選ぶ。
