# Research & Design Decisions Template

## Summary
- **Feature**: `infrastructure`
- **Discovery Scope**: New Feature（Phase1基盤構築、グリーンフィールド）
- **Key Findings**:
  - Open WebUI・Ollama・SearXNGはいずれも公式Dockerイメージが提供されており、Docker Composeでの組み合わせ実績が豊富（自作コンテナは不要）
  - SearXNGはデフォルトでJSON出力が無効化されており、`settings.yml` の `search.formats` に `json` を追加し、かつ `server.limiter: false` にしないと `/search?format=json` が403を返す
  - Ollamaの GPU 利用は Docker Compose の `deploy.resources.reservations.devices`（`driver: nvidia`, `capabilities: [gpu]`）で指定し、NVIDIA Container Toolkitの導入が前提

## Research Log

### Open WebUI + Ollama の Docker Compose構成
- **Context**: 要件1（基盤構成）・要件2（チャット動作）・要件5.2（GPU利用）の実現方法を確認するため
- **Sources Consulted**:
  - https://gist.github.com/usrbinkat/de44facc683f954bf0cca6c87e2f9f88
  - https://mljourney.com/how-to-run-ollama-with-docker-and-docker-compose/
  - https://seanthegeek.net/posts/how-to-run-ollama-and-open-webui-as-a-systemd-service-using-docker-compose/
- **Findings**:
  - Open WebUI公式イメージ: `ghcr.io/open-webui/open-webui:main`。`OLLAMA_BASE_URL` 環境変数でOllamaのエンドポイントをコンテナ名で指定可能
  - Ollama公式イメージ: `ollama/ollama:latest`。`OLLAMA_HOST=0.0.0.0` を設定しないと同一ネットワーク上の他コンテナからアクセスできない
  - GPU割り当ては `deploy.resources.reservations.devices` に `driver: nvidia`, `count: 1` (or `all`), `capabilities: [gpu]` を指定する
- **Implications**:
  - 両サービスをコンテナ名で名前解決させる共通ネットワークを定義する
  - GPUが利用できない環境でも起動できるよう、GPU指定はオーバーライド/オプション扱いにできるかは設計判断としてDocker Compose標準のdeploy reservationsを採用（無効な場合はCPUフォールバックがOllama側で行われる）

### SearXNG JSON出力の有効化
- **Context**: 要件3（`/search?format=json` 応答）の実現方法を確認するため
- **Sources Consulted**:
  - https://github.com/searxng/searxng/discussions/4470
  - https://docs.openwebui.com/features/chat-conversations/web-search/providers/searxng/
  - https://github.com/searxng/searxng/blob/master/searx/settings.yml
- **Findings**:
  - デフォルトでは `search.formats` に `html` のみが含まれ、JSON出力は無効
  - `settings.yml` に以下を設定する必要がある:
    ```yaml
    search:
      formats:
        - html
        - json
    ```
  - `server.limiter: true`（デフォルト）の場合、レートリミッタがAPIアクセスを403でブロックするため、`server.limiter: false` を設定する必要がある
- **Implications**:
  - リポジトリで管理する `settings.yml` をコンテナにマウントし、上記2点を明示的に設定する
  - `server.limiter: false` はAPI疎通確認（Phase1完了基準）のために必要だが、外部公開を想定しないローカル単一ホスト構成のため、本Specのスコープ内で許容する

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| 単一docker-compose.yml + override | 全サービスを1つのCompose定義に集約し、開発用差分をoverrideファイルに分離 | 後続Specがサービスを追記するだけで拡張可能、ネットワーク・ボリュームを自然に共有 | ファイルが将来肥大化する可能性（9 Spec分） | `docs/project_structure_proposal_v1.md` の構成提案・steering/tech.mdの方針と一致 |
| Spec単位で個別compose+`docker compose -f`結合 | 各Specが自分のcompose断片を持ち、起動時に複数ファイルを結合 | Spec間の独立性が高い | 結合順序・ネットワーク定義の重複管理が複雑になり、個人開発の運用コストが増す | 不採用（要件4台のシンプルさを優先） |

## Design Decisions

### Decision: 共有Dockerネットワークの命名と所有
- **Context**: 要件1.2/1.4 で、後続Specが同一ネットワークにサービスを追加できる必要がある
- **Alternatives Considered**:
  1. Docker Composeのデフォルトネットワーク（プロジェクト名ベースの自動生成）に依存する
  2. 明示的な名前付きブリッジネットワーク（例: `agentplatform-net`）を `docker-compose.yml` に定義し、全サービスがこれに接続する
- **Selected Approach**: 2. `docker-compose.yml` 内で `agentplatform-net` という名前のブリッジネットワークを明示的に定義し、Open WebUI・Ollama・SearXNG、および後続Specが追加するサービスもこれに接続する
- **Rationale**: デフォルトネットワーク名はディレクトリ名やCOMPOSE_PROJECT_NAMEに依存して変化しうるため、後続Specが安定して参照できる名前を明示する方が安全
- **Trade-offs**: 明示的定義の分だけ記述量が増えるが、命名の安定性とドキュメント性が向上する
- **Follow-up**: 後続Spec（dify-integration等）はこの名前を `docker-compose.yml` の同一ファイルへの追記、または同名ネットワークへの接続として利用する想定。ネットワーク名を変更する場合は依存する全Specの確認が必要（Revalidation Trigger）

### Decision: GPU割り当ての扱い
- **Context**: 要件5.2でNVIDIA GPUが利用可能な場合にOllamaがそれを使用することが求められる
- **Alternatives Considered**:
  1. `docker-compose.yml` 本体にGPU予約を直接記述する（GPU非搭載環境では起動失敗のリスク）
  2. GPU予約設定を `docker-compose.override.yml`（開発環境向け）に記述し、本体は汎用構成とする
- **Selected Approach**: 2. GPU予約（`deploy.resources.reservations.devices`）は `docker-compose.override.yml` に記述し、本体の `docker-compose.yml` はGPUの有無に依存しない最小構成とする
- **Rationale**: 要件5.1（Windows 11 + WSL2上での起動）を満たしつつ、要件5.2（GPU利用可能時の利用）をオーバーライドで表現することで、開発者の環境差異に対応できる
- **Trade-offs**: GPU設定が本体に統合されないため、GPU利用が「デフォルトで有効」ではなく「オーバーライドで有効化」になる。個人開発者の単一ホスト運用では `docker-compose.override.yml` は通常常駐させる前提のため実用上の問題はない
- **Follow-up**: `docker-compose.override.yml` がGitにコミットされる前提か `.gitignore` 対象かは File Structure Plan で明示する

## Risks & Mitigations
- NVIDIA Container Toolkitが未導入の環境ではGPU予約付きのOllama起動が失敗する — `docker-compose.override.yml` のGPU設定をコメントアウト/削除すればCPUモードで起動可能であることをドキュメント化する
- SearXNGの `server.limiter: false` はAPIへの過剰アクセスを防ぐ機構を無効化する — ローカル単一ホスト・外部非公開構成であることを前提とし、`docker/networks.md` 等に運用上の注意を記載する
- Open WebUI起動直後はOllamaのモデル未ダウンロード状態のため、チャット応答にはモデルのpullが別途必要 — 本Specのスコープ外（要件定義のOut of scopeで明示済み）だが、起動確認手順にその旨を記載する
- LM StudioのGGUFをOllamaに`ollama create`で取り込む際、デフォルトではOllama管理データ（blobs）側にコピーされ、Windows + WSL2 + 異なるドライブ間（D:→Docker vhdx）ではハードリンクが効かずディスク容量を二重消費する（例: 8GBモデルなら計16GB） — `docker/model-sharing.md`に容量計画上の注意として明記する
- WSL2から`/mnt/d/`配下（Windowsドライブ）への読み込みはネイティブLinux FSより低速な場合がある — モデルの初回ロード時のみ影響し推論性能自体には影響しないため、許容リスクとして記録する
- LM Studio側でモデルファイルを更新（再ダウンロード等）してもOllamaは自動追従しない — `ollama create`の再実行が必要であることを`docker/model-sharing.md`に運用手順として記載する

## Additional Research Log

### LM Studioモデル資産の共有方式
- **Context**: ユーザーが既にDドライブのLM Studio配下にGGUFモデルを保持しており、Ollamaから再利用したい（要件6）
- **Sources Consulted**: ユーザー提供の事前検討資料「2026-06-14_difference_in_model_manage.md」（`docs/proposal`配下）
- **Findings**:
  - LM Studioは`models/<publisher>/<repo>/file.gguf`の人間可読なディレクトリ構造でGGUFを管理するが、Ollamaは取り込み時にSHA256ベースの独自管理形式（`manifests/`・`blobs/`）に変換するため、単純なパス共有では`ollama list`に表示されない
  - Modelfileの`FROM <path>`にGGUFファイルパスを指定し`ollama create <name> -f Modelfile`を実行することで取り込み可能。シンボリックリンクによる直接統合（方法③）はハッシュ計算・manifest手動作成が必要で非実用的なため不採用
  - Docker構成では、LM Studioのモデルディレクトリをコンテナに読み取り専用でバインドマウントし、コンテナ内からModelfileでFROM参照する方法（方法②）が現環境（Windows+WSL2+Docker）に適合する
- **Implications**:
  - Ollamaサービスに`/lmstudio-models:ro`の読み取り専用バインドマウントを追加し、ホスト側パスは`.env`の`LMSTUDIO_MODELS_PATH`で利用者ごとに設定する
  - Ollamaの管理データ（`ollama-data`ボリューム）はLM Studioのモデルディレクトリと完全に独立させ、書き込みはOllama管理データ側のみで発生させる
  - Modelfile作成・`ollama create`の実行・テンプレート指定は個々のモデルごとの運用作業であり、本Specでは手順のドキュメント化のみを担当する（Out of Boundary）

## References
- [Ollama + Open-Webui + Nvidia/CUDA + Docker + docker-compose](https://gist.github.com/usrbinkat/de44facc683f954bf0cca6c87e2f9f88) — GPU対応のCompose構成例
- [SearXNG JSON API discussion #4470](https://github.com/searxng/searxng/discussions/4470) — `search.formats` と `server.limiter` の設定方法
- [Open WebUI SearXNG provider docs](https://docs.openwebui.com/features/chat-conversations/web-search/providers/searxng/) — Open WebUIからのSearXNG利用パターン
