# Implementation Plan

> 注: 本機能は新規サービスコンテナを追加しない（**Xinferenceは不採用**）。既存 Ollama（Vision/埋め込み/要約）と imgpush を再利用し、「画像→画像」の**完全一致・視覚酷似はローカルのハッシュ照合**（SHA-256／pHash）、**内容の意味的関連は caption 方式テキストKB**で実現する。Dify管理画面でのテキストKB作成・モデル設定・アプリインポート・APIキー発行といったコード化できない技術セットアップを伴う（タスク2・タスク8）。Phase 0スパイクの結果（Xinference非互換）と方針転換の根拠は `research.md` を参照。

- [x] 1. Foundation: Xinference成果物の撤去と本機能の環境変数・依存の整備
  - `docker/docker-compose.yml` から `xinference` サービス定義と `xinference-data` ボリュームを削除する（他サービス定義は変更しない）
  - `docker/.env.example` から `XINFERENCE_PORT` と Xinference 前提のコメントを削除し、`MULTIMODAL_RAG_CAPTION_MODEL`・`MULTIMODAL_RAG_HASH_INDEX_PATH`・`MULTIMODAL_RAG_PHASH_MAX_DISTANCE` を追記する（`IMGPUSH_BROWSER_BASE_URL`・`DIFY_MULTIMODAL_RAG_APP_API_KEY`・`DIFY_DATASET_API_KEY`・`MULTIMODAL_RAG_DATASET_ID` は既存を流用）。モデル/KBはDify管理画面で設定する旨をコメント明記
  - pipelines ランタイムの依存宣言に `Pillow`・`imagehash` を追加し、ハッシュ副インデックスを登録スクリプトと pipelines コンテナで共有するパスを確定する（既存バインドマウント配下で compose 無改変が可能か確認し、不可なら読み取り可能マウントを1つ追加）
  - 旧 Xinference 疎通を主張する `tests/test_multimodal_rag_infrastructure.py` を撤去または caption＋ハッシュ構成向けに置き換える（Xinferenceの存在を前提とするテストを残さない）
  - 観測可能な完了条件: `docker compose config` が `xinference` を含まず正常解決し、`.env.example` に本機能の新規変数が揃い、pipelines 依存に `Pillow`/`imagehash` が含まれ、Xinference前提テストが存在しない
  - _Requirements: 2.5, 3.1_
  - _Boundary: docker config, pipelines deps_

- [x] 2. Foundation: DifyテキストKBとOllamaモデルのセットアップ・Dataset APIキー発行
  - Ollama に キャプション用 Vision モデル・テキスト埋め込みモデル・要約用チャットモデルを用意し、Dify にプロバイダ登録して利用可能にする
  - Dify管理画面で（Ollama埋め込みを用いる）テキストKBを作成し、hybrid/weighted score による関連度並べ替えを有効化する
  - Dataset APIキーを発行して作成KBの dataset id を記録し、キャプションモデル名とともに `.env` へ設定する（`DIFY_DATASET_API_KEY`・`MULTIMODAL_RAG_DATASET_ID`・`MULTIMODAL_RAG_CAPTION_MODEL`）
  - 観測可能な完了条件: Difyデバッグでテキストクエリが（空KBに対しても）エラーなく実行でき、Dataset API がキーで疎通し、dataset id とモデル設定が `.env` に記録される
  - _Requirements: 1.3, 2.1, 2.2, 2.3, 3.1_
  - _Depends: 1_

- [x] 3. (P) Core: 共有imgpushクライアントと画像バリデーション
  - 画像バイトを imgpush へアップロードし、internal/browser/public の3スコープURLと filename を組み立てる共有クライアントを実装する（public は未設定時 None）
  - JPG/PNG/GIF 以外、または 2MB 超を拒否する画像バリデーションを実装する
  - 単体テストで URL組み立て・形式/サイズ違反の拒否・imgpush接続エラーの送出を検証する
  - 観測可能な完了条件: モックimgpush応答から3スコープURLを正しく返し、非対応形式/2MB超で検証エラー、接続失敗で例外を送出する単体テストが通る
  - _Requirements: 1.1, 2.2_
  - _Boundary: ImgpushClient_
  - _Depends: 1_

- [x] 4. (P) Core: ローカル画像ハッシュ索引（完全一致・準一致）
  - 画像バイトから SHA-256（完全一致キー）と知覚ハッシュ pHash/dHash（準一致キー）を算出する
  - 副インデックス（初期JSON、件数増でSQLite化を検討）の読み書きを実装する（ファイル不在は空として扱い、書き込みはアトミック、同一SHAは追記しない冪等）
  - 画像クエリに対し完全一致（exact・distance0）を先頭、準一致（ハミング距離 ≤ 閾値）を距離昇順で返す検索を実装する
  - 単体テストで 完全一致・準一致（リサイズ/再圧縮）・非該当・add冪等・索引不在時の空扱いを検証する
  - 観測可能な完了条件: 同一画像で完全一致、軽微加工画像で準一致がヒットし、無関係画像がヒットせず、同一SHAの二重追記がされない単体テストが通る
  - _Requirements: 2.5, 3.1, 5.3_
  - _Boundary: ImageHashIndex_
  - _Depends: 1_

- [x] 5. (P) Core: multimodal_rag ワークフロー（キャプション化＋テキストKB検索）
  - Dify workflowモードのDSLを作成し、Start（テキスト＋任意画像）→[画像時]Vision LLMでクエリ画像キャプション化→クエリ統合→Knowledge Retrieval（テキストKB・hybrid/weighted）→正規化Code→0件分岐→LLM要約→End（構造化出力 count/items/summary）を構成する
  - 正規化Codeで検索結果を共通アイテム（filename/title/text/source/score）へ変換し、関連度順を保持して件数を算出する。テキストのみ入力時は Vision ノードを空処理でスキップする
  - インポート後に Vision/埋め込み/要約の各OllamaモデルとテキストKBを設定し、リクエストにユーザー識別情報を含めない
  - 観測可能な完了条件: `POST /v1/workflows/run` が count/items/summary を返し、画像入力時にキャプションが検索クエリへ反映され、1件以上で正規化アイテムと要約、0件で空出力（count=0）を返す
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.3, 5.2_
  - _Boundary: MultimodalRAG Workflow_
  - _Depends: 2_

- [x] 6. Core: マルチモーダルKB登録スクリプト（ハッシュ＋キャプション）
  - 指定ディレクトリ内の画像を走査・検証する（違反はスキップしログ通知、他画像の登録は継続）
  - SHA-256/pHash を算出し、SHA既存なら登録済みスキップ（冪等）。未登録画像を imgpush（internal）へアップロードする
  - Ollama Vision で日本語キャプションを生成し、キャプション＋画像Markdownリンク＋filename/メタデータの文書を Dify Dataset API で登録する。登録成功後に副インデックスへ `{filename, sha256, phash, title}` を追記する（登録失敗時は索引に追記しない）
  - 単体テストで 不正画像スキップ・正常画像のハッシュ算出＋キャプション＋Dataset API呼び出し＋索引追記・再実行スキップを検証する
  - 観測可能な完了条件: モックで不正画像をスキップし正常画像のみ Dataset API 登録＋索引追記、再実行で登録済みをスキップする単体テストが通る
  - _Requirements: 1.1, 1.2, 1.3, 2.5, 5.3_
  - _Boundary: Register Script_
  - _Depends: 2, 3, 4_

- [ ] 7. Core: multimodal_rag Pipeline（ハッシュ統合・中継・フォールバック制御）
- [x] 7.1 ハッシュ照合と自鯖内検索の統合・結果提示
  - Open WebUIメッセージからテキストと任意画像を抽出し、両方無い場合は入力を促すメッセージを返す
  - 画像がある場合は ImageHashIndex で完全/準一致を照合し、並行して imgpush（internal）へアップロードしてワークフローへ画像入力（remote_url）を渡す
  - `total = ハッシュ一致数 + workflow count` を算出。ハッシュ一致（完全→準一致）を最上位、続いてKB意味検索アイテムを並べ、同一filenameの重複はハッシュ側優先で除去。browser URL でサムネイルMarkdownを組み立て、関連情報＋要約を統一フォーマットで返す（外部送信・通知なし）。索引読込失敗は空一致としてKB検索を継続する
  - 観測可能な完了条件: モックで（a）入力なし→促し、（b）画像ハッシュ完全一致→当該画像を最上位に外部送信なしで提示、（c）テキスト/画像で total>=1→サムネイル＋関連情報＋要約、をテストで確認できる
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 4.1, 5.1_
  - _Boundary: MultimodalRAG Pipeline_
  - _Depends: 3, 4, 5_

- [x] 7.2 フォールバック制御と通知・エラー処理
  - `total==0` かつ画像ありのとき public URL を確保して `reverse_image_search` ワークフローを発火し、フォールバック通知＋外部送信通知を応答先頭に前置する
  - `total==0` かつ画像なしのときは見つからなかった旨を返す（フォールバック不可）
  - imgpush/Dify 接続失敗等の例外を捕捉し、例外を伝播せずユーザー向けエラーメッセージを返す
  - 観測可能な完了条件: モックで 画像 total==0→両通知付きでWeb結果を返す、テキストのみ total==0→見つからない旨、例外→エラー文字列、を返すことをテストで確認できる
  - _Requirements: 4.2, 4.3, 4.4, 4.5, 5.2, 5.3_
  - _Boundary: MultimodalRAG Pipeline_
  - _Depends: 7.1_

- [ ] 7.3 Pipeline のモデル登録確認と外部送信ゼロ不変条件
  - Pipeline を pipelines ランタイムへ登録し、pipelines コンテナからハッシュ副インデックスパスが読めることを確認する
  - `total>=1`（ハッシュ一致 or KB充足）経路で imgpush public/SerpAPI を呼ばない不変条件をテストで担保する
  - 観測可能な完了条件: `docker compose restart pipelines` 後 `GET /models` に `multimodal_rag` が含まれ、自鯖内充足経路で外部送信が発生しないテストが通る
  - _Requirements: 4.1, 4.2_
  - _Boundary: MultimodalRAG Pipeline_
  - _Depends: 7.1, 7.2_

- [ ] 8. Integration: セットアップ手順とエンドツーエンド配線
  - Ollamaモデル用意・DifyテキストKB作成・Dataset APIキー発行・ハッシュ副インデックス共有パス設定・ワークフローインポート・モデル設定・画像登録（ハッシュ＋キャプション）の再現手順を技術セットアップガイドとして整備する
  - 環境変数（タスク1で整備した各キー）と各アプリAPIキーを結線し、Pipeline → ハッシュ索引 / ワークフロー → テキストKB → Ollama、およびフォールバック → reverse_image_search の経路を疎通させる
  - 観測可能な完了条件: ガイドに従ってクリーン環境から設定でき、登録済みKB/索引に対する自鯖内検索（完全一致・準一致・意味関連）とフォールバックの双方が疎通する
  - _Requirements: 1.3, 2.1, 2.2, 2.3, 2.5, 4.5_
  - _Depends: 1, 2, 5, 6, 7.3_

- [ ] 9. Validation: 統合・E2E テスト
  - Open WebUIから `multimodal_rag` を選択し、テキスト検索→自鯖内サムネイル＋要約（外部送信通知なし）、登録画像そのもの→完全一致が最上位（Webフォールバックしない）、軽微加工版→準一致、画像→内容関連画像/関連情報、を確認する
  - 自鯖内に無い画像→フォールバック通知＋外部送信通知＋Web結果、入力なし→促し、`dify-api` 停止→エラーメッセージ、を確認する
  - 登録スクリプト→索引→Pipeline照合の一気通貫（完全一致/準一致）、登録スクリプトの不正画像スキップ/冪等再実行、を統合テストで再確認する
  - 観測可能な完了条件: 上記すべてのE2Eシナリオが想定どおりの応答を返し、自鯖内充足時（ハッシュ一致を含む）に外部送信が発生しないことを確認できる
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3_
  - _Depends: 6, 7.3, 8_
