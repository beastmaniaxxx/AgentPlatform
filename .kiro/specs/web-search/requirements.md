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
<!-- Will be generated in /kiro-spec-requirements phase -->
