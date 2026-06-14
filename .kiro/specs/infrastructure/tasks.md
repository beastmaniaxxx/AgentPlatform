# Implementation Plan

- [x] 1. Foundation: Docker Compose基盤とネットワーク・ボリューム・環境変数管理の準備
- [x] 1.1 docker-compose.ymlの骨格作成（共有ネットワークとボリューム定義）
  - `docker/`ディレクトリを新設し、`docker-compose.yml`に`agentplatform-net`という名前のブリッジネットワークを定義する
  - Open WebUI・Ollama・SearXNG用の名前付きボリュームをトップレベル`volumes:`に定義する
  - 観測可能完了: `docker compose -f docker/docker-compose.yml config`がエラーなく実行でき、出力に`agentplatform-net`ネットワークと各ボリュームが含まれる
  - _Requirements: 1.2, 1.4_

- [x] 1.2 環境変数テンプレートとGit除外設定の作成
  - `docker/.env.example`に各サービスが必要とするポート番号・`SEARXNG_BASE_URL`・`OLLAMA_BASE_URL`・`LMSTUDIO_MODELS_PATH`（LM Studioモデルディレクトリのホスト側パス）等をコメント付きで列挙する
  - リポジトリの`.gitignore`に`docker/.env`と`docker/docker-compose.override.yml`を追加する
  - 観測可能完了: `docker/.env.example`をコピーして`docker/.env`を作成しても`git status`でUntracked/Trackedに表示されない
  - _Requirements: 4.1, 4.2, 6.3_

- [x] 1.3 共有ネットワーク・拡張方針ドキュメントの作成
  - `docker/networks.md`に`agentplatform-net`の命名理由、後続Specがサービス・ボリュームを同一`docker-compose.yml`に追記する方法、SearXNGの`server.limiter: false`設定に関する運用上の注意（外部非公開前提）を記載する
  - 観測可能完了: `docker/networks.md`が作成され、ネットワーク名・拡張手順・運用上の注意の3項目が記載されている
  - _Requirements: 1.4, 5.3_

- [x] 2. Core: 各サービス定義の追加
- [x] 2.1 Ollamaサービス定義の追加
  - `docker-compose.yml`に`ollama/ollama:latest`イメージのサービスを追加し、`agentplatform-net`に接続する
  - `OLLAMA_HOST=0.0.0.0`を設定し、Ollama管理データ用の名前付きボリュームをマウントする
  - `env_file`で`docker/.env`を参照するよう設定する
  - `.env`の`LMSTUDIO_MODELS_PATH`が指すホストディレクトリをコンテナ内`/lmstudio-models`に読み取り専用（`:ro`）でバインドマウントする
  - 観測可能完了: `docker compose up -d ollama`でコンテナが起動し、`docker compose exec ollama curl -s localhost:11434`がOllamaの応答を返す。また`docker compose exec ollama ls /lmstudio-models`でLM Studio側のGGUFファイル一覧が参照でき、同コンテナ内からの書き込み（例: `touch /lmstudio-models/test`）が拒否される
  - _Requirements: 2.2, 4.3, 6.1, 6.2, 6.3_

- [x] 2.2 Open WebUIサービス定義の追加
  - `docker-compose.yml`に`ghcr.io/open-webui/open-webui:main`イメージのサービスを追加し、`agentplatform-net`に接続する
  - `OLLAMA_BASE_URL`をOllamaサービスのコンテナ名を指すよう設定し、`depends_on: ollama`を指定する
  - Open WebUI用ボリュームをマウントし、ホストアクセス用ポートを`.env`の値で公開する
  - 観測可能完了: `docker compose up -d`実行後、ブラウザで`http://localhost:<port>`にアクセスするとOpen WebUIのチャット画面が表示される
  - _Requirements: 2.1, 2.2, 4.3_
  - _Depends: 2.1_

- [x] 2.3 SearXNGサービス定義とJSON出力設定の追加
  - `docker/searxng/settings.yml`を作成し、`search.formats`に`html`と`json`を含め、`server.limiter: false`を設定する
  - `docker-compose.yml`に`searxng/searxng:latest`イメージのサービスを追加し、`settings.yml`をマウントして`agentplatform-net`に接続、ホストアクセス用ポートを`.env`の値で公開する
  - 観測可能完了: `curl "http://localhost:<port>/search?format=json&q=test"`がJSON形式のレスポンスを返す
  - _Requirements: 3.1, 3.2, 4.3, 5.3_

- [x] 2.4 docker-compose.override.ymlによるGPU割り当て設定の追加
  - `docker/docker-compose.override.yml.example`（Git管理対象）を作成し、Ollamaサービスへの`deploy.resources.reservations.devices`によるNVIDIA GPU予約の設定例を記述する
  - GPU非搭載環境では本ファイルをコピーせず`docker-compose.yml`単体で起動できることを`docker/networks.md`または同ファイル内コメントに明記する
  - 観測可能完了: `docker/docker-compose.override.yml.example`を`docker-compose.override.yml`としてコピーし、`docker compose -f docker/docker-compose.yml -f docker/docker-compose.override.yml config`の出力にOllamaサービスのGPU予約設定が反映される
  - _Requirements: 1.3, 5.2_
  - _Depends: 2.1_

- [x] 2.5 LM Studioモデル共有手順ドキュメントの作成
  - `docker/model-sharing.md`に、`LMSTUDIO_MODELS_PATH`の設定方法、`/lmstudio-models`配下のGGUFファイルを指すModelfileの作成例、`ollama create`によるモデル取り込み手順を記載する
  - ディスク容量の二重消費（GGUFがOllama管理データ側にコピーされる）、LM Studio側のモデル更新時に`ollama create`を再実行する必要があること、WSL2経由での読み込みは初回ロードのみ影響することを注意事項として記載する
  - 観測可能完了: `docker/model-sharing.md`が作成され、Modelfile作成例・`ollama create`コマンド例・容量/更新追従に関する注意事項が記載されている
  - _Requirements: 6.4_
  - _Depends: 2.1_

- [x] 3. Integration & Validation: 起動確認とPhase1完了基準の検証
- [x] 3.1 スモークテスト手順書の作成
  - `tests/smoke/infrastructure_smoke.md`に、`docker compose up`実行手順、Open WebUIチャット確認手順、Ollamaコンテナ停止時のOpen WebUI側エラー表示確認手順、SearXNGの`/search?format=json`応答確認手順、LM Studioモデルディレクトリの読み取り専用マウント確認手順（`docker/model-sharing.md`を参照したModelfile取り込みの動作確認を含む）を記載する
  - 観測可能完了: `tests/smoke/infrastructure_smoke.md`が作成され、上記5つの確認手順がすべて記載されている
  - _Requirements: 2.3, 6.4_
  - _Depends: 2.2, 2.3, 2.5_

- [x] 3.2 統合起動確認とPhase1完了基準の検証
  - `docker/.env`を`docker/.env.example`から作成した状態で`docker compose up`（必要に応じて`docker-compose.override.yml`含む）を実行し、Open WebUI・Ollama・SearXNGの3コンテナが`agentplatform-net`上で起動し、コンテナ名で相互に名前解決できることを確認する
  - `tests/smoke/infrastructure_smoke.md`の手順に従い、Open WebUIでのチャット応答、Ollama停止時のエラー表示、SearXNGの`/search?format=json`応答、Ollamaコンテナからの`/lmstudio-models`読み取り専用マウントを確認する
  - 観測可能完了: Open WebUIからのチャット応答とSearXNGの`/search?format=json`によるJSON応答が得られ、Phase1完了基準（Open WebUIからチャット可能、SearXNGのJSON API応答）を満たすことが確認できる
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 3.2, 4.3, 5.1, 5.3, 6.1, 6.2, 6.3_
  - _Depends: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1_

## Implementation Notes
- 1.1: `docker compose config` は、サービスから参照されていないトップレベルの`networks:`/`volumes:`定義を出力から除外する（Compose v5.1.4で確認）。`docker/docker-compose.yml`には`agentplatform-net`ネットワークと`open-webui-data`/`ollama-data`/`searxng-data`ボリュームをソースYAMLとして定義済み。これらが`config`の出力に現れるのは、2.1〜2.4でサービスが各リソースを参照した時点になる（3.2での統合確認時に解決）。
- 2.1: `docker-compose.yml`にトップレベル`name: agentplatform`を追加した。Compose v5のデフォルトプロジェクト名はディレクトリ名（本リポジトリでは`docker`）になるため、同じく`docker`ディレクトリ名でデプロイされた別プロジェクト（Dify）とプロジェクト名が衝突し、`docker compose up --remove-orphans`実行時に無関係なコンテナ・ネットワークが削除される事故が発生した（リカバリ済み、データ消失なし）。`name: agentplatform`によりプロジェクト名を固定し再発を防止する。
- 2.1: `ollama/ollama:latest`イメージには`curl`/`wget`が含まれない。「Ollamaの応答を返す」ことの確認には`docker compose exec ollama ollama list`（同じローカルAPIを呼ぶCLI）を使うこと。3.1/3.2のスモークテスト手順でも同様に`ollama list`等を使用する。
- 2.3: `searxng`サービスには`env_file: .env`を付与しない。`searxng/searxng:latest`イメージは`SEARXNG_PORT`環境変数をコンテナ内部のリスニングポートとして使用するため、ホスト側ポート用の`.env`の`SEARXNG_PORT`を渡すと内部ポートと`ports:`マッピング（`${SEARXNG_PORT}:8080`）が不整合になる。`${SEARXNG_PORT}`の変数展開はCompose本体が`.env`から自動で行うため`env_file`は不要。
- 3.2: 実機検証では`SEARXNG_PORT=8081`（8080は別プロジェクトで使用中）、`LMSTUDIO_MODELS_PATH=/d/LM Studio_Data/models`（スペースを含むパスでも`docker compose config`/バインドマウントは正常動作）、GPU override（RTX 5090）を使用。`docker compose exec ollama nvidia-smi`でGPU認識、`/lmstudio-models`の読み取り専用マウント、`ollama create`によるLM StudioモデルからのOllamaモデル作成（`qwen3vl-test`, 16GB）、`ollama run`での応答生成まで確認済み。
- 3.2: 要件2.3（Ollama接続失敗時のOpen WebUIエラー表示）はOpen WebUI本体のSPA UIロジック（本Specの実装境界外）であり、認証済みブラウザセッションでの確認が必要。インフラ層の障害・復旧条件（`ollama`コンテナ停止時にDNS解決が失敗し`open-webui`コンテナから`http://ollama:11434`への接続が`Name or service not known`になること、再起動後に復旧すること）は確認済み。UIでのエラー表示確認は運用時のフォローアップ（MANUAL_VERIFY）として記録する。
