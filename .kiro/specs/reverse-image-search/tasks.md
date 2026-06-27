# Implementation Plan

- [ ] 1. Foundation: 環境変数・imgpushサービス・画像アップロードヘルパーの準備
- [x] 1.1 docker/.env.exampleへの環境変数追加
  - `docker/.env.example`に`IMGPUSH_PORT`（imgpushのホスト公開ポート）・`IMGPUSH_INTERNAL_URL`（既定`http://imgpush:5000`、Pipelineからのアップロード先）・`IMGPUSH_PUBLIC_BASE_URL`（オペレーター提供の公開ベースURL、初期値は空欄）・`DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY`（ワークフローのAPIキー、初期値は空欄）をコメント付きで追加する
  - `SERPAPI_KEY`（Secret）と`REVERSE_IMAGE_ENGINE`（既定`google_lens`）はDify管理画面で環境変数として設定する旨を`.env.example`にコメントで明記し、値は置かない
  - 観測可能完了: `docker/.env.example`をコピーして作成した`docker/.env`に上記4変数が存在し、`git status`で`docker/.env`が追跡対象外であることが確認できる
  - _Requirements: 1.1, 1.2, 4.3_

- [ ] 1.2 docker-compose.ymlへのimgpushサービス追加
  - `docker/docker-compose.yml`に`imgpush`サービス（`hauxir/imgpush`イメージ）を追加し、`agentplatform-net`に接続、画像永続化ボリューム（`imgpush-data`→`/images`）と`127.0.0.1:${IMGPUSH_PORT}:5000`を定義する。既存サービス定義は変更しない
  - 観測可能完了: `docker compose up`後に`curl http://127.0.0.1:${IMGPUSH_PORT}/liveness`が200を返し、サンプル画像を`POST /`した応答の`filename`を`GET /<filename>`で取得できる
  - _Requirements: 1.1_
  - _Boundary: imgpush Service_

- [ ] 1.3 画像アップロードヘルパー（ImgpushUploader）の実装
  - `pipelines/image_uploader.py`に`ImgpushUploader`クラスを実装し、`upload(image_bytes, mime_type)`がimgpushの`POST /`（multipart、フィールド名`file`）を呼び出して応答`{"filename": ...}`と公開ベースURLから公開URL`f"{base}/{filename}"`（末尾スラッシュ正規化）を組み立てて返す
  - 公開ベースURLが空の場合は`ValueError`、imgpush接続・タイムアウト・非2xxは`requests.exceptions.RequestException`を送出し、エラーメッセージへの変換は呼び出し元に委ねる。imgpushへユーザー識別情報を付与しない。Open WebUIメッセージ形式には依存しない（入力は画像バイトとMIMEのみ）
  - 観測可能完了: モックしたimgpush応答`{"filename": "abc.jpg"}`に対し`upload()`が`<base>/abc.jpg`を返すこと、公開ベースURL空で`ValueError`、接続エラーで`RequestException`を送出することをユニットテストで確認できる
  - _Requirements: 1.1, 4.3_
  - _Boundary: ImgpushUploader_

- [ ] 2. Core: 逆画像検索ワークフローとPipelineの実装
- [ ] 2.1 (P) reverse_image_searchワークフローの作成
  - `workflows/reverse_image_search.yml`に、Start→HTTP Request（SerpAPI `engine={{#env.REVERSE_IMAGE_ENGINE#}}`、`url`/`image_url`両方に`{{#sys.query#}}`、`api_key={{#env.SERPAPI_KEY#}}`を`params`で構成）→Code（`REVERSE_IMAGE_ENGINE`に応じて`visual_matches`/`image_results`・`inline_images`/Yandex類似画像配列を共通形式`{title, link, source, thumbnail}`へ正規化し、上位5件の`![](thumbnail)`形式Markdownと件数を算出、`thumbnail`欠落項目はスキップ、`error`検出時は0件相当）→If-Else（0件分岐）→LLM（要約・`[出典: source](link)`付与）/Answer（0件時の再検索を促す通知文）→Answer（Markdown画像＋出典＋要約）という構成のDify advanced-chat DSLを作成する
  - `SERPAPI_KEY`はSecret環境変数として参照しDSL・`docker/.env`に値を置かない。SerpAPIへのリクエストにユーザー識別情報を含めない。正規化以降のノードはエンジン非依存に保つ
  - 観測可能完了: `workflows/reverse_image_search.yml`をDifyにインポートし、SerpAPIのモック/実応答に対するデバッグ実行で、1件以上時にMarkdown画像＋出典＋要約、0件時に再検索を促す通知文が返ることを確認できる
  - _Requirements: 1.2, 2.1, 2.2, 2.3, 4.2, 4.3_
  - _Boundary: ReverseImageSearch Workflow_

- [ ] 2.2 (P) ReverseImageSearch Pipelineの実装
  - `pipelines/reverse_image_search_bridge.py`に`Pipeline`クラス（`self.id = "reverse_image_search"`、`Valves`に`DIFY_API_BASE_URL`・`DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY`・`IMGPUSH_INTERNAL_URL`・`IMGPUSH_PUBLIC_BASE_URL`・`REQUEST_TIMEOUT_SECONDS`）を実装する。`pipe()`は直近メッセージから画像（`image_url` data URI）を抽出し、`ImgpushUploader.upload()`で公開URLを取得後、`DifyChatBridge.ask(query=公開URL, user_id)`でワークフローへ中継する
  - 画像を検知して外部処理へ進む全経路（成功/0件/エラー）で固定のプライバシー通知文を応答先頭に前置する（同意操作なし・非ブロッキング）。画像未検出時はimgpush/Difyを呼ばず画像添付を促すメッセージを返す。`ValueError`（公開URL未設定/画像デコード不正）・`requests.exceptions.RequestException`（imgpush/Dify接続失敗）を捕捉し、例外を再raiseせず通知＋エラーメッセージ文字列を返す。imgpush/SerpAPIへユーザー識別情報を付与しない
  - 観測可能完了: `docker compose restart pipelines`後、`curl http://127.0.0.1:${PIPELINES_PORT}/models`のレスポンスに`reverse_image_search`が含まれる。モックで(a)画像→`upload`と`ask`呼び出し＋通知前置、(b)画像なし→添付促し（imgpush/Dify未呼び出し）、(c)imgpush/Dify例外→通知＋エラーメッセージ文字列、をユニットテストで確認できる
  - _Requirements: 1.1, 1.2, 1.3, 3.1, 3.2, 4.1, 4.3_
  - _Boundary: ReverseImageSearch Pipeline_
  - _Depends: 1.3_

- [ ] 3. Integration & Validation: セットアップ手順とEnd-to-End確認
- [ ] 3.1 セットアップ手順書の作成
  - `docs/reverse-image-search-setup.md`に、(1) imgpushを公開到達可能にする設定（`IMGPUSH_PUBLIC_BASE_URL`の用意、Cloudflare Tunnel等の代表例、画像が外部公開され蓄積する旨と定期削除の注意）、(2) `workflows/reverse_image_search.yml`のDifyへのインポート・公開・APIキー発行手順（発行キーを`docker/.env`の`DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY`へ設定）、(3) Dify管理画面でのSecret環境変数`SERPAPI_KEY`と環境変数`REVERSE_IMAGE_ENGINE`（`google_lens`/`yandex_images`/`bing_reverse_image`）・LLMノードのモデル設定、(4) `pipelines`コンテナ再起動とOpen WebUIでの`reverse_image_search`モデル登録手順、(5) imgpush疎通確認（`/liveness`・サンプルPOST/GET）を記載する
  - 観測可能完了: `docs/reverse-image-search-setup.md`が作成され、上記5手順が`docker/.env`およびDify環境変数の対応する変数名を明記した形で記載されている
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 4.1, 4.2, 4.3_
  - _Depends: 1.1, 1.2, 1.3, 2.1, 2.2_

- [ ] 3.2 逆画像検索End-to-End確認（既定エンジン）
  - `docs/reverse-image-search-setup.md`の手順に従い既定`REVERSE_IMAGE_ENGINE=google_lens`で、Open WebUIのチャットで`reverse_image_search`モデルを選択し、(a) 画像を添付して送信し、プライバシー通知＋類似画像サムネイル＋出典＋要約が表示されること、(b) 類似画像が見つからない画像で再検索を促す通知が表示されること、(c) 画像を添付せず送信して添付を促すメッセージが表示されること、(d) `dify-api`停止またはimgpush到達不可状態でエラーメッセージが表示されることを確認する
  - 観測可能完了: Open WebUIのチャット画面で、通知＋画像一覧＋出典＋要約・0件通知・画像未提供メッセージ・接続エラーメッセージの4パターンがそれぞれ表示される
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 4.1, 4.2, 4.3_
  - _Depends: 3.1_

- [ ] 3.3 エンジン切替確認（Yandex / Bing）
  - `REVERSE_IMAGE_ENGINE`を`yandex_images`・`bing_reverse_image`に切替えた各状態で、同一画像に対するチャット送信またはDifyデバッグ実行で、各エンジンの応答が共通形式へ正規化され、1件以上時にMarkdown画像＋出典＋要約、0件時に再検索通知が表示されることを確認する。`url`/`image_url`同時送信が各エンジンで無視されることを併せて確認する
  - 観測可能完了: `yandex_images`・`bing_reverse_image`の各設定で、コード編集なしに切替えた結果が共通形式で表示される（少なくとも1件以上の結果表示と0件通知の双方を確認）
  - _Requirements: 1.2, 2.1, 2.2, 2.3, 4.2_
  - _Depends: 3.1_
