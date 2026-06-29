# Implementation Plan

> 注: 本機能はDify管理画面でのモデル登録・マルチモーダルKB作成・アプリインポート・APIキー発行といったコード化できない技術セットアップを伴う。タスク2（互換性スパイク）が最大リスク（Xinference×Dify v1.11マルチモーダルKB互換）の検証ゲートであり、これを通過しないとタスク4以降の自鯖内検索が成立しない。非互換時は design/requirements へ戻る（research.md 代替策参照）。

- [x] 1. Foundation: Xinference サービスと環境変数の追加
  - `docker-compose.yml` に Xinference サービスを追加し `agentplatform-net` 接続・GPU割当・モデルキャッシュ永続ボリューム・`127.0.0.1:${XINFERENCE_PORT}:9997` を定義（既存サービス定義は変更しない）
  - `.env.example` に本機能の新規環境変数（`XINFERENCE_PORT`・`IMGPUSH_BROWSER_BASE_URL`・`DIFY_MULTIMODAL_RAG_APP_API_KEY`・`DIFY_DATASET_API_KEY`・`MULTIMODAL_RAG_DATASET_ID`）を追加し、モデル/KBはDify管理画面で設定する旨をコメント明記
  - 観測可能な完了条件: `docker compose up` 後 `xinference` が `agentplatform-net` で起動し、`GET http://127.0.0.1:${XINFERENCE_PORT}/` が応答する
  - _Requirements: 2.1, 2.2, 2.3, 3.1_
  - _Boundary: Xinference Service_

- [ ] 2. Foundation: Dify マルチモーダルKB 互換性スパイクとKB構築
  - Xinference にマルチモーダル埋め込みモデルと vision rerank モデルをロードし、Dify にプロバイダ登録する
  - Visionタグ付きマルチモーダルKBを作成し、少数のサンプル画像（Markdownリンク経由）を登録する
  - Difyデバッグ実行で text→image / image→image / image→text のクロスモーダル検索とマルチモーダルRerankingが機能することを確認する
  - Dataset APIキーを発行し、作成したKBの dataset id を記録する（`DIFY_DATASET_API_KEY`・`MULTIMODAL_RAG_DATASET_ID` に設定）
  - 観測可能な完了条件: 3方向クロスモーダル検索とRerankの動作確認結果（成否・採用モデルID・代替判断）を `research.md` に追記し、非互換なら停止して design へ戻す
  - _Requirements: 2.1, 2.2, 2.3, 3.1_
  - _Boundary: Multimodal KB, Xinference Service_
  - _Depends: 1_

- [ ] 3. (P) Foundation: 共有imgpushクライアントと画像バリデーション
  - 画像バイトを imgpush へアップロードし、internal/browser/public の3スコープURLと filename を組み立てる共有クライアントを実装する（public は未設定時 None）
  - JPG/PNG/GIF 以外、または 2MB 超を拒否する画像バリデーションを実装する
  - 単体テストで URL組み立て・形式/サイズ違反の拒否・imgpush接続エラーの送出を検証する
  - 観測可能な完了条件: モックimgpush応答から3スコープURLを正しく返し、非対応形式/2MB超で検証エラー、接続失敗で例外を送出する単体テストが通る
  - _Requirements: 1.1, 2.2_
  - _Boundary: ImgpushClient_
  - _Depends: 1_

- [ ] 4. (P) Core: multimodal_rag ワークフロー（自鯖内KB検索）
  - Dify workflowモードのDSLを作成し、Start（テキスト＋任意画像入力）→ Knowledge Retrieval（マルチモーダルKB・query/query_images・multimodal rerank）→ 正規化Code → 0件分岐 → LLM要約 → End（構造化出力 count/items/summary）を構成する
  - 正規化Codeで検索結果と画像添付を共通アイテム（filename/title/text/source/score）へ変換し、Rerank順を保持して件数を算出する
  - インポート後に KB・rerankモデル・LLMノードのOllamaモデルを設定し、リクエストにユーザー識別情報を含めない
  - 観測可能な完了条件: `POST /v1/workflows/run` 呼び出しが count/items/summary を返し、1件以上時に正規化アイテムと要約、0件時に空出力（count=0）を返す
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.3, 5.2_
  - _Boundary: MultimodalRAG Workflow_
  - _Depends: 2_

- [ ] 5. (P) Core: マルチモーダルKB 登録スクリプト
  - 指定ディレクトリ内の画像を走査し、共有クライアントで形式/サイズを検証する（違反はスキップしログ通知、他画像の登録は継続）
  - 検証通過画像を imgpush（internal）へアップロードし、画像Markdownリンクと filename/メタデータを含む文書を生成して Dify Dataset API で登録する
  - filename/コンテンツハッシュで登録済みを判定してスキップし、再実行で未登録分のみ処理する冪等性を担保する（Dataset API/imgpush エラーは捕捉しメッセージ＋非0終了）
  - 観測可能な完了条件: モックで不正画像をスキップし正常画像のみ Dataset API を呼ぶこと、再実行で登録済みをスキップすることを単体テストで確認できる
  - _Requirements: 1.1, 1.2, 1.3, 5.3_
  - _Boundary: Register Script_
  - _Depends: 2, 3_

- [ ] 6. Core: multimodal_rag Pipeline（中継・フォールバック制御）
- [ ] 6.1 自鯖内検索の中継と結果提示
  - Open WebUIメッセージからテキストと任意画像を抽出し、両方無い場合は入力を促すメッセージを返す
  - 画像がある場合は共有クライアントで imgpush（internal）へアップロードし、ワークフロー実行へ画像入力（remote_url）を渡す
  - ワークフローを実行し、`count>=1` のとき browser URL でサムネイルMarkdownを組み立て、関連情報＋要約を統一フォーマットで返す（外部送信・通知なし）
  - 観測可能な完了条件: モックで（a）入力なし→促し、（b）テキスト/画像で count>=1→サムネイル＋関連情報＋要約を外部送信・通知なしで返す、をテストで確認できる
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.2, 3.3, 3.4, 4.1, 5.1_
  - _Boundary: MultimodalRAG Pipeline_
  - _Depends: 3, 4_

- [ ] 6.2 フォールバック制御と通知・エラー処理
  - `count==0` かつ画像ありのとき public URL を確保して `reverse_image_search` ワークフローを発火し、フォールバック通知＋外部送信通知を応答先頭に前置する
  - `count==0` かつ画像なしのときは見つからなかった旨を返す（フォールバック不可）
  - imgpush/Dify 接続失敗等の例外を捕捉し、例外を伝播せずユーザー向けエラーメッセージを返す
  - 観測可能な完了条件: モックで画像 count==0→両通知付きでWeb結果を返す、テキストのみ count==0→見つからない旨、例外→エラー文字列、を返すことをテストで確認できる
  - _Requirements: 4.2, 4.3, 4.4, 4.5, 5.2, 5.3_
  - _Boundary: MultimodalRAG Pipeline_
  - _Depends: 6.1_

- [ ] 6.3 Pipeline のモデル登録確認
  - Pipeline を pipelines ランタイムへ登録し、`count>=1` 経路で imgpush public/SerpAPI を呼ばない不変条件をテストで担保する
  - 観測可能な完了条件: `docker compose restart pipelines` 後 `GET /models` に `multimodal_rag` が含まれ、自鯖内充足経路で外部送信が発生しないテストが通る
  - _Requirements: 4.1, 4.2_
  - _Boundary: MultimodalRAG Pipeline_
  - _Depends: 6.1, 6.2_

- [ ] 7. Integration: セットアップ手順とエンドツーエンド配線
  - Xinferenceモデル登録・Difyプロバイダ設定・マルチモーダルKB作成（Visionタグ）・Dataset APIキー発行・ワークフローインポート・モデル設定・画像登録・互換性スパイクの再現手順を技術セットアップガイドとして整備する
  - 環境変数（タスク1で追加した各キー）と各アプリAPIキーの設定値を結線し、Pipeline → ワークフロー → KB → Xinference、およびフォールバック → reverse_image_search の経路を疎通させる
  - 観測可能な完了条件: ガイドに従ってクリーン環境から設定でき、登録済みKBに対する自鯖内検索とフォールバックの双方が疎通する
  - _Requirements: 1.3, 2.1, 2.2, 2.3, 4.5_
  - _Depends: 1, 2, 4, 5, 6.3_

- [ ] 8. Validation: 統合・E2E テスト
  - Open WebUI から `multimodal_rag` を選択し、テキスト検索→自鯖内サムネイル＋要約（外部送信通知なし）、画像検索→類似画像/関連情報、を確認する
  - 自鯖内に無い画像→フォールバック通知＋外部送信通知＋Web結果、入力なし→促し、`dify-api` 停止→エラーメッセージ、を確認する
  - Phase 0スパイクの3方向クロスモーダル検索＋Rerank、登録スクリプトの不正画像スキップ/冪等再実行、を統合テストで再確認する
  - 観測可能な完了条件: 上記すべてのE2Eシナリオが想定どおりの応答を返し、自鯖内充足時に外部送信が発生しないことを確認できる
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3_
  - _Depends: 5, 6.3, 7_
