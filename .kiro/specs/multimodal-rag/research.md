# Research & Design Decisions: multimodal-rag

## Summary

- **Feature**: `multimodal-rag`
- **Discovery Scope**: Complex Integration（Difyマルチモーダルナレッジベース新規導入 + 既存 reverse-image-search へのフォールバック連携）
- **Key Findings**:
  - Dify v1.11.0+ のマルチモーダルナレッジベースは text↔image / image↔image / image↔text のクロスモーダル検索とマルチモーダルRerankingに対応。画像はMarkdownリンク経由（JPG/PNG/GIF・最大2MB）で自動抽出・ベクトル化される（brief制約と一致）。
  - Knowledge Retrieval ワークフローノードは「Query Images」入力変数を持ち、画像をクエリにできる（マルチモーダルKB追加時のみ・2MB上限）。出力 `result` 配列は各チャンクの content/metadata/title と、画像添付を含む場合 `files` フィールドを返す。マルチモーダルKBでは Vision タグ付き multimodal rerank モデルの選択が必須（無いと画像が結果から除外）。
  - v1.11.0 で**公式に列挙されたマルチモーダル埋め込みモデルはすべてクラウド系**（AWS Bedrock nova-2-multimodal-embeddings / Google Vertex AI multimodalembedding@001 / Jina jina-embedding-v4・jina-clip-v1/v2・jina-reranker-m0 / Tongyi multimodal-embedding-v1）。Ollama はネイティブ rerank 非対応。自鯖埋め込み（Xinference等）の v1.11 マルチモーダルKB 互換は**公式未記載＝未検証リスク**。
  - **プライバシー方針との衝突**を確認 → ユーザー判断により「自鯖ホスト（Xinference等）でローカル完結」を選択（steering NFR#1 と整合、本機能の目的を担保）。
  - フォールバック方向はユーザー判断により「自鯖内→Web（brief準拠）」を選択。

## Research Log

### Dify v1.11 マルチモーダルナレッジベースの能力
- **Context**: brief が前提とする「Dify v1.11.0以降のマルチモーダル埋め込み」が、クロスモーダル検索（特に画像クエリ）とRerankingを実際にワークフローで実現できるか確認が必要だった。
- **Sources Consulted**:
  - Dify Blog: Multimodal retrieval is now available in the knowledge base
  - GitHub Discussion #29512（v1.11.0 リリースノート）
  - Dify Docs: Knowledge Retrieval node
- **Findings**:
  - マルチモーダル埋め込みで text/image を統一ベクトル空間に配置し、3方向クロスモーダル検索が可能。
  - 画像はMarkdownリンク（JPG/PNG/GIF・最大2MB）で文書に埋め込むと自動抽出・ベクトル化。
  - Knowledge Retrieval ノードに「Query Images」入力（画像変数、2MB上限、マルチモーダルKB必須）。出力 `result`（配列: content/metadata/title）＋ `files`（画像詳細）。
  - マルチモーダルKB使用時は Vision タグ付き multimodal rerank の選択が必須。
- **Implications**: ワークフローは Start（text + image file 入力）→ Knowledge Retrieval（query + query_images, multimodal rerank）→ 正規化 → 件数分岐 → LLM要約 → End（構造化出力）で構成可能。画像クエリ（image→image / image→text）が標準機能で実現できる。

### 埋め込み・Rerankモデルの調達（プライバシー衝突）
- **Context**: steering NFR#1（外部送信最小化・ローカル完結・LLM推論は全ローカル）と、本機能の目的（Web送信前に自鯖内確認）に対し、公式列挙のマルチモーダル埋め込みがクラウド系のみである点が衝突。
- **Sources Consulted**:
  - GitHub Discussion #29512（対応モデル一覧）
  - Xinference（xorbitsai/inference）: OpenAI互換API・オンプレでマルチモーダルモデル実行・Dify連携実績
  - dify-ollama-rerank-adapter（Ollamaにrerankが無いことの回避策）
  - Mixpeek/Spheron: 自鯖向けマルチモーダル埋め込み（CLIP/SigLIP/JinaCLIP-v2）
- **Findings**:
  - 公式マルチモーダル埋め込みはクラウド系（Bedrock/Vertex/Jina API/Tongyi）。
  - Xinference はオンプレで CLIP/SigLIP/Jina-CLIP 系の埋め込みと rerank を OpenAI互換で提供でき、Dify は Xinference を埋め込みプロバイダとして利用可能（一般RAG実績）。ただし v1.11 の**マルチモーダルKB（Visionタグ）**で Xinference 埋め込みが「マルチモーダル埋め込み」として認識されるかは未検証。
  - Ollama はネイティブ rerank エンドポイント無し（アダプタが必要）。
- **Implications**: ユーザー選択は「自鯖ホストでローカル完結」。Xinference を新規コンテナとして追加し、マルチモーダル埋め込み＋vision rerank をローカル提供する方針。ただし Dify v1.11 マルチモーダルKB との互換は**実装前の Phase 0 互換性スパイクで必ず検証**する（下記リスク）。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| 自鯖埋め込み（Xinference）＋ローカル完結【採用】 | Xinferenceでマルチモーダル埋め込み＋vision rerankをオンプレ提供、Dify マルチモーダルKBに接続 | privacy方針と整合・外部送信ゼロ・本機能の目的を担保 | Dify v1.11 マルチモーダルKB互換が未検証・GPU VRAM/セットアップ負荷増 | Phase 0 互換性スパイク必須。非互換時の代替を用意 |
| クラウド埋め込み（Jina API等） | Jina等のマルチモーダル埋め込み＋rerankを利用 | Dify動作実績・追加インフラ最小 | 登録/検索時に画像が外部送信→privacy方針・本機能目的に反する | ユーザー判断で不採用 |
| フォールバック制御の所在: Pipeline主導【採用】 | multimodal_rag.ymlは自鯖検索のみ・構造化出力。Pipelineが件数を見て reverse_image_search を発火 | ワークフロー疎結合・internal/public URLスコープを分離管理しやすい・制御責務がmultimodal-ragに局在 | Pipelineが2つのDifyアプリキーとimgpush public uploadを扱う | reverse_image_search.yml を無改変で再利用 |
| フォールバック制御の所在: Workflow主導 | multimodal_rag.yml内のHTTPノードで reverse_image_search アプリを呼ぶ | ワークフロー内で完結 | Difyアプリ間HTTP結合・1ワークフロー内でinternal/public URLが混在し複雑 | 不採用 |

## Design Decisions

### Decision: ワークフローは workflow モード（advanced-chat ではなく）
- **Context**: Pipeline がフォールバック判定（自鯖検索の十分性）と、ブラウザ到達可能なサムネイルURL再構築を行うため、`answer` 文字列ではなく構造化出力（件数・アイテム）が必要。
- **Alternatives Considered**:
  1. advanced-chat ＋ 応答文字列にセンチネル埋め込み — 文字列パースが脆弱
  2. workflow モード ＋ `/workflows/run` の構造化 `outputs` — 件数を機械的に判定可能
- **Selected Approach**: `multimodal_rag.yml` を workflow モードとし、End ノードで `count` / `items`(JSON) / `summary` を返す。Pipeline は `DifyWorkflowBridge.run()`（`POST /workflows/run`）で呼ぶ。
- **Rationale**: 十分性判定が明示的・堅牢。既存 `DifyChatBridge.ask()`（chat-messages）はフォールバック先 reverse_image_search 呼び出しに流用。
- **Trade-offs**: 新たに run 用ブリッジメソッドが必要だが小規模。
- **Follow-up**: `/workflows/run` の inputs に画像ファイルを渡す形式（remote_url）を実装時に検証。

### Decision: imgpush の3つのURLスコープを分離
- **Context**: 画像URLの用途が3つあり、到達性要件が異なる。
- **Selected Approach**:
  - **internal**（`IMGPUSH_INTERNAL_URL`, 例 `http://imgpush:5000`）: Dify が KB インデックス時/検索時に画像取得（コンテナ間・外部送信なし）
  - **browser**（新規 `IMGPUSH_BROWSER_BASE_URL`, 既定 `http://localhost:${IMGPUSH_PORT}`）: Open WebUI がサムネイル表示時にブラウザから取得
  - **public**（既存 `IMGPUSH_PUBLIC_BASE_URL`）: フォールバック時のみ SerpAPI が外部から取得（reverse-image-search 由来）
- **Rationale**: 自鯖内検索は internal/browser のみで完結し外部送信ゼロ。public はフォールバック発生時にのみ使用し、その時だけ外部送信通知を出す。
- **Trade-offs**: 環境変数が増えるが、到達性とプライバシー境界が明確化。
- **Follow-up**: KB には imgpush filename を保持し、表示用URLは browser base から Pipeline が再構築（KBに保存されたURL基底に依存しない）。

### Decision: 画像登録は scripts/ の冪等スクリプト
- **Context**: brief の「事前にDifyナレッジベースへ登録」はチャットフロー外のバッチ操作。
- **Selected Approach**: `scripts/register_multimodal_kb.py`（structure.md の scripts/＝冪等な運用スクリプト規約に従う）。ディレクトリ内画像を検証（JPG/PNG/GIF・2MB）→ imgpush(internal)へアップロード → Markdown文書化 → Dify Dataset API（`POST /v1/datasets/{id}/document/create-by-text`）で登録。filename/ハッシュで登録済みをスキップし冪等化。
- **Rationale**: 検索Pipelineと責務分離。運用スクリプトとして再実行安全。
- **Trade-offs**: Open WebUIからの登録UIは提供しない（境界外・将来検討）。

### Decision: imgpush クライアントを共有ヘルパーに新設
- **Context**: reverse-image-search では `ImgpushUploader` が `reverse_image_search_bridge.py` にインライン化済み。multimodal-rag の登録スクリプトと検索Pipelineの双方で imgpush アップロードが必要。
- **Selected Approach**: 新規 `pipelines/imgpush_client.py`（`ImgpushClient` + 画像バリデーション）を multimodal-rag が所有・利用。
- **Rationale**: 承認済み reverse-image-search のファイル改変を避けつつDRYを確保。
- **Trade-offs**: 当面 reverse_image_search_bridge.py 内の実装と重複。`reverse_image_search_bridge.py` を共有ヘルパーへ移行するのは**境界外の任意フォローアップ**とする。

## Risks & Mitigations
- **[最大リスク] Dify v1.11 マルチモーダルKB が Xinference 提供のマルチモーダル埋め込み/vision rerank を「Vision」モデルとして受理しない可能性** — Phase 0 互換性スパイクで先行検証（小規模KBで text→image / image→image / image→text とRerankの動作確認）。非互換時の代替: (a) Dify「Jina」プロバイダの base URL を自鯖 Jina 互換エンドポイント（自鯖 jina-clip-v2 / jina-reranker-m0）へ向ける、(b) OpenAI互換エンドポイント経由、(c) それでも不可なら要件・スコープ再検討（テキスト→画像のみに縮小 等）。スパイク結果を本research.mdに追記。
- **GPU VRAM 競合**（Ollama LLM・ComfyUI将来導入・Xinference 埋め込み/rerank の同時常駐）— Xinference のモデルを軽量（CLIP/SigLIP系）に選定、必要時オンデマンドロード。手順書にVRAM目安を明記。
- **`/workflows/run` への画像入力（Query Images）受け渡し形式の不確実性** — remote_url（imgpush internal）/ Dify files upload の双方を実装時に検証。
- **Open WebUI でのサムネイル到達性** — browser base URL（`http://localhost:${IMGPUSH_PORT}`）が単一ホスト前提。リモートアクセス構成では手順書で base URL 調整を案内。
- **imgpush 画像の無限蓄積**（登録画像＋検索一時画像）— reverse-image-search 同様に定期削除は運用フォローアップ（境界外）。ただし登録画像は永続が前提のため、検索一時画像との区別（命名/ボリューム分離）を実装時に検討。

## References
- [Multimodal retrieval is now available in the knowledge base - Dify Blog](https://dify.ai/blog/multimodal-retrieval-is-now-available-in-the-knowledge-base)
- [Dify v1.11.0 リリース Discussion #29512](https://github.com/langgenius/dify/discussions/29512)
- [Knowledge Retrieval - Dify Docs](https://docs.dify.ai/en/use-dify/nodes/knowledge-retrieval)
- [Xinference (xorbitsai/inference)](https://github.com/xorbitsai/inference)
- [Integrate Local Models Deployed by Xinference | Dify](https://legacy-docs.dify.ai/development/models-integration/xinference)
- [dify-ollama-rerank-adapter](https://github.com/jtianling/dify-ollama-rerank-adapter)
