# Requirements Document

## Project Description (Input)
個人開発者として、Open WebUIにアップロードした画像と類似する画像をWeb上から探したい。現状、Open WebUIからアップロードされた画像（base64）を外部の逆画像検索APIへ渡す手段がなく、手動での検索が必要になっている。

Pipelineスクリプトがbase64画像をimgpushへPOSTして一時公開URLを取得し、DifyワークフローがそのURLをSerpAPI（`engine=google_reverse_image` または `engine=google_lens`）へ送信して類似画像を検索する。取得した類似画像URLと出典サイトをLLMが要約し、サムネイル＋出典サイト一覧としてOpen WebUIに返却する。また、画像が外部（SerpAPI）へ送信される旨をUI上で通知する。

## Requirements

### Boundary Context

- **In scope**:
  - Open WebUIにアップロードされた画像（base64）を受信し、一時的に外部から参照可能な公開URLへ変換する
  - 当該公開URLを用いた外部の逆画像検索の実行（類似画像・出典サイト情報の取得）
  - 取得した類似画像のサムネイル（Markdown画像埋め込み）と出典サイト一覧のLLM要約付き提示
  - 画像が一時的に外部公開され、第三者の検索サービスへ送信される旨のユーザー通知（情報通知のみ・非ブロッキング）
  - 画像未提供・結果0件・処理失敗時のユーザー通知
- **Out of scope**:
  - ストレージ内画像検索（`multimodal-rag` Specが担当）
  - Instagram検索（`instagram-search` Specが担当）
  - 逆画像検索結果が不十分な場合のフォールバック制御自体（`multimodal-rag` Specが担当）
  - TinEye等への検索バックエンド切り替え（外部送信ポリシー更新が必要なため将来検討、本Specでは対象外）
  - Open WebUI↔Dify間のPipeline中継基盤の構築自体（`dify-integration` Specで完了済み）
- **Adjacent expectations**:
  - 本機能はOpen WebUI↔Dify間のPipeline中継基盤（`dify-integration` Specで構築済み）が利用可能であることを前提とする
  - 本Specが返す逆画像検索結果は、`multimodal-rag` Specがフォールバック判定の入力として参照する想定だが、フォールバックの発火・制御は本Specの責務外とする

### Requirement 1: アップロード画像による逆画像検索の実行

**Objective:** As a 個人開発者, I want Open WebUIにアップロードした画像と類似する画像をWeb上から検索する, so that 手元の画像の出典や類似画像を手動でブラウザ検索せずに見つけられる

#### Acceptance Criteria

1. When ユーザーがOpen WebUIのチャットに画像を添付して送信した場合, the 逆画像検索機能 shall アップロードされた画像を一時的に外部から参照可能な公開URLへ変換する
2. When 画像の公開URL化に成功した場合, the 逆画像検索機能 shall 当該URLを用いて外部の逆画像検索を実行し、類似画像および出典サイト情報を取得する
3. While 逆画像検索の処理が進行中である間, the 逆画像検索機能 shall ユーザーに処理が進行中であることが分かる状態を維持する

### Requirement 2: 類似画像結果の要約とサムネイル提示

**Objective:** As a 個人開発者, I want 検索された類似画像をサムネイルと出典サイト一覧で確認する, so that どの画像がどこに掲載されているかを一目で把握できる

#### Acceptance Criteria

1. When 逆画像検索で類似画像が1件以上取得できた場合, the 逆画像検索機能 shall 取得した類似画像をMarkdown形式の画像埋め込み（サムネイル）で表示する
2. When 類似画像を提示する場合, the 逆画像検索機能 shall 各類似画像に対応する出典サイト情報を併せて提示する
3. When 類似画像と出典サイトを提示する場合, the 逆画像検索機能 shall ローカルLLMによる要約を付与した応答をチャットに返す

### Requirement 3: 外部送信に関するプライバシー通知

**Objective:** As a プライバシーを重視するユーザー, I want アップロード画像が外部へ送信される事実を知らされる, so that 自分の画像がどこへ送られるかを把握したうえで機能を利用できる

#### Acceptance Criteria

1. When ユーザーがアップロード画像による逆画像検索を実行した場合, the 逆画像検索機能 shall 画像が一時的に外部から参照可能なURLとして公開され、当該URLが第三者の検索サービスへ送信される旨をユーザーに通知する
2. The 逆画像検索機能 shall 上記の外部送信に関する通知を、ユーザーの明示的な同意操作を必須とすることなく（非ブロッキングで）行い、逆画像検索の実行を妨げない

### Requirement 4: 異常系・エッジケースの処理

**Objective:** As a 個人開発者, I want 画像未提供・結果0件・処理失敗時に分かりやすい通知を受け取る, so that 何が起きたかを理解して次の操作を判断できる

#### Acceptance Criteria

1. If ユーザーが画像を添付せずにテキストのみで逆画像検索を実行しようとした場合, then the 逆画像検索機能 shall 画像の添付が必要である旨をユーザーに通知する
2. If 逆画像検索の結果が0件である場合, then the 逆画像検索機能 shall 類似画像が見つからなかったことをユーザーに通知する
3. If 画像の公開URL化または外部の逆画像検索の実行中にエラー（外部検索サービスの利用上限到達を含む）が発生した場合, then the 逆画像検索機能 shall 例外を発生させずユーザー向けのエラーメッセージを返す
