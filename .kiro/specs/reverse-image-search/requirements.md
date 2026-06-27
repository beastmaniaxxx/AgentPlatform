# Requirements Document

## Project Description (Input)
個人開発者として、Open WebUIにアップロードした画像と類似する画像をWeb上から探したい。現状、Open WebUIからアップロードされた画像（base64）を外部の逆画像検索APIへ渡す手段がなく、手動での検索が必要になっている。

Pipelineスクリプトがbase64画像をimgpushへPOSTして一時公開URLを取得し、DifyワークフローがそのURLをSerpAPI（`engine=google_reverse_image` または `engine=google_lens`）へ送信して類似画像を検索する。取得した類似画像URLと出典サイトをLLMが要約し、サムネイル＋出典サイト一覧としてOpen WebUIに返却する。また、画像が外部（SerpAPI）へ送信される旨をUI上で通知する。

## Requirements
<!-- Will be generated in /kiro-spec-requirements phase -->
