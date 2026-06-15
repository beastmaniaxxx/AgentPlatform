# Requirements Document

## Project Description (Input)
個人開発者として、Open WebUIのチャットUIから最新のWeb情報を取得したい。現状はLLMの知識カットオフにより最新ニュースやWeb上の情報に回答できず、キーワードに基づくWeb画像の取得もチャットから行えない。

`infrastructure`・`dify-integration`の両Specは完了済みであり、SearXNGのJSON出力が有効化済み、Open WebUI↔Dify間のPipeline中継基盤（`dify_bridge`）も構築済みである。これらを前提として、Difyワークフロー内でSearXNGプラグイン（HTTPノード）を呼び出し、以下を実現する。

- ユーザーがOpen WebUIにテキストクエリを入力すると、SearXNG（Google・Bing・DuckDuckGo・Brave等の複数エンジン）でJSON検索し、上位5件をローカルLLM（Ollama）が要約・引用元URL付きで返却する
- 検索結果が0件の場合はその旨を通知し、再検索を促す
- キーワードに基づく画像検索（SearXNGの`!images`カテゴリ）を行い、結果をMarkdown形式（`![](url)`）でチャット内に表示する

対象範囲は`workflows/web_search.yml`・`workflows/image_search.yml`の作成、および必要に応じた`docker/searxng/settings.yml`のエンジン追記（Google Images、Bing Images、DuckDuckGo Images、Yandex Images）。逆画像検索・Instagram検索・Dify-Open WebUI間のPipeline基盤構築自体は対象外（それぞれ別Specが担当）。テキスト検索・キーワード画像検索は完全匿名（SearXNG経由）で行う。

### Out of Scope: Reddit投稿検索

Reddit投稿検索は本Specの対象外とする。

- SearXNGの`reddit`エンジンはold.reddit.comのクロールに依存するが、Reddit側のrobots.txt変更（Google以外の検索エンジンからのクロールを禁止）により、有効化しても安定した結果が得られない
- Reddit公式API（OAuth2）経由であれば機能的には実現可能だが、(1) OAuth2クレデンシャル管理が必要で本Specの「完全匿名（SearXNG経由）」方針と矛盾する、(2) 2025年11月のResponsible Builder Policyにより個人プロジェクトでも事前承認が必須、(3) レート制限（100 QPM）が課される
- Reddit投稿検索を実現する場合は、別Spec（例: `reddit-search`）として切り出し、OAuth2前提・事前承認待ちである旨を別途要件化する

## Requirements

### Boundary Context

- **In scope**: テキストクエリによるWeb検索（複数検索エンジンの結果集約・上位5件の要約・引用元URL付き応答）、キーワードによる画像検索（Markdown形式での画像表示）、各検索における0件時のユーザー通知、検索処理失敗時のユーザー通知、検索処理の匿名性確保
- **Out of scope**: 逆画像検索（`reverse-image-search` Specが担当）、Instagram検索（`instagram-search` Specが担当）、Reddit投稿検索（上記の通り対象外、別Spec化を検討）、Open WebUI↔Dify間のPipeline中継基盤構築自体（`dify-integration` Specで完了済み）
- **Adjacent expectations**: 本機能はSearXNGのJSON検索機能（`infrastructure` Specで有効化済み）およびOpen WebUI↔Dify間のPipeline中継（`dify-integration` Specで構築済み）が利用可能であることを前提とする。本Specはこれらの上にWeb検索・画像検索の応答フローを構築する

### Requirement 1: テキストクエリによるWeb検索と要約

**Objective:** As a 個人開発者, I want Open WebUIのチャットにテキストクエリを送信して最新のWeb情報を要約付きで取得する, so that LLMの知識カットオフを超えた最新情報にアクセスできる

#### Acceptance Criteria
1. When ユーザーがOpen WebUIのチャットでWeb検索を意図したテキストクエリを送信した場合, the Web検索機能 shall 複数の検索エンジンによるメタ検索結果を取得する
2. When 検索結果が1件以上存在する場合, the Web検索機能 shall 検索結果の上位5件を要約し、各要約に引用元URLを付与した応答をチャットに返す
3. If 検索結果が0件である場合, then the Web検索機能 shall 検索結果が見つからなかったことをユーザーに通知し、クエリの変更を促すメッセージを返す
4. If 検索処理中にエラーが発生した場合, then the Web検索機能 shall 例外を発生させずユーザー向けのエラーメッセージを返す
5. The Web検索機能 shall 検索クエリの送信および結果取得をユーザーを特定する情報を付与せずに行う

### Requirement 2: キーワードによる画像検索とMarkdown表示

**Objective:** As a 個人開発者, I want キーワードに基づくWeb画像をチャット内で直接閲覧する, so that 画像を探すために別のツールやブラウザに切り替える必要がなくなる

#### Acceptance Criteria
1. When ユーザーがOpen WebUIのチャットで画像検索を意図したキーワードクエリを送信した場合, the 画像検索機能 shall キーワードに基づく画像検索結果を取得する
2. When 画像検索結果が1件以上存在する場合, the 画像検索機能 shall 取得した画像をMarkdown形式の画像埋め込みでチャット内に表示する
3. If 画像検索結果が0件である場合, then the 画像検索機能 shall 結果が見つからなかったことをユーザーに通知し、クエリの変更を促すメッセージを返す
4. If 検索処理中にエラーが発生した場合, then the 画像検索機能 shall 例外を発生させずユーザー向けのエラーメッセージを返す
5. The 画像検索機能 shall 検索クエリの送信および結果取得をユーザーを特定する情報を付与せずに行う
