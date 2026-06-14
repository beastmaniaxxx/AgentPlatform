# AgentPlatform プロジェクト構成提案

cc-sdd（Kiroスタイル Spec-Driven Development）に基づき、要件定義書の内容を機能単位のSpecに分解して構成します。

---

## 1. リポジトリ全体構造

```
AgentPlatform/
├── .kiro/                          # cc-sdd の仕様ディレクトリ
│   ├── steering/                   # プロジェクト全体のコンテキスト
│   │   ├── product.md              # 何を/誰のために作るか
│   │   ├── tech.md                 # 技術スタック
│   │   └── structure.md            # ディレクトリ規約・命名規則
│   └── specs/                      # 機能ごとの仕様
│       ├── infrastructure/         # Phase 1：基盤環境
│       ├── dify-integration/       # Phase 2：Dify連携
│       ├── web-search/             # Phase 3：SearXNG ワード検索
│       ├── image-generation/       # Phase 4：ComfyUI画像生成
│       ├── reverse-image-search/   # Phase 5：逆画像検索
│       ├── instagram-search/       # Phase 6：Instagram連携
│       ├── multimodal-rag/         # Phase 7：マルチモーダルRAG
│       ├── video-generation/       # Phase 8：動画生成
│       └── ui-customization/       # Phase 9：UI調整
│
├── .claude/                        # Claude Code設定
│   └── settings.local.json         # 権限設定
│
├── docker/                         # Docker Compose設定群
│   ├── docker-compose.yml          # 全サービス統合定義
│   ├── docker-compose.override.yml # 開発用オーバーライド
│   ├── .env.example                # 環境変数テンプレート
│   ├── openwebui/
│   ├── ollama/
│   ├── searxng/
│   │   └── settings.yml            # JSON出力有効化済み
│   ├── dify/
│   ├── comfyui/
│   ├── imgpush/                    # 逆画像検索用
│   └── networks.md                 # ネットワーク構成説明
│
├── pipelines/                      # OpenWebUI Pipelineスクリプト
│   ├── dify_bridge.py              # OpenWebUI ↔ Dify 中継
│   ├── image_uploader.py           # base64 → imgpush 変換
│   └── README.md
│
├── workflows/                      # Difyワークフロー定義
│   ├── web_search.yml              # SearXNGワード検索
│   ├── image_search.yml            # SearXNG画像検索
│   ├── reverse_image_search.yml    # SerpAPI連携
│   ├── instagram_search.yml        # Instagram Graph API
│   ├── multimodal_rag.yml          # ストレージ内画像検索
│   ├── image_generation.yml        # ComfyUI連携
│   └── video_generation.yml
│
├── comfyui-workflows/              # ComfyUI APIフォーマット
│   ├── text_to_image.json
│   ├── image_to_image_controlnet.json
│   └── text_to_video.json
│
├── scripts/                        # 運用スクリプト
│   ├── setup.sh                    # 初期セットアップ
│   ├── backup.sh                   # データバックアップ
│   ├── update.sh                   # コンテナ更新
│   └── health_check.sh
│
├── docs/                           # 補助ドキュメント
│   ├── architecture.md             # システム全体アーキテクチャ
│   ├── setup-guide.md              # セットアップ手順
│   ├── troubleshooting.md
│   └── images/                     # ドキュメント用画像
│
├── tests/                          # テスト・検証スクリプト
│   ├── integration/                # 統合テスト
│   └── smoke/                      # スモークテスト
│
├── .gitignore
├── .env.example
├── CLAUDE.md                       # Claude Code への指示・索引
├── LICENSE
└── README.md
```

---

## 2. `.kiro/steering/` の内容

cc-sddではプロジェクト全体に共通するコンテキストを `steering/` に配置します。これは全Specから参照される「プロジェクトメモリ」です。

### 2.1 `steering/product.md`

```markdown
# プロダクト概要

## ビジョン
完全セルフホスト型のマルチモーダルAIエージェント。
プライバシーを保ちながらWeb検索・画像生成・逆画像検索を
チャットUIから統合的に操作できる環境を提供する。

## ターゲットユーザー
- 個人開発者
- ローカルAI環境を構築したいクリエイター
- プライバシーを重視するパワーユーザー

## 解決する課題
- クラウドAIのプライバシー・コスト問題
- 検索・生成ツールの断片化
- LLMの知識カットオフ問題

## 非機能の優先順位
1. プライバシー（外部送信を最小化）
2. コスト（OSS・無料枠を優先）
3. 拡張性（ノードベースで機能追加可能）
4. 性能（個人ハードウェアで実用速度）
```

### 2.2 `steering/tech.md`

```markdown
# 技術スタック

## 基盤
- OS: Windows 11 + WSL2
- コンテナ: Docker Compose

## サービス層
- フロントエンド: Open WebUI（公式イメージ利用）
- LLMサーバ: Ollama
- LLMモデル: Qwen 3.6 / Gemma 4（Vision対応）
- メタ検索: SearXNG（JSON出力有効化必須）
- AIオーケストレーター: Dify v1.11以降
- 画像生成: ComfyUI（Dev Mode有効化）
- 一時画像ホスト: imgpush
- 外部API: SerpAPI / Instagram Graph API

## コード規約
- Python: PEP8、type hint必須
- YAML: 2スペースインデント
- 環境変数: SCREAMING_SNAKE_CASE
- ファイル名: kebab-case（ドキュメント）、snake_case（Python）
```

### 2.3 `steering/structure.md`

```markdown
# プロジェクト構造規約

## ディレクトリの責務
- docker/      : インフラ定義のみ。アプリケーションロジックは含めない
- pipelines/   : OpenWebUI拡張のみ。Difyのロジックは含めない
- workflows/   : Dify エクスポートファイル。手動編集は最小限
- scripts/     : 実行可能スクリプト。冪等性を担保する
- docs/        : 仕様以外のドキュメント

## 命名規則
- Spec名: kebab-case（例：reverse-image-search）
- DockerサービスCN: 小文字（例：searxng, dify-api）
- 環境変数: 大文字スネーク（例：SERPAPI_KEY）

## 依存関係の方向
docker ← pipelines ← workflows
すべてはdockerの上に成立する。逆方向の依存は禁止。
```

---

## 3. Spec単位の分解方針

要件定義書の機能を **9つのSpec** に分解します。各SpecはPhaseと対応し、独立して進められる粒度に設計します。

| Spec名                  | Phase | 内容                                        | 依存先             |
| ----------------------- | ----- | ------------------------------------------- | ------------------ |
| infrastructure          | 1     | Docker基盤、ネットワーク、ボリューム        | -                  |
| dify-integration        | 2     | DifyとOpen WebUIのPipeline中継              | infrastructure     |
| web-search              | 3     | SearXNG連携（ワード検索）                   | infrastructure, dify-integration |
| image-generation        | 4     | ComfyUIによるテキスト→画像                  | dify-integration   |
| reverse-image-search    | 5     | imgpush + SerpAPI                           | dify-integration   |
| instagram-search        | 6     | Instagram Graph API                         | dify-integration   |
| multimodal-rag          | 7     | Difyナレッジベース                          | dify-integration, reverse-image-search |
| video-generation        | 8     | ComfyUI動画生成                             | image-generation   |
| ui-customization        | 9     | Functions / Custom CSS                      | （全機能完了後）   |

---

## 4. 各Specディレクトリの中身

cc-sddの規約に従い、各Specは以下の構造を持ちます。

```
.kiro/specs/web-search/
├── spec.json           # メタデータ（status, phase, dependencies）
├── requirements.md     # EARS形式の要件
├── design.md           # 技術設計・File Structure Plan
└── tasks.md            # 実装タスク分解
```

### 4.1 `spec.json` の例（web-search）

```json
{
  "name": "web-search",
  "phase": 1,
  "status": "draft",
  "dependencies": ["infrastructure"],
  "created_at": "2026-05-30",
  "owner": "personal"
}
```

### 4.2 `requirements.md` の構造（EARS形式）

```markdown
# Web検索（SearXNG）要件

## ユーザーストーリー
個人開発者として、最新情報をチャットから取得したい。
LLMの知識カットオフを補い、引用付きで回答を得るため。

## 機能要件（EARS形式）

### REQ-WS-001
**WHEN** ユーザーがOpen WebUIにテキストクエリを入力したとき
**THE SYSTEM SHALL** SearXNGの複数エンジン（Google・Bing・DuckDuckGo・Brave）に
クエリを送信し、JSON形式で結果を取得する。

### REQ-WS-002
**WHEN** SearXNGから検索結果を受け取ったとき
**THE SYSTEM SHALL** 上位5件のページ内容を要約し、引用元URLを含めて返却する。

### REQ-WS-003
**IF** 検索結果が0件の場合
**THE SYSTEM SHALL** ユーザーにその旨を通知し、再検索を促す。
```

### 4.3 `design.md` の構造

```markdown
# Web検索 技術設計

## アーキテクチャ
[Open WebUI] → [Pipeline] → [Dify] → [SearXNG] → [Ollama要約] → [返却]

## File Structure Plan
- docker/searxng/settings.yml           : JSON出力有効化
- workflows/web_search.yml              : Difyワークフロー
- pipelines/dify_bridge.py              : 既存スクリプト流用

## データフロー
（シーケンス図）

## 設定値
- SEARXNG_BASE_URL: http://searxng:8080
- 結果件数: 上位5件
- タイムアウト: 30秒

## エラーハンドリング
- SearXNG接続失敗 → ユーザーにエラーメッセージ表示
- 検索結果0件 → 「該当する情報が見つかりませんでした」
```

### 4.4 `tasks.md` の構造

```markdown
# Web検索 実装タスク

## TASK-WS-001: SearXNG コンテナのセットアップ
- [ ] docker-compose.yml にSearXNGサービスを追加
- [ ] settings.yml の formats に json を追加
- [ ] 動作確認：curl で /search?q=test&format=json が返ること

## TASK-WS-002: Difyワークフロー作成
- [ ] DifyのMarketplaceでSearXNGプラグインをインストール
- [ ] Workflow Studioでフロー作成（Start→SearXNG→LLM→End）
- [ ] エクスポートして workflows/web_search.yml として保存

## TASK-WS-003: Pipeline経由のOpen WebUI連携
- [ ] dify_bridge.py の DIFY_BASE_URL を設定
- [ ] DIFY_KEY を環境変数から読み込むよう修正
- [ ] Open WebUI管理画面からアップロード

## TASK-WS-004: 検証
- [ ] チャットから「2026年の最新ニュース」と入力
- [ ] 引用付き回答が返ることを確認
- [ ] 統合テストを tests/integration/ に追加
```

---

## 5. CLAUDE.md（プロジェクトルート）

cc-sddではトップレベルに `CLAUDE.md` を置き、Claude Codeに対する索引として機能させます。

```markdown
# AgentPlatform - Claude Code 索引

## プロジェクト概要
マルチモーダルAIエージェントの個人開発プロジェクト。
詳細は `.kiro/steering/product.md` を参照。

## 技術スタック
`.kiro/steering/tech.md` を参照。

## ディレクトリ規約
`.kiro/steering/structure.md` を参照。

## 開発フロー
1. ステアリングを更新：`/kiro-steering`
2. 新Spec開始：`/kiro-spec-init <feature-name>`
3. 要件定義：`/kiro-spec-requirements <feature-name>`
4. 設計：`/kiro-spec-design <feature-name>`
5. タスク分解：`/kiro-spec-tasks <feature-name>`
6. 実装：`/kiro-impl <feature-name>`

## 進行中のSpec
`.kiro/specs/` 配下の spec.json の status を参照。

## ブランチ戦略
- main: 動作確認済みコード
- feature/<spec-name>: Spec単位の開発ブランチ

## 注意事項
- 既存ファイルへの変更は必要最小限に留める
- Spec間の依存関係は spec.json に明記する
- 各Spec完了時にmainへマージ
```

---

## 6. `.claude/settings.local.json`

cc-sddでは多くのファイルを生成するため、権限設定で許可リストを整えます。

```json
{
  "permissions": {
    "allow": [
      "Write(.kiro/**)",
      "Write(docker/**)",
      "Write(pipelines/**)",
      "Write(workflows/**)",
      "Write(comfyui-workflows/**)",
      "Write(scripts/**)",
      "Write(docs/**)",
      "Write(tests/**)",
      "Edit(.kiro/**)",
      "Edit(docker/**)",
      "Edit(pipelines/**)",
      "Bash(git *)",
      "Bash(docker *)",
      "Bash(docker-compose *)"
    ],
    "deny": [
      "Write(.env*)",
      "Edit(.env*)"
    ]
  }
}
```

---

## 7. 開発フローの全体像

```
[初期化]
  └─ npx cc-sdd@latest --claude --lang ja
     → .kiro/ と .claude/ が生成される

[ステアリング]
  └─ /kiro-steering

[Spec 1: infrastructure]
  ├─ /kiro-spec-init infrastructure
  ├─ /kiro-spec-requirements infrastructure
  ├─ /kiro-spec-design infrastructure
  ├─ /kiro-spec-tasks infrastructure
  └─ /kiro-impl infrastructure
     → docker-compose.yml が完成

[Spec 2: dify-integration]
  └─ 同上のフロー

... 以降、各Specを順次進める ...

[各Spec完了時]
  ├─ /kiro-validate-impl <spec-name>
  ├─ git commit & push
  └─ 次のSpecへ
```

---

## 8. .gitignore 推奨内容

```
# 環境変数（機密情報）
.env
.env.local
docker/.env

# ボリュームデータ
docker/**/data/
docker/**/storage/

# Pythonキャッシュ
__pycache__/
*.pyc
venv/

# Node（OpenWebUIをフォークする場合）
node_modules/

# Claude Code
.claude/local/

# OS
.DS_Store
Thumbs.db

# ログ
*.log
logs/

# ComfyUIのモデル（巨大ファイル）
comfyui-workflows/models/
```

---

## 9. 初期化コマンド（実行手順）

リポジトリクローン直後に実行するコマンドの想定順序：

```bash
# 1. リポジトリクローン
git clone https://github.com/beastmaniaxxx/AgentPlatform.git
cd AgentPlatform

# 2. cc-sdd インストール
npx cc-sdd@latest --claude --lang ja

# 3. ステアリング初期化
# Claude Code 内で：
# /kiro-steering

# 4. 最初のSpecを開始
# /kiro-spec-init infrastructure

# 5. 以降、要件→設計→タスク→実装を順に進める
```

---

## 10. README.md の推奨構造

```markdown
# AgentPlatform

完全セルフホスト型マルチモーダルAIエージェント

## 概要
[簡潔な説明]

## アーキテクチャ
[architecture.md へのリンク]

## クイックスタート
[setup-guide.md へのリンク]

## 開発フロー
本プロジェクトはcc-sddによる仕様駆動開発で進行しています。
詳細は `.kiro/steering/` および `CLAUDE.md` を参照してください。

## ライセンス
[LICENSE]
```

---

## まとめ：このプロジェクト構成の特徴

1. **cc-sddの規約に完全準拠**：`.kiro/steering/` と `.kiro/specs/<feature>/` の二層構造
2. **Phaseと1:1対応するSpec分解**：要件定義書のPhase 1〜9がそのままSpecになる
3. **依存関係の明示**：spec.jsonのdependenciesで進行順序を制御
4. **実装ディレクトリとの分離**：仕様（.kiro/）と実装（docker/, pipelines/等）を分離
5. **個人開発に最適化**：CIや高度な権限分離は省略、必要最小限の構成
6. **拡張容易性**：新機能追加時はSpecを1つ追加するだけ
