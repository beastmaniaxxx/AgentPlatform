# Docker Network & Volume 構成

## ネットワーク名: `agentplatform-net`

`docker-compose.yml` では、Docker Composeのデフォルトネットワーク（プロジェクト名ベースの自動生成）に依存せず、明示的に `agentplatform-net` という名前のブリッジネットワークを定義している。

理由:
- デフォルトネットワーク名はディレクトリ名や`COMPOSE_PROJECT_NAME`に依存して変化しうるため、名前を明示しないと後続Specが安定して参照できない
- `agentplatform-net` に接続したコンテナは、コンテナ名による名前解決で相互通信できる（例: Open WebUIから `http://ollama:11434` でOllamaに到達できる）

## 後続Specによる拡張方法

後続Spec（`dify-integration` 等）が新しいサービスを追加する場合は、以下の手順に従う。

1. `docker/docker-compose.yml` の `services:` トップレベルキーに新しいサービス定義を追記する
2. 追加したサービスの `networks:` に `agentplatform-net` を指定し、既存サービス（Open WebUI・Ollama・SearXNG等）とコンテナ名で名前解決できるようにする
3. 永続化が必要な場合は、`docker-compose.yml` の `volumes:` トップレベルキーに新しい名前付きボリュームを追加し、サービス定義からマウントする
4. 環境変数が必要な場合は `docker/.env.example` に追記し、利用者が `docker/.env` に値を設定できるようにする

このパターンに従うことで、ネットワーク名やボリューム命名規則を変更せずにサービスを追加できる。

## SearXNGの`server.limiter: false`に関する運用上の注意

`docker/searxng/settings.yml` では、`/search?format=json` をブロックなく利用できるようにするため `server.limiter: false` を設定する。

この設定はSearXNGのレート制限機構を無効化し、APIへの過剰アクセスを防ぐ仕組みが働かなくなる。そのため、以下を前提として運用する。

- SearXNGのポート（`SEARXNG_PORT`）はホスト外部に公開しない、またはローカルネットワーク内のみで利用する
- インターネットに直接公開する構成にする場合は、`server.limiter` の設定やリバースプロキシでのアクセス制御を別途検討する
