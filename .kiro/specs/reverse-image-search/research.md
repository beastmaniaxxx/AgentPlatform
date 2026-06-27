# Research & Design Decisions

## Summary
- **Feature**: `reverse-image-search`
- **Discovery Scope**: Complex Integration（新規外部サービス imgpush の追加 + 新規外部API SerpAPI 連携 + 既存 Dify/Pipeline ブリッジ基盤の拡張）
- **Key Findings**:
  - SerpAPI の Google Lens / Reverse Image API は**直接の画像ファイルアップロードに非対応**で、Googleのサーバーが直接フェッチするため**公開アクセス可能な画像URL**が必須。imgpush をそのURL供給元として用いるが、imgpush の公開到達性（インバウンド）は steering の「外部接続はアウトバウンドのみ」方針の例外となる。
  - imgpush の API は `POST /`（multipart, フィールド名 `file`）→ `{"filename": "<name>"}` を返すのみで、自身の公開URLは関知しない。呼び出し側が公開ベースURLとファイル名から完全URLを組み立てる必要がある。
  - 既存の web-search Spec が確立した「Pipeline（テキストクエリ中継）→ advanced-chat ワークフロー（HTTPノード→Codeノード→If-Else→LLM/Answer）」パターンを踏襲でき、逆画像検索は「クエリ＝公開画像URL」として同型に実装できる。

## Research Log

### SerpAPI Google Lens / Reverse Image の画像入力方式
- **Context**: アップロード画像をどの形式でSerpAPIへ渡すか（バイト列の直接送信が可能か、公開URLが必須か）が、imgpush導入要否と公開到達性要件を左右する。
- **Sources Consulted**:
  - SerpApi Google Lens API ドキュメント / ブログ（https://serpapi.com/google-lens-api , https://serpapi.com/blog/uploading-images-and-searching-with-google-lens-via-serpapi/）
  - SerpApi Google Reverse Image API（https://serpapi.com/google-reverse-image）
  - serpapi/public-roadmap Issue #948「Support image search via file upload」（未実装）
- **Findings**:
  - Google Lens API は `url` パラメータに**公開アクセス可能な画像URL**を要求。`google_reverse_image` も `image_url` に公開URLを要求。
  - SerpAPI 自体に画像バイトを受け取るアップロードエンドポイントは存在しない。S3等の公開ストレージへ先にアップロードして公開URLを得るワークフローが公式に案内されている。
  - Google Lens は AWS S3 のURLで取得に難があると報告されており、Imgur等の単純な画像ホストが推奨される。imgpush（単純な静的配信）は要件に適合する。
- **Implications**:
  - imgpush の導入は必須。かつ imgpush は SerpAPI（公開インターネット）から到達できる必要があり、本Specは「公開ベースURL（`IMGPUSH_PUBLIC_BASE_URL`）の受領とURL組み立て・受け渡し契約」を所有し、トンネル/リバースプロキシ等の公開到達手段の構築自体は境界外（オペレーター責務）とする。
  - 採用エンジンは `google_lens`（現行API、`visual_matches` にサムネイル・タイトル・出典・リンクを含み要件2.1-2.3に適合）。`google_reverse_image` はレガシーのため不採用。

### imgpush の API・設定・運用特性
- **Context**: imgpush をどう docker-compose に組み込み、Pipelineからどう呼び出すか。
- **Sources Consulted**: hauxir/imgpush リポジトリ（https://github.com/hauxir/imgpush）
- **Findings**:
  - アップロード: `POST /`（multipart form, フィールド名 `file`、`Authorization: Bearer <API_KEY>` は任意）→ `{"filename": "<name>"}`。
  - 取得: `GET /<filename>`（`?w=&h=` でリサイズ可）。`/liveness` が常時200。
  - 主な環境変数: `MAX_SIZE_MB`(既定16)、`MAX_UPLOADS_PER_DAY/HOUR/MINUTE`(IP単位レート制限)、`ALLOWED_ORIGINS`、`OUTPUT_TYPE`、`NAME_STRATEGY`(randomstr/uuidv4)、`NUDE_FILTER_MAX_THRESHOLD`、`API_KEY`/`REQUIRE_API_KEY_FOR_UPLOAD`、`STORAGE_BACKEND`(local/s3)。`PUBLIC_URL` 相当は存在しない。
- **Implications**:
  - 公開URLは `f"{IMGPUSH_PUBLIC_BASE_URL}/{filename}"` をPipeline側で組み立てる。
  - 画像はローカルFS（ボリューム）に蓄積され自動失効しない。「一時的」な公開は運用上のクリーンアップ（定期削除）を要するが、本Spec境界外の運用フォローアップとする。
  - `NUDE_FILTER` は正当な画像を誤って拒否し得るため、既定閾値の調整可否をセットアップ手順で案内する。

### Dify ワークフローからのSerpAPI呼び出し（SSRFプロキシ・シークレット・URL符号化）
- **Context**: Difyの HTTPリクエストノードからSerpAPI（外部HTTPS）を安全に呼び出す方法と、APIキー・画像URLの扱い。
- **Sources Consulted**: 既存 `docker/docker-compose.yml`（dify-ssrf-proxy 設定）、`workflows/web_search.yml`（HTTPノード/Codeノードのパターン）、Dify DSL の環境変数参照仕様。
- **Findings**:
  - Dify の HTTPノードは `dify-ssrf-proxy`(squid) 経由でアウトバウンドする。serpapi.com は外部（非プライベート）宛のため既定で許可される想定だが、HTTPS CONNECT 到達は実装時に検証が必要。
  - SerpAPI キーはDifyの**Secret型環境変数**（`{{#env.SERPAPI_KEY#}}`）として参照すれば、DSLエクスポート・ログでマスクされる。
  - 画像の公開URLをSerpAPIの `url` クエリパラメータに渡す際は**URLエンコードが必須**（`https://...` の `:`/`/` がクエリ文字列を壊すため）。
- **Implications**:
  - SERPAPI_KEY は Dify管理画面でインポート後にSecret環境変数として設定（`docker/.env`・DSLには値を置かない）。LLMノードのモデル設定と同様の「オペレーターによるインポート後設定」手順に統合する。
  - HTTPノードはクエリパラメータを `params`（key-value）で構成し、`url={{#sys.query#}}` をエンコードさせる。確実性のため、Pipeline側で公開URLを `urllib.parse.quote` 済みにして渡す二重防御も検討（実装時に検証）。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Pipelineでimgpushアップロード→URLをワークフローへ中継（採用） | base64→imgpush変換をPipeline(`image_uploader.py`)が担い、公開URLを `query` としてワークフローへ渡す | 既存web-searchパターンと同型、責務分離が明確、imgpushはagentplatform-net内でPipelineから到達可能 | Pipeline↔ワークフロー間でURL文字列の符号化整合が必要 | 採用 |
| Difyワークフロー内でimgpushアップロード | Difyの画像ファイルをワークフロー内でimgpushへPOST | Pipelineを薄く保てる | DifyのファイルをワークフローからPOSTする経路が複雑、SSRFプロキシ制約、base64取り扱いがDify側に漏れる | 不採用 |
| imgpushを使わずDify FILES_URLを公開 | Difyの `/files` を公開しSerpAPIに渡す | サービス追加不要 | Dify内部URL/認証が絡み公開が困難、brief方針と不一致 | 不採用 |

## Design Decisions

### Decision: imgpush公開到達性はオペレーター提供の `IMGPUSH_PUBLIC_BASE_URL` とする
- **Context**: SerpAPIが画像を取得するにはimgpushが公開到達可能でなければならないが、steeringは全サービス127.0.0.1バインド・アウトバウンド限定。
- **Alternatives Considered**:
  1. cloudflared を docker-compose に同梱して本Specが公開を所有
  2. ngrok等の簡易トンネルを手順案内
  3. オペレーター提供の公開ベースURLのみを契約とし、トンネル本体は境界外（採用）
- **Selected Approach**: imgpush を内部サービスとして追加し、Pipelineは `IMGPUSH_PUBLIC_BASE_URL`（オペレーターが設定）＋filenameで公開URLを組み立てる。トンネル/リバースプロキシの構築はセットアップ手順で案内するが本Spec境界外。
- **Rationale**: 実装範囲を最小化し、steeringのネットワーク方針への例外を「ドキュメントとオペレーター設定」に局所化。既存の「オペレーターがDifyインポート/APIキー発行を行う」運用パターンと一貫。
- **Trade-offs**: すぐ動く状態は提供せず、オペレーターによる公開設定が前提。代わりに各環境（自宅/VPS/トンネル）に柔軟に適応できる。
- **Follow-up**: セットアップ手順に公開設定の代表例（Cloudflare Tunnel等）と、`IMGPUSH_PUBLIC_BASE_URL` 未設定時にPipelineが明示エラーを返す挙動を記載。

### Decision: SERPAPI_KEY は Dify Secret 環境変数で管理
- **Context**: SerpAPIキーはDifyワークフローのHTTPノード内で使用される。プロジェクトの他シークレットは `docker/.env`。
- **Alternatives Considered**:
  1. `docker/.env` に置きPipelineからワークフロー `inputs` で渡す（会話ログに露出し得る）
  2. Dify Secret環境変数として設定（DSL/ログでマスク、採用）
- **Selected Approach**: Dify管理画面でインポート後にSecret型環境変数 `SERPAPI_KEY` を設定し、HTTPノードで `{{#env.SERPAPI_KEY#}}` を参照。DSL・`docker/.env` には値を置かない。
- **Rationale**: ワークフロー内専用シークレットはDifyのSecret機構が purpose-built で安全（マスク）。会話 `inputs` 経由のキー露出を避ける。briefの「.env管理」は discovery 入力であり、より安全なDify Secretで代替する。
- **Trade-offs**: シークレットの単一ソースが `docker/.env` に統一されない（Dify側にも存在）。セットアップ手順で取得・設定箇所を明示して補う。
- **Follow-up**: `docker/.env.example` には SERPAPI_KEY は追加せず、設定先がDify管理画面である旨をコメント or 手順書に明記。

### Decision: 外部送信のプライバシー通知はPipelineが応答に前置（情報通知のみ・非ブロッキング）
- **Context**: 要件3（情報通知のみ・非ブロッキング）。画像のimgpushアップロードと外部送信はPipelineが起点。
- **Selected Approach**: 画像を検知し外部検索処理へ進む経路で、Pipelineが固定の注意文をワークフロー応答の先頭に前置して返す。同意操作は求めない。
- **Rationale**: 成功/0件/エラーいずれの応答でも通知が表示され、通知の出力位置が一意に定まる。ワークフローは結果整形に専念できる。
- **Trade-offs**: 通知文がPipeline側に固定化される（多言語化はui-customization Specで横断調整余地）。

## Risks & Mitigations
- **imgpush公開到達性の未設定** — `IMGPUSH_PUBLIC_BASE_URL` 未設定/到達不可時はPipelineが明示的なエラーメッセージを返し、手順書で公開設定を案内する。
- **SerpAPI無料枠（月100検索）超過** — 超過時のSerpAPIエラーをCodeノードで0件相当または明示エラーとして扱い、ユーザーに分かるメッセージを返す。利用上限はセットアップ手順に明記。
- **SSRFプロキシがserpapi.comへのHTTPS到達を阻害** — 実装時に `dify-ssrf-proxy` 経由でのSerpAPI到達を疎通確認。必要なら許可設定を追記。
- **画像URLのクエリ符号化不整合** — HTTPノードの `params` 利用＋Pipeline側 `quote` の二重防御を検証。
- **imgpush画像の蓄積（プライバシー）** — 自動失効しないため、定期削除は運用フォローアップ（本Spec境界外）。手順書に注意を記載。
- **NUDE_FILTER誤検知** — 正当画像の拒否可能性。閾値調整/無効化をセットアップ手順で案内。
- **Pipeline間ヘルパーのimport** — `image_uploader.py` を `reverse_image_search_bridge.py` から import する構成が pipelines ランタイムで解決されることを起動時に検証。

## References
- [SerpApi Google Lens API](https://serpapi.com/google-lens-api) — 公開URL必須・`visual_matches` 構造
- [Uploading Images and Searching with Google Lens via SerpApi](https://serpapi.com/blog/uploading-images-and-searching-with-google-lens-via-serpapi/) — 直接アップロード非対応、公開URL前提のワークフロー
- [SerpApi Google Reverse Image API](https://serpapi.com/google-reverse-image) — レガシーエンジン（不採用）
- [hauxir/imgpush](https://github.com/hauxir/imgpush) — API・環境変数仕様
- 既存実装: `workflows/web_search.yml`, `pipelines/web_search_bridge.py`, `pipelines/dify_bridge.py`, `docker/docker-compose.yml`
