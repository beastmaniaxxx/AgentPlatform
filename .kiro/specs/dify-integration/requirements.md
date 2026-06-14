# Requirements Document

## Project Description (Input)
個人開発者として、Open WebUIのチャット入力をDifyワークフローへ中継し、Difyが各種バックエンド（SearXNG、ComfyUI、外部API等）をオーケストレーションできるようにしたい。

現状、`infrastructure` SpecによりOpen WebUI・Ollama・SearXNGがDocker Compose上で連携動作する基盤は構築済みだが、DifyコンテナおよびOpen WebUI ↔ Dify のPipeline中継は未構築であり、後続のすべての機能Spec（web-search、image-generation、reverse-image-search、instagram-search、multimodal-rag）が着手できない状態にある。

これを解消するため、`docker-compose.yml` にDifyサービス群（v1.11以降、マルチモーダルRAG対応版）を追加し、`pipelines/dify_bridge.py`（Open WebUI ↔ Dify中継）を実装する。`DIFY_BASE_URL` と `DIFY_KEY` を環境変数化し、DifyからOllama（OpenAI互換API）への接続をGUI設定で完了させ、Open WebUI管理画面からPipelineをアップロードして疎通確認を行う。また、base64画像をOpen WebUIから受け取り、後続Spec（逆画像検索等）で使えるようPipeline側で前処理できる構成とする。

個別の機能ワークフロー（web_search.yml等）やComfyUI/imgpush等の追加サービスは各機能Specの範囲とし、本Specには含まない。

## Boundary Context

- **In scope**: Difyサービス群の追加と既存Dockerネットワークへの統合、Open WebUIとDify間のテキスト・画像メッセージ中継、Dify接続先URL・APIキーの環境変数化、DifyからOllamaへのモデル接続設定手順、中継経路のEnd-to-End疎通確認に必要な最小限の検証用Difyワークフロー
- **Out of scope**: 各機能Spec固有のDifyワークフロー（web_search等）の作成、ComfyUI・imgpush等の追加サービスの導入、base64画像のURL変換処理（imgpush連携は `reverse-image-search` Specで対応）
- **Adjacent expectations**: 後続の機能Spec（web-search、image-generation、reverse-image-search、instagram-search、multimodal-rag）は、本Specが提供する中継経路・接続設定・環境変数の枠組みを前提として、それぞれ専用のDifyワークフローを追加する。`infrastructure` Specが構築したDockerネットワーク・ボリューム構成を変更せずに利用する

## Requirements

### Requirement 1: Difyサービス群の追加とネットワーク統合

**Objective:** 個人開発者として、Difyワークフローエンジンを既存のDocker環境に統合したい。それにより、後続の機能Specがワークフローベースで機能を実装できる基盤を得る。

#### Acceptance Criteria

1. When 個人開発者がDocker Compose環境を起動したとき、the Dify統合基盤 shall Difyの動作に必要なサービス群を起動する。
2. The Dify統合基盤 shall Difyのサービス群を、既存のOpen WebUI・Ollama・SearXNGと同一のDockerネットワーク上でコンテナ名による名前解決により相互通信できる状態で提供する。
3. The Dify統合基盤 shall Difyの設定・データをコンテナ再起動後も保持する永続化領域を提供する。

### Requirement 2: Open WebUIからDifyへのメッセージ中継

**Objective:** ユーザーとして、Open WebUIのチャットでメッセージを送信すると、その内容がDifyワークフローに転送され、ワークフローの応答がチャットに表示されるようにしたい。それにより、Difyが各バックエンドをオーケストレーションした結果を単一のUIから受け取れる。

#### Acceptance Criteria

1. When ユーザーがOpen WebUI上で新しいテキストメッセージを送信したとき、the Pipeline shall そのメッセージ内容をDifyワークフローAPIへ転送する。
2. When Difyワークフローが応答を返したとき、the Pipeline shall その応答内容をOpen WebUIのチャット画面に表示する。
3. While Difyワークフローが応答を生成中である場合、the Pipeline shall ユーザーに処理中であることが分かる状態を提供する。
4. If Dify APIへの接続が失敗（タイムアウト・認証エラー等）した場合、then the Pipeline shall 接続エラーが発生したことが分かるメッセージをOpen WebUIのチャット画面に表示する。

### Requirement 3: 接続設定・機密情報管理

**Objective:** 個人開発者として、DifyのAPI接続先・APIキーを環境変数で管理したい。それにより、機密情報をリポジトリにコミットせずに環境ごとに設定を切り替えられる。

#### Acceptance Criteria

1. The Dify統合基盤 shall DifyワークフローAPIの接続先URLとAPIキーを環境変数から読み込む。
2. The Dify統合基盤 shall 必要な環境変数の一覧と設定例を、機密情報の値を含まないテンプレートとして提供する。
3. The Dify統合基盤 shall APIキー等の機密情報を含む設定ファイルをリポジトリのバージョン管理対象から除外する。

### Requirement 4: DifyからOllamaへのモデル接続

**Objective:** 個人開発者として、DifyワークフローからローカルのOllamaが提供するLLMモデルを利用できるようにしたい。それにより、外部LLMサービスに依存せずワークフローを構築できる。

#### Acceptance Criteria

1. The Dify統合基盤 shall DifyのモデルプロバイダーとしてOllama（OpenAI互換API）を接続するための設定手順を提供する。
2. When 個人開発者がDify管理画面でOllama接続設定を完了したとき、the Dify shall Ollama上で稼働するモデルをワークフロー内のモデル選択候補として表示する。
3. When Dify上のワークフローがOllama接続済みのモデルを呼び出したとき、the Dify shall Ollamaから応答を取得し、ワークフロー内の処理結果として利用できる状態にする。

### Requirement 5: マルチモーダル（画像）入力の中継

**Objective:** ユーザーとして、Open WebUIで画像を含むメッセージを送信した場合に、その画像データがDifyワークフローに渡されるようにしたい。それにより、後続の画像系機能（逆画像検索等）がDifyワークフロー経由で画像を扱える。

#### Acceptance Criteria

1. When ユーザーがOpen WebUIで画像を含むメッセージを送信したとき、the Pipeline shall 画像データをDifyワークフローのマルチモーダル入力として受け取れる形式に変換して転送する。
2. When ユーザーが画像を含まないテキストのみのメッセージを送信したとき、the Pipeline shall 画像データの変換処理を行わずテキスト内容のみをDifyワークフローへ転送する。
3. If Difyワークフローへの画像データを含むリクエストの転送または処理が失敗した場合、then the Pipeline shall エラーが発生したことが分かるメッセージをOpen WebUIのチャット画面に表示する。

### Requirement 6: 疎通確認用ワークフローとEnd-to-End検証

**Objective:** 個人開発者として、Open WebUIからDifyワークフローまでの中継経路が正しく機能していることを確認したい。それにより、後続の機能Specが本基盤の上に安心してワークフローを追加できる。

#### Acceptance Criteria

1. The Dify統合基盤 shall 受け取ったメッセージの内容をそのまま返す検証用Difyワークフローを提供する。
2. When 個人開発者がOpen WebUI管理画面からPipelineを登録したとき、the Open WebUI shall そのPipelineをチャットで選択可能なモデルとして認識する。
3. When ユーザーが検証用ワークフローに対応するモデルを選択してテキストメッセージを送信したとき、the システム shall 送信内容に基づく応答をOpen WebUIのチャット画面に表示する。
4. When ユーザーが検証用ワークフローに対応するモデルを選択して画像を含むメッセージを送信したとき、the システム shall 画像が中継されたことを確認できる応答をOpen WebUIのチャット画面に表示する。
