# LM Studioモデル資産の共有

LM Studioが管理するGGUFモデル資産を、Ollamaから読み取り専用で参照し、Modelfile経由でOllamaに取り込む手順を説明する。

## 前提

- `docker/.env`の`LMSTUDIO_MODELS_PATH`に、LM Studioのモデルディレクトリのホスト側パスを設定していること（例: `/mnt/d/LMStudio/models`）
- `docker compose up`でOllamaコンテナが起動していること
- 上記ディレクトリは、Ollamaコンテナ内の`/lmstudio-models`に**読み取り専用**でマウントされる

## Modelfileの作成

LM StudioのGGUFファイルは `models/<publisher>/<repo>/file.gguf` のような階層で配置されている。Ollamaコンテナ内では、これが `/lmstudio-models/<publisher>/<repo>/file.gguf` として参照できる。

Ollamaコンテナに入り、Modelfileを作成する。

```bash
docker compose exec ollama sh
```

コンテナ内で、取り込みたいGGUFファイルを指すModelfileを作成する。

```dockerfile
# /tmp/Modelfile-qwen3
FROM /lmstudio-models/Qwen/Qwen3-8B-GGUF/qwen3-8b-q4_k_m.gguf

# 推奨パラメータ（モデルに応じて調整する）
PARAMETER temperature 0.7
PARAMETER num_ctx 8192

# チャットテンプレート（モデルによって異なる。
# 公式Ollamaライブラリのモデルページやモデルの tokenizer_config.json を参照して指定する）
TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>"""
```

## `ollama create`によるモデル取り込み

作成したModelfileから、Ollamaにモデルを登録する。

```bash
ollama create qwen3-8b -f /tmp/Modelfile-qwen3
```

取り込みが成功すると、`ollama list`に登録したモデルが表示され、Open WebUIのモデルセレクタからも選択できるようになる。

```bash
ollama list
```

## 注意事項

### ディスク容量の二重消費

`ollama create`は、Modelfileの`FROM`で指定したGGUFファイルをOllamaの管理データ（`/root/.ollama`配下、`ollama-data`ボリューム）にコピーする。Windows + WSL2 + 異なるドライブ間（LM StudioのモデルがあるドライブとDocker Desktopの仮想ディスク）では、ハードリンクではなくコピーになるため、同じモデルのファイルサイズ分だけ追加でディスクを消費する（例: 8GBのモデルなら、LM Studio側8GB + Ollama管理データ側8GB = 計16GB）。

ディスク容量の計画には、Ollamaに取り込むモデル分の追加容量を含めておくこと。

### LM Studio側のモデル更新への追従

LM Studio側でモデルファイルを更新（再ダウンロード等）しても、Ollama側には自動で反映されない。更新を取り込むには、`ollama create`を再実行する必要がある。

```bash
ollama create qwen3-8b -f /tmp/Modelfile-qwen3
```

### WSL2経由でのファイル読み込み速度

`/lmstudio-models`はWindowsドライブ（例: Dドライブ）をWSL2経由でマウントしているため、ネイティブのLinuxファイルシステムより読み込みが遅い場合がある。この影響は`ollama create`実行時（GGUFファイルの読み込み・コピー時）の初回ロードのみであり、取り込み後のOllamaによる推論性能には影響しない。
