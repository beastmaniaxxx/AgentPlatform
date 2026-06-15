# Dify統合セットアップ手順

`dify-integration` Specで追加したDocker Composeサービス群（Difyサービス群・`pipelines`）の初期セットアップ手順をまとめる。本手順は、`docker compose up -d`で全サービスが起動済み（タスク6.1）であることを前提とする。

対象環境: `docker/.env`の以下の変数を使用する。

| 変数 | 用途 |
|------|------|
| `DIFY_WEB_PORT` | Dify管理画面（`dify-web`）のホスト公開ポート（既定: `3001`） |
| `DIFY_API_PORT` | Dify API（`dify-api`）のホスト公開ポート（既定: `5001`） |
| `OPEN_WEBUI_PORT` | Open WebUIのホスト公開ポート（既定: `3000`） |
| `PIPELINES_PORT` | Open WebUI Pipelinesのホスト公開ポート（既定: `9099`） |
| `DIFY_APP_API_KEY` | 検証用ワークフロー（`echo_workflow.yml`）のアプリAPIキーを設定する変数 |

## 1. Difyの初回管理者アカウント作成

1. ブラウザで `http://localhost:${DIFY_WEB_PORT}`（既定: `http://localhost:3001`）にアクセスする。
2. 初回アクセス時はセットアップ画面が表示されるので、管理者用の以下の情報を入力する。
   - メールアドレス
   - ユーザー名
   - パスワード
3. 「セットアップを完了する」を実行すると、入力した管理者アカウントでDify管理画面（コンソール）にログインできる状態になる。
4. 以降の手順は、このアカウントでログインした状態のDify管理画面（コンソール）で行う。

## 2. Dify管理画面でのOllamaモデルプロバイダー設定

DifyのモデルプロバイダーとしてOllama（OpenAI互換API、`agentplatform-net`上でコンテナ名`ollama`により名前解決可能）を接続する。

1. Dify管理画面の右上のアカウントメニューから「設定」→「モデルプロバイダー」を開く。
2. プロバイダー一覧から「Ollama」を選択し、「モデルを追加」を実行する。
3. 追加するOllamaモデルごとに、以下を入力する。
   - **Model Name**: Ollamaにpull済みのモデル名（例: `qwen3vl-test`など、`ollama list`で確認できる名前）
   - **Base URL**: `http://ollama:11434`
   - **Model Type**: モデルの種類（LLM／Text Embeddingなど、対象モデルに合わせて選択）
   - その他のパラメータ（コンテキスト長など）は既定値のままでよい
4. 保存すると、当該モデルがDifyのモデル選択候補（ワークフローの「LLM」ノードのモデル選択ドロップダウン等）に表示される。
5. Ollamaで複数のモデルを利用する場合は、モデルごとに2〜4の手順を繰り返す。

> 補足: `dify-plugin-daemon`が`agentplatform-net`経由で`ollama`コンテナに到達できることがタスク6.1で確認済みのため、追加の接続設定は不要である。

## 3. echo_workflow.ymlのインポート・公開・アプリAPIキー発行

中継経路のEnd-to-End確認用に、`workflows/echo_workflow.yml`をDifyにインポートし、アプリ用APIキーを発行する。

1. Dify管理画面の「スタジオ」（アプリ一覧）を開き、「DSLファイルをインポート」（Import from DSL file）を選択する。
2. リポジトリの `workflows/echo_workflow.yml` を選択してアップロードする。
3. インポートが完了すると、名前「echo」のチャットフローアプリが作成される。アプリを開き、画面右上の「公開する」（Publish）を実行してワークフローを公開状態にする。
4. アプリ画面左側のメニューから「APIアクセス」（API Access）を開き、「APIキー」セクションで「新しいAPIキーを作成」を実行する。
5. 発行されたAPIキー（`app-`から始まる文字列）をコピーし、`docker/.env`の`DIFY_APP_API_KEY`に設定する。

   ```
   DIFY_APP_API_KEY=app-xxxxxxxxxxxxxxxxxxxxxxxx
   ```

6. `docker/.env`の変更を反映するため、`pipelines`コンテナを再起動する。

   ```
   docker compose restart pipelines
   ```

## 4. Open WebUI管理画面でのPipelines接続設定

Open WebUIから`pipelines`コンテナ（`pipelines/dify_bridge.py`）をOpenAI互換APIの接続先として登録し、`dify_bridge`モデルをチャットで選択できるようにする。

1. ブラウザで `http://localhost:${OPEN_WEBUI_PORT}`（既定: `http://localhost:3000`）にアクセスし、管理者アカウントでログインする。
2. 管理者設定（Admin Settings）の「接続」（Connections）を開き、「OpenAI API」接続を新規追加する。
3. 以下を入力する。
   - **API Base URL**: `http://pipelines:9099`
   - **API Key**: Pipelinesランタイムの既定キー `0p3n-w3bu!`（変更していない場合）
4. 保存後、モデル選択メニューに `Dify Bridge`（`dify_bridge`）が表示されることを確認する。

これにより、Open WebUIのチャットで`dify_bridge`モデルを選択すると、3.で公開した`echo_workflow.yml`を経由した中継経路（タスク6.3・6.4のEnd-to-End確認）が利用可能になる。
