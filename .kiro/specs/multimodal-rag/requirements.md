# Requirements Document

## Introduction

個人開発者が、自鯖（セルフホスト環境）内に保存済みの画像から類似画像・関連情報を、単一のチャットUI（Open WebUI）から自然言語または画像入力で検索できるようにする。Web上の逆画像検索を行う前に、まず自鯖内ナレッジベースに該当画像が存在するかを確認し、自鯖内で十分な結果が得られない場合にのみ `reverse-image-search`（Web逆画像検索）へフォールバックする。これにより、外部送信を最小化しつつ（プライバシー優先）、手元の画像の出典・類似画像・関連情報を効率的に発見できる。

検索はテキスト→画像・画像→画像・画像→テキストのクロスモーダルに対応し、マルチモーダルRerankingにより関連度の高い結果を上位に提示する。事前にナレッジベースへ登録された画像（JPG/PNG/GIF、最大2MB）を検索対象とする。

## Boundary Context

- **In scope**:
  - 画像のナレッジベースへの登録フロー（JPG/PNG/GIF・最大2MBの形式/サイズバリデーションを含む）
  - テキスト入力・画像入力によるクロスモーダル検索（テキスト→画像、画像→画像、画像→テキスト）の実行と結果取得
  - マルチモーダルRerankingによる検索結果の関連度順並べ替え
  - 検索結果の提示（Markdown形式の画像埋め込み＋関連情報、`reverse-image-search` と統一された出力フォーマット）
  - 自鯖内検索の結果が不十分な場合に `reverse-image-search`（Web逆画像検索）へフォールバックする制御（発火判定・切り替え通知）
  - 入力未提供・結果0件・処理失敗時のユーザー通知
- **Out of scope**:
  - Web上の逆画像検索ロジック自体（`reverse-image-search` Specが担当）
  - 画像生成・動画生成結果の自動ナレッジベース登録（「今後の検討事項」、本Specでは対象外）
  - Instagram検索（`instagram-search` Specが担当）
  - Open WebUI↔Dify間のPipeline中継基盤の構築自体（`dify-integration` Specで完了済み）
- **Adjacent expectations**:
  - 本機能はOpen WebUI↔Dify間のPipeline中継基盤（`dify-integration` Specで構築済み）が利用可能であることを前提とする
  - 本Specは「自鯖内検索→Web検索」フォールバックの発火・制御の責務を負う。フォールバック先として `reverse-image-search`（Web逆画像検索）を呼び出すが、Web検索ロジック自体および外部送信に関する詳細な実装は `reverse-image-search` に委譲する
  - フォールバックにより入力画像が外部Web検索サービスへ送信される場合、外部送信に関するユーザー通知が行われることを前提とする（通知実体は `reverse-image-search` が担うが、本Specはその通知が利用者に到達する経路を妨げない）
  - 本Specの検索結果出力フォーマットは下流の `ui-customization` で横断的に調整されるため、`reverse-image-search` の出力フォーマット（Markdown画像埋め込み等）と統一する

## Requirements

### Requirement 1: 画像のナレッジベース登録とバリデーション

**Objective:** As a 個人開発者, I want 自鯖内の画像を検索対象としてナレッジベースに登録する, so that 後でテキストや画像からそれらを検索できるようにする

#### Acceptance Criteria

1. When ユーザーが画像をナレッジベースへ登録しようとした場合, the マルチモーダルRAG機能 shall 当該画像の形式（JPG/PNG/GIF）とサイズ（最大2MB）を検証する
2. If 登録対象の画像が許可形式（JPG/PNG/GIF）以外である、またはサイズが2MBを超過する場合, then the マルチモーダルRAG機能 shall 当該画像を登録せず、形式またはサイズの制約に違反した旨をユーザーに通知する
3. When 登録対象の画像が形式およびサイズの検証を通過した場合, the マルチモーダルRAG機能 shall 当該画像を検索対象としてナレッジベースに登録する

### Requirement 2: テキスト・画像によるクロスモーダル検索

**Objective:** As a 個人開発者, I want テキストまたは画像を入力して自鯖内の関連画像・関連情報を検索する, so that 手元の手がかりから保存済み画像とその関連情報を見つけられる

#### Acceptance Criteria

1. When ユーザーがテキストクエリで検索を実行した場合, the マルチモーダルRAG機能 shall ナレッジベースから当該テキストに関連する画像を検索して取得する
2. When ユーザーが画像を入力して検索を実行した場合, the マルチモーダルRAG機能 shall ナレッジベースから当該画像に類似する画像を検索して取得する
3. When ユーザーが画像を入力して検索を実行した場合, the マルチモーダルRAG機能 shall 当該画像に関連する情報（テキスト）を取得して提示する
4. While 検索処理が進行中である間, the マルチモーダルRAG機能 shall ユーザーに処理が進行中であることが分かる状態を維持する

### Requirement 3: マルチモーダルRerankingと結果の提示

**Objective:** As a 個人開発者, I want 関連度の高い結果がサムネイル付きで上位に整理された状態で確認する, so that 目的の画像・情報を一目で把握できる

#### Acceptance Criteria

1. When 検索で複数の候補結果が取得された場合, the マルチモーダルRAG機能 shall マルチモーダルRerankingにより関連度の高い結果が上位になるよう並べ替える
2. When 検索結果を提示する場合, the マルチモーダルRAG機能 shall 取得した画像をMarkdown形式の画像埋め込み（サムネイル）で表示する
3. When 画像を提示する場合, the マルチモーダルRAG機能 shall 各結果に対応する関連情報を併せて提示する
4. When 検索結果を提示する場合, the マルチモーダルRAG機能 shall `reverse-image-search` と統一された出力フォーマット（Markdown画像埋め込み＋関連情報）で応答をチャットに返す

### Requirement 4: 自鯖内検索からWeb逆画像検索へのフォールバック制御

**Objective:** As a プライバシーを重視するユーザー, I want 自鯖内で十分な結果が得られないときだけWeb逆画像検索へ切り替わる, so that 不要な外部送信を避けつつ必要なときはWeb検索で補完できる

#### Acceptance Criteria

1. When 自鯖内検索を実行する場合, the マルチモーダルRAG機能 shall まずナレッジベースに対する検索を試行し、その結果が十分か否かを判定する
2. If 自鯖内検索の結果が0件である、または関連度が十分でないと判定された場合, then the マルチモーダルRAG機能 shall `reverse-image-search`（Web逆画像検索）へフォールバックする
3. When フォールバックを実行する場合, the マルチモーダルRAG機能 shall 自鯖内では十分な結果が得られずWeb逆画像検索に切り替える旨をユーザーに通知する
4. When フォールバックにより入力画像が外部Web検索サービスへ送信される場合, the マルチモーダルRAG機能 shall 画像が外部へ送信される旨の通知が利用者に到達することを妨げない
5. The マルチモーダルRAG機能 shall フォールバックの発火・制御の責務を負い、Web逆画像検索のロジック自体は `reverse-image-search` に委譲する

### Requirement 5: 異常系・エッジケースの処理

**Objective:** As a 個人開発者, I want 入力不足・結果0件・処理失敗時に分かりやすい通知を受け取る, so that 何が起きたかを理解して次の操作を判断できる

#### Acceptance Criteria

1. If ユーザーがテキストも画像も入力せずに検索を実行しようとした場合, then the マルチモーダルRAG機能 shall 検索にはテキストまたは画像の入力が必要である旨をユーザーに通知する
2. If 自鯖内検索とWeb逆画像検索フォールバックの双方で結果が0件である場合, then the マルチモーダルRAG機能 shall 該当する画像・情報が見つからなかった旨をユーザーに通知する
3. If 画像登録または検索処理中にエラー（フォールバック先の利用上限到達を含む）が発生した場合, then the マルチモーダルRAG機能 shall 例外を発生させずユーザー向けのエラーメッセージを返す
