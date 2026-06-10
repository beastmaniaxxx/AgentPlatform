# プロジェクト構造規約

## 組織方針

仕様（`.kiro/`）と実装（`docker/`, `pipelines/`, `workflows/`等）を分離する。各機能は `.kiro/specs/<feature>/` に対応するSpecとして定義され、Phase単位で段階的に実装される。

## ディレクトリの責務

- `docker/` : インフラ定義のみ。アプリケーションロジックは含めない
- `pipelines/` : Open WebUI拡張（Pythonスクリプト）のみ。Difyのロジックは含めない
- `workflows/` : Difyワークフローのエクスポートファイル。手動編集は最小限に留める
- `comfyui-workflows/` : ComfyUIのAPI Formatワークフロー定義
- `scripts/` : 運用スクリプト（セットアップ、バックアップ、更新等）。冪等性を担保する
- `docs/` : 仕様（`.kiro/specs/`）以外の補助ドキュメント（要件定義、構成提案等）
- `tests/` : 統合テスト・スモークテスト

## 依存関係の方向

```
docker ← pipelines ← workflows
```

すべては `docker/` 上に成立する。逆方向の依存（dockerからpipelines/workflowsを参照する等）は禁止。

## 命名規則

- Spec名: kebab-case（例: `reverse-image-search`, `web-search`）
- Dockerサービスコンテナ名: 小文字（例: `searxng`, `dify-api`）
- 環境変数: 大文字スネークケース（例: `SERPAPI_KEY`, `SEARXNG_BASE_URL`）

## Spec構成（`.kiro/specs/<feature>/`）

各Specは以下の構造を持ち、Phaseと1:1対応する：

- `spec.json` : メタデータ（status, phase, dependencies, language等）
- `requirements.md` : EARS形式の要件
- `design.md` : 技術設計・File Structure Plan
- `tasks.md` : 実装タスク分解

依存関係は `spec.json` の `dependencies` に明記し、進行順序を制御する。

---
_実装ディレクトリ（docker/, pipelines/, workflows/等）が作成され次第、具体的な配置パターンを追記する_
