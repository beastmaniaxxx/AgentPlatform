# Dify関連サービス設定

`dify-integration` Specで追加するDifyサービス群（`docker-compose.yml`）が参照する、Dify公式リポジトリからvendorした設定ファイルおよびイメージバージョン方針を記録する。

## vendor元

- リポジトリ: https://github.com/langgenius/dify
- 取得タグ: `1.14.2`（v1.11以降の最新安定タグ、取得日時点）
- vendorしたファイル:
  - `ssrf_proxy/squid.conf.template`（`docker/ssrf_proxy/squid.conf.template`から取得）
  - `ssrf_proxy/docker-entrypoint.sh`（`docker/ssrf_proxy/docker-entrypoint.sh`から取得）

これらは`dify-sandbox`の送信制御を行う`dify-ssrf-proxy`サービス（タスク2.2）が使用する。`docker-entrypoint.sh`は`squid.conf.template`内の`${VAR}`形式のプレースホルダーを環境変数で展開して`squid.conf`を生成する。

## イメージタグ方針

以降のDify関連サービス追加（タスク2.1〜2.5）では、取得タグ`1.14.2`に対応する以下のイメージタグを使用する。

| サービス | イメージ | タグ |
|---------|---------|------|
| dify-api / dify-worker / dify-worker-beat | `langgenius/dify-api` | `1.14.2` |
| dify-web | `langgenius/dify-web` | `1.14.2` |
| dify-sandbox | `langgenius/dify-sandbox` | `0.2.15` |
| dify-plugin-daemon | `langgenius/dify-plugin-daemon` | `0.6.1-local` |
| dify-db（pgvector拡張） | `pgvector/pgvector` | `pg16` |
| dify-redis | `redis` | `6-alpine` |

## ssrf_proxy / sandbox関連の環境変数

`squid.conf.template`の展開（`docker-entrypoint.sh`）には以下の環境変数が必要。タスク2.2で`docker-compose.yml`の`dify-ssrf-proxy`サービスに設定する。

| 変数 | 説明 | 公式デフォルト値 |
|------|------|------------------|
| `HTTP_PORT` | squidのプロキシポート（`SSRF_HTTP_PORT`相当） | `3128` |
| `COREDUMP_DIR` | squidのコアダンプ出力先（`SSRF_COREDUMP_DIR`相当） | `/var/spool/squid` |
| `REVERSE_PROXY_PORT` | `dify-sandbox`へのリバースプロキシポート（`SSRF_REVERSE_PROXY_PORT`相当） | `8194` |
| `SANDBOX_HOST` | `dify-sandbox`のコンテナ名（`SSRF_SANDBOX_HOST`相当） | `sandbox` |
| `SANDBOX_PORT` | `dify-sandbox`のリスニングポート | `8194` |

`agentplatform-net`上でのコンテナ名は本Specの命名規則（`dify-`プレフィックス）に合わせるため、`SANDBOX_HOST`は`dify-sandbox`を設定する。
