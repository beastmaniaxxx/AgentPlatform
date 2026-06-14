# infrastructure スモークテスト

`infrastructure` SpecのPhase1完了基準（Open WebUIからチャット可能、SearXNGの`/search?format=json`が応答する）を確認するための手順。

## 前提条件

- Docker / Docker Composeが利用可能であること
- `docker/.env.example`を`docker/.env`としてコピーし、必要に応じて値を編集していること
  - `LMSTUDIO_MODELS_PATH`には、LM Studioのモデルディレクトリのホスト側パス（存在するディレクトリ）を指定する。LM Studioを利用しない場合も、空ディレクトリ等の存在するパスを指定する
- GPUを利用する場合は`docker/docker-compose.override.yml.example`を`docker-compose.override.yml`としてコピーしていること（GPU非搭載環境ではコピーしない）

## 1. `docker compose up`実行手順

`docker/`ディレクトリで以下を実行し、3コンテナを起動する。

```bash
cd docker
docker compose up -d
```

確認項目:

- `docker compose ps`で`ollama`・`open-webui`・`searxng`の3サービスが`Up`状態であること
- `docker network inspect agentplatform-net`で、3コンテナがネットワークに接続されていること
- Open WebUIコンテナからOllamaコンテナへ、コンテナ名で名前解決できること

```bash
docker compose exec open-webui sh -c "getent hosts ollama"
```

## 2. Open WebUIチャット確認手順

1. ブラウザで `http://localhost:<OPEN_WEBUI_PORT>/`（デフォルト: `http://localhost:3000/`）にアクセスする
2. チャット画面（初回はアカウント作成画面）が表示されることを確認する
3. Ollamaにモデルが1つ以上pull済みの場合、モデルセレクタからモデルを選択し、チャットメッセージを送信する
4. Ollamaから応答が返り、チャット画面に表示されることを確認する

> モデルが未pullの場合、応答自体は得られないが、これは接続エラーとは異なる（本Specのスコープ外、`docker/model-sharing.md`等でモデルを用意してから確認する）。

ブラウザを使わずに確認する場合は、以下でHTMLが返ることを確認する。

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/
```

## 3. Ollamaコンテナ停止時のOpen WebUI側エラー表示確認手順

1. Ollamaコンテナを停止する

```bash
docker compose stop ollama
```

2. ブラウザでOpen WebUIのチャット画面からメッセージを送信する
3. Ollamaに接続できない旨のエラーがチャット画面に表示されることを確認する
4. 確認後、Ollamaコンテナを再起動する

```bash
docker compose start ollama
```

## 4. SearXNGの`/search?format=json`応答確認手順

```bash
curl -s "http://localhost:<SEARXNG_PORT>/search?format=json&q=test"
```

確認項目:

- HTTPステータスが200であること
- レスポンスがJSON形式であり、`"query"`および`"results"`キーを含むこと

## 5. LM Studioモデルディレクトリの読み取り専用マウント確認手順

1. Ollamaコンテナ内から、マウントされたLM Studioモデルディレクトリのファイル一覧が参照できることを確認する

```bash
docker compose exec ollama ls -la /lmstudio-models
```

2. Ollamaコンテナ内から、`/lmstudio-models`への書き込みが拒否される（読み取り専用）ことを確認する

```bash
docker compose exec ollama sh -c "touch /lmstudio-models/test"
# => touch: cannot touch '/lmstudio-models/test': Read-only file system
```

3. Ollamaサーバが起動していることを確認する（`curl`/`wget`は`ollama/ollama:latest`イメージに含まれないため、`ollama`コマンドを使用する）

```bash
docker compose exec ollama ollama list
```

4. `docker/model-sharing.md`の手順に従い、`/lmstudio-models`配下のGGUFファイルを指すModelfileを作成し、`ollama create`でモデルを取り込む

```bash
docker compose exec ollama sh
# コンテナ内で docker/model-sharing.md の手順に従いModelfileを作成
ollama create <model-name> -f /tmp/Modelfile-<model-name>
```

5. `ollama list`に取り込んだモデルが表示されることを確認する

```bash
docker compose exec ollama ollama list
```

## クリーンアップ

確認が完了したら、必要に応じてコンテナを停止する。

```bash
docker compose down
```
