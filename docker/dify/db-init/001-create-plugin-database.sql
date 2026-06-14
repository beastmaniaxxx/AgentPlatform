-- dify-plugin-daemonが使用する専用データベースを作成する。
-- postgresイメージは初回起動時（データディレクトリが空の場合）のみ
-- /docker-entrypoint-initdb.d 配下のスクリプトを実行する。
CREATE DATABASE dify_plugin;
