# Research & Design Decisions: multimodal-rag

## Summary

- **Feature**: `multimodal-rag`
- **Discovery Scope**: Complex Integration（Difyマルチモーダルナレッジベース新規導入 + 既存 reverse-image-search へのフォールバック連携）
- **Key Findings**:
  - Dify v1.11.0+ のマルチモーダルナレッジベースは text↔image / image↔image / image↔text のクロスモーダル検索とマルチモーダルRerankingに対応。画像はMarkdownリンク経由（JPG/PNG/GIF・最大2MB）で自動抽出・ベクトル化される（brief制約と一致）。
  - Knowledge Retrieval ワークフローノードは「Query Images」入力変数を持ち、画像をクエリにできる（マルチモーダルKB追加時のみ・2MB上限）。出力 `result` 配列は各チャンクの content/metadata/title と、画像添付を含む場合 `files` フィールドを返す。マルチモーダルKBでは Vision タグ付き multimodal rerank モデルの選択が必須（無いと画像が結果から除外）。
  - v1.11.0 で**公式に列挙されたマルチモーダル埋め込みモデルはすべてクラウド系**（AWS Bedrock nova-2-multimodal-embeddings / Google Vertex AI multimodalembedding@001 / Jina jina-embedding-v4・jina-clip-v1/v2・jina-reranker-m0 / Tongyi multimodal-embedding-v1）。Ollama はネイティブ rerank 非対応。自鯖埋め込み（Xinference等）の v1.11 マルチモーダルKB 互換は**公式未記載＝未検証リスク**。
  - **プライバシー方針との衝突**を確認 → 当初はユーザー判断で「自鯖ホスト（Xinference等）でローカル完結」を選択（steering NFR#1 と整合）。
  - フォールバック方向はユーザー判断により「自鯖内→Web（brief準拠）」を選択。
  - **[方針転換 2026-07-04]** Phase 0互換性スパイクで Xinference のローカル・マルチモーダル埋め込みが非互換と確定（Difyの枠はクラウドプラグイン限定・モデルがTorchCodec/trust_remote_code依存でロード不能）。ユーザー判断により、Xinferenceを廃止し **caption方式ローカルテキストKB**（Ollama Vision キャプション＋Ollama テキスト埋め込み）へ転換。新規コンテナ不要でローカル完結を維持。「画像→画像」はキャプションを介した意味的関連となる。
  - **[補強 2026-07-04]** caption方式は「完全一致・視覚酷似」が弱い（ユーザー指摘）。ユーザー判断により、Dify非依存の **ローカル・ハッシュ照合レイヤ（SHA-256＝完全一致、pHash/dHash＝準一致, Pillow＋imagehash・CPUのみ）** を追加。画像クエリ時に完全/準一致を最上位提示し、caption意味検索と併走。完全一致がローカルで解決するためWebフォールバック（外部送信）を抑止し、プライバシー目的を強化。

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

### [追記 2026-07-04] Dify マルチモーダル埋め込み枠のプロバイダ制約とローカル逃げ道の検証
- **Context**: Phase 0スパイク（下記）で Xinference のローカル・マルチモーダル埋め込みがロード不能と判明。design/requirements へ戻るにあたり、「Xinference を直せば解決するのか」「他にローカルで成立する道はあるのか」を確定する必要があった。
- **Sources Consulted**:
  - Dify v1.11.0 Discussion #29512（対応マルチモーダル埋め込み一覧の再確認）
  - Dify v1.11.1 リリース告知（forum.dify.ai）
  - Dify PR #4110（Jina プロバイダのカスタム base_url 対応）
  - GitHub Issue #29747（multimodal-embedding-v1 のURLエラー）
  - inference.readthedocs.io（Xinference jina-clip-v2）、RAGflow Issue #4254
- **Findings**:
  - **Dify v1.11 のマルチモーダル埋め込み枠は、キュレーションされたクラウドプラグイン（AWS Bedrock / Google Vertex / Jina / Tongyi）に限定**される。Xinference や汎用 OpenAI互換の埋め込みは「通常のテキスト埋め込み」としては登録できるが、マルチモーダルKBの Vision 埋め込みとしては**選択肢に現れない**。→ research 当初の代替案 (b)(c)（Xinference/OpenAI互換で繋ぐ）は**構造的に不成立**。
  - 唯一のローカル逃げ道は、Dify の **Jina プラグインがカスタム base_url に対応**している点（PR #4110）。自鯖に Jina API 互換サーバを立て `jina-clip-v2`＋`jina-reranker-m0` を配信し Dify の Jina プロバイダを向ける方法。ただし `jina-clip-v2` はスパイクで TorchCodec 依存により落ちたモデルそのもので、別ランタイムでの安定配信は未検証・高工数・高リスク。
- **Implications**: 「Xinference を直す」だけでは解決しない。ローカル完結・低リスク・即着手可能な現実解は、マルチモーダル埋め込みを断念し、**既存 Ollama の Vision モデルで画像キャプションを生成 → 通常のテキスト埋め込み（Ollama）でテキストKBに索引する caption 方式**。ユーザー判断（2026-07-04）により caption 方式を採用。「画像→画像」は視覚類似ではなくキャプションを介した意味的関連となる（requirements の意味差異を明記済み）。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| caption方式ローカルテキストKB＋ハッシュ照合【採用 2026-07-04】 | Ollama Vision で画像キャプション生成→Ollama テキスト埋め込みで Dify テキストKBに索引（意味検索）。加えて SHA-256/pHash のローカル副インデックスで完全一致・準一致を検出し最上位提示。検索時はクエリ画像をハッシュ照合＋キャプション化してテキスト検索 | 完全ローカル・外部送信ゼロ・**新規コンテナ不要（Xinference廃止）**・即着手可・追加インフラ最小・privacy方針と整合・**完全一致100%/準一致高精度** | 「異なるが視覚的に似た画像」の厳密類似は非対応（Non-Goal）・キャプション品質が意味検索の再現率を左右・共有ハッシュ索引を1つ管理 | ユーザー判断で採用。要件2.2/2.5/3.1を調整済み |
| 自鯖埋め込み（Xinference）＋ローカル完結【不採用: スパイクで非互換確定】 | Xinferenceでマルチモーダル埋め込み＋vision rerankをオンプレ提供、Dify マルチモーダルKBに接続 | privacy方針と整合・外部送信ゼロ | **Phase 0スパイクで非互換確定**（Dify枠がクラウド限定＋モデルがTorchCodec/trust_remote_code依存でロード不能） | 下記 Phase 0 スパイク結果参照 |
| 自鯖Jina互換エンドポイント【不採用: 高リスク】 | Dify Jinaプラグインのカスタムbase_urlを自鯖 jina-clip-v2/jina-reranker-m0 へ向ける | 真の視覚マルチモーダル＋ローカル維持 | jina-clip-v2 はスパイクで落ちたモデル・別ランタイム安定配信が未検証・高工数 | caption方式を優先し見送り（将来Dify対応時に再検討） |
| クラウド埋め込み（Jina API/Tongyi等）【不採用】 | クラウドのマルチモーダル埋め込み＋rerankを利用 | Dify公式サポートで確実動作・全クロスモーダル | 登録/検索時に画像が外部送信→privacy方針・本機能目的に反する | ユーザー判断で不採用 |
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

### Decision: スパイク結果を受けた方針転換 — caption方式ローカルテキストKB（2026-07-04）
- **Context**: Phase 0スパイクで Xinference のローカル・マルチモーダル埋め込みがロード不能、かつ Dify のマルチモーダル埋め込み枠がクラウドプラグイン限定（上記追記の Research Log）と確定。承認済み design の前提（Xinference＋マルチモーダルKB）が崩れた。
- **Alternatives Considered**: (1) caption方式ローカルテキストKB、(2) 自鯖Jina互換エンドポイント、(3) クラウド埋め込み、(4) multimodal-rag 保留（Architecture Pattern Evaluation 参照）。
- **Selected Approach**: **caption方式**。登録時に Ollama Vision で画像キャプションを生成し、Ollama テキスト埋め込みで Dify テキストKBに索引。検索時はクエリ画像もワークフロー内 Vision LLM ノードでキャプション化してテキスト検索。Reranking は Dify Knowledge Retrieval の hybrid/weighted score（rerankモデル不要）。
- **Rationale**: 完全ローカル（steering NFR#1 準拠）・**新規コンテナ不要（Xinference廃止・docker-compose無改変）**・既存 Ollama 再利用で即着手可・追加インフラ最小。真の視覚類似は諦めるが、本機能の目的（Web送信前に自鯖内を先に確認）はキャプションを介した意味検索で担保できる。
- **Trade-offs**: 「画像→画像」は視覚特徴の類似ではなくキャプション（画像内容の説明）を介した意味的関連になる（要件2.2の意味を調整）。検索再現率はキャプション品質に依存。
- **Follow-up**: 将来 Dify がローカル・マルチモーダル埋め込みに対応した時点で、真の視覚マルチモーダルKBへの移行を再検討（Non-Goals に記載）。キャプション生成プロンプトは docs/setup で調整可能にする。

### Decision: 完全一致・視覚酷似のためのローカル・ハッシュ照合レイヤ追加（2026-07-04）
- **Context**: caption方式は画像を非可逆にテキスト化するため、「同一画像／視覚的にそっくりな画像」の検索精度が下がる。本機能の主目的（Web逆画像検索の前に自鯖内を確認）は、まさに完全一致・準一致の発見が中核であり、ここが弱いと**完全一致クエリほど外部Webフォールバック＝外部送信に落ちやすく、プライバシー目的と逆行**する。ユーザー指摘により顕在化。
- **Alternatives Considered**: (1) ハッシュ照合レイヤ追加、(2) caption のみで割り切り（完全一致は諦める）、(3) クラウド/自鯖Jinaで視覚埋め込み（前段の Design Decision で不採用）。
- **Selected Approach**: **SHA-256（完全一致）＋知覚ハッシュ pHash/dHash（視覚的準一致）** の副インデックスを Dify とは独立にローカル構築（`Pillow`＋`imagehash`, CPUのみ）。登録スクリプトが索引を書き込み、Pipeline が画像クエリ時に完全/準一致を照合して**最上位に提示**、加えて caption 意味検索を併記。十分性判定は `total = ハッシュ一致 + KB count`。
- **Rationale**: 完全一致は SHA-256 で 100%・O(1)。準一致は pHash のハミング距離で高精度・低コスト。GPU/新規コンテナ/外部送信いずれも不要でローカル完結。caption の弱点（完全一致）を的確に補完し、プライバシー目的（外部送信抑止）を強化する。
- **Trade-offs**: 登録スクリプトと Pipeline で共有するハッシュ副インデックス（JSON/SQLite）を1つ管理する必要（共有パスの到達性を手順書で担保）。`Pillow`/`imagehash` 依存を pipelines ランタイムへ追加。pHash 閾値の調整が必要。
- **Follow-up**: pHash 閾値（`MULTIMODAL_RAG_PHASH_MAX_DISTANCE`）の既定値は少数サンプルで調整し docs に明記。件数増時は JSON→SQLite 化を検討。

## Risks & Mitigations
- **[主リスク] キャプション品質が検索再現率を左右** — Vision モデル・キャプションプロンプトを docs で調整可能に。登録キャプションとクエリキャプションを同一方針（同一モデル・同種プロンプト）で生成し語彙を揃える。統合テストで text→image / image→image / image→text の再現を確認。
- **視覚的にのみ類似する画像（キャプションが同一化しにくいケース）は取りこぼす** — 本方式の既知の限界（Non-Goals）。0件時はWeb逆画像検索フォールバックが補完する設計で緩和。
- **Ollama Vision の負荷/応答時間**（登録バッチ・クエリ時のキャプション生成、要約・埋め込みと同一Ollamaに集中）— 登録は非同期バッチで許容。クエリ時のキャプションは1枚のみで軽量。モデル選定と負荷は手順書で案内。
- **`/workflows/run` の画像入力受け渡し・Vision LLM ノードへの接続形式の不確実性** — remote_url（imgpush internal）/ Dify files upload の双方を実装時に検証。テキストのみ入力時に Vision ノードを空処理でスキップする分岐を設計。
- **Open WebUI でのサムネイル到達性** — browser base URL（`http://localhost:${IMGPUSH_PORT}`）が単一ホスト前提。リモートアクセス構成では手順書で base URL 調整を案内。
- **imgpush 画像の無限蓄積**（登録画像＋検索一時画像）— reverse-image-search 同様に定期削除は運用フォローアップ（境界外）。ただし登録画像は永続が前提のため、検索一時画像との区別（命名/ボリューム分離）を実装時に検討。
- **[解消済み] Dify×ローカル・マルチモーダル埋め込みの互換** — Phase 0スパイクで非互換確定し、caption方式へ転換したため本リスクは設計から除外（履歴として下記スパイク結果を保持）。

## Phase 0 互換性スパイク結果

> 実施手順: `docs/multimodal-rag-compatibility-spike.md`
> このセクションはタスク2の完了判定ゲートである。2026-07-03 時点では、Xinference 側でローカルマルチモーダル埋め込みを安定提供できないため、Dify管理画面でのKB作成・3方向検索確認へ進まず停止する。

- 実施日: 2026-07-03
- 実施状態: 非互換/停止
- 実施者: ユーザー手動実行 + Codex支援
- Dify バージョン: 未記録（Dify管理画面でのKB検証前に停止）
- Xinference 到達先: `http://xinference:9997`
- 採用モデルID:
  - マルチモーダル埋め込み: 採用なし
  - vision rerank: `qwen3-vl-reranker-2b`（`Qwen3-VL-Reranker-2B` は単体ロード成功）
- Visionタグ付きマルチモーダルKB:
  - 作成状態: 未実施（embedding 非互換のためKB作成前に停止）
  - dataset id: 未記録
  - Dataset API キー: 未発行
- 検証結果:
  - `Qwen3-VL-Embedding-2B`: ロード失敗。`PreTrainedModel.from_pretrained() got multiple values for keyword argument 'trust_remote_code'`
  - `jina-clip-v2`: ロード失敗。`Could not load libtorchcodec`（TorchCodec / PyTorch / FFmpeg 互換エラー）
  - `gme-Qwen2-VL-2B-Instruct`: ロード失敗。`Could not load libtorchcodec`（TorchCodec / PyTorch / FFmpeg 互換エラー）
  - `Qwen3-VL-Reranker-2B`: rerank 単体ロード成功。ただし embedding が成立しないためマルチモーダルKB検証には進めない
  - text→image: 未実施（embedding 非互換のため停止）
  - image→image: 未実施（embedding 非互換のため停止）
  - image→text: 未実施（embedding 非互換のため停止）
  - Rerank: モデル単体ロードのみ成功。KB上のRerank動作は未実施
- 代替判断: 現行 `xprobe/xinference:latest` では、DifyマルチモーダルKB向けのローカルマルチモーダルembeddingを安定提供できないと判断する。タスク4以降へ進まず、design/requirements に戻って代替案を選定する。
- 次アクション: 代替案として (a) Xinference イメージ固定/カスタム化による PyTorch/TorchCodec/FFmpeg 互換修正、(b) 自鯖 Jina 互換エンドポイント、(c) OpenAI互換エンドポイント、(d) 要件・スコープ再検討（テキスト→画像のみ等）を比較し、承認済み設計を更新する。

## References
- [Multimodal retrieval is now available in the knowledge base - Dify Blog](https://dify.ai/blog/multimodal-retrieval-is-now-available-in-the-knowledge-base)
- [Dify v1.11.0 リリース Discussion #29512](https://github.com/langgenius/dify/discussions/29512)
- [Knowledge Retrieval - Dify Docs](https://docs.dify.ai/en/use-dify/nodes/knowledge-retrieval)
- [Xinference (xorbitsai/inference)](https://github.com/xorbitsai/inference)
- [Integrate Local Models Deployed by Xinference | Dify](https://legacy-docs.dify.ai/development/models-integration/xinference)
- [dify-ollama-rerank-adapter](https://github.com/jtianling/dify-ollama-rerank-adapter)
- [Dify v1.11.1 Multimodal Knowledge Base Is Live（forum.dify.ai）](https://forum.dify.ai/t/dify-v1-11-1-multimodal-knowledge-base-is-live/371)
- [Dify PR #4110: Jina プロバイダの custom url 対応](https://github.com/langgenius/dify/pull/4110)
- [Dify Issue #29747: multimodal-embedding-v1 のURLエラー](https://github.com/langgenius/dify/issues/29747)
- [Xinference jina-clip-v2 モデル（Read the Docs）](https://inference.readthedocs.io/en/latest/models/builtin/embedding/jina-clip-v2.html)
