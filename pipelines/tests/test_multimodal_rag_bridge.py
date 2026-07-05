import base64
import json

import pytest
import requests

from mmrag_lib.image_hash_index import HashEntry, HashMatch, ImageHashIndex
from mmrag_lib.imgpush_client import ImgpushClient, ImgpushUploadResult
from mmrag_lib.ollama_caption import OllamaCaptionClient
from multimodal_rag_bridge import DifyChatBridge, DifyWorkflowBridge, Pipeline


@pytest.fixture(autouse=True)
def _stub_caption(monkeypatch):
    # 既定でクエリ画像キャプション（Ollama直呼び）をスタブ化し、実通信を避ける。
    monkeypatch.setattr(OllamaCaptionClient, "generate_caption", lambda self, image_bytes: "画像キャプション")


FAKE_IMAGE_B64 = base64.b64encode(b"fakeimagedata").decode()
FAKE_IMAGE_DATA_URI = f"data:image/jpeg;base64,{FAKE_IMAGE_B64}"


def _image_messages():
    return [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": FAKE_IMAGE_DATA_URI}},
    ]}]


def _text_messages(text="hello"):
    return [{"role": "user", "content": text}]


def _make_pipeline(monkeypatch, **env):
    defaults = {
        "DIFY_API_BASE_URL": "http://dify-api:5001/v1",
        "DIFY_MULTIMODAL_RAG_APP_API_KEY": "test-mmrag-key",
        "DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY": "test-ris-key",
        "OLLAMA_BASE_URL": "http://ollama:11434",
        "MULTIMODAL_RAG_CAPTION_MODEL": "test-vision",
        "IMGPUSH_INTERNAL_URL": "http://imgpush:5000",
        "IMGPUSH_BROWSER_BASE_URL": "http://localhost:5100",
        "IMGPUSH_PUBLIC_BASE_URL": "https://public.example.com",
        "MULTIMODAL_RAG_HASH_INDEX_PATH": "/data/hash_index.json",
        "MULTIMODAL_RAG_PHASH_MAX_DISTANCE": "6",
        "MULTIMODAL_RAG_MIN_SCORE": "0.35",
        "MULTIMODAL_RAG_MIN_SCORE_IMAGE": "0.5",
        "REQUEST_TIMEOUT_SECONDS": "30",
    }
    defaults.update(env)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)
    return Pipeline()


def _upload_result(filename="query.jpg", public=True):
    return ImgpushUploadResult(
        filename=filename,
        internal_url=f"http://imgpush:5000/{filename}",
        browser_url=f"http://localhost:5100/{filename}",
        public_url=f"https://public.example.com/{filename}" if public else None,
    )


def _hash_match(filename="registered.jpg", match_type="exact", distance=0, title="登録画像"):
    return HashMatch(
        entry=HashEntry(filename=filename, sha256="s" * 64, phash="ph", dhash="dh", title=title),
        match_type=match_type,
        distance=distance,
    )


def _outputs(count, items, summary=""):
    return {"count": count, "items": json.dumps(items, ensure_ascii=False), "summary": summary}


def test_pipeline_id_is_multimodal_rag(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    assert pipeline.id == "multimodal_rag"


def test_valves_load_from_environment(monkeypatch):
    pipeline = _make_pipeline(monkeypatch, MULTIMODAL_RAG_PHASH_MAX_DISTANCE="9")
    assert pipeline.valves.DIFY_MULTIMODAL_RAG_APP_API_KEY == "test-mmrag-key"
    assert pipeline.valves.IMGPUSH_BROWSER_BASE_URL == "http://localhost:5100"
    assert pipeline.valves.MULTIMODAL_RAG_HASH_INDEX_PATH == "/data/hash_index.json"
    assert pipeline.valves.MULTIMODAL_RAG_PHASH_MAX_DISTANCE == 9
    assert pipeline.valves.REQUEST_TIMEOUT_SECONDS == 30


def test_pipe_prompts_for_input_when_no_text_and_no_image(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    run_called = []
    query_called = []
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda *a, **kw: run_called.append(1) or {})
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: query_called.append(1) or [])

    result = pipeline.pipe(
        user_message="",
        model_id="multimodal_rag",
        messages=_text_messages(""),
        body={},
    )

    assert isinstance(result, str) and len(result) > 0
    assert len(run_called) == 0
    assert len(query_called) == 0


def test_pipe_handles_multimodal_list_user_message(monkeypatch):
    # Open WebUI は画像付きメッセージで user_message をマルチモーダルなリスト
    # （text/image_url パーツの配列）で渡す。文字列前提だとクラッシュしていた回帰。
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(
        ImageHashIndex, "query",
        lambda self, image_bytes, max_distance: [_hash_match("registered.jpg", "exact", 0)],
    )
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("q.jpg", public=True))
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(0, []))

    content = [
        {"type": "text", "text": "この車は？"},
        {"type": "image_url", "image_url": {"url": FAKE_IMAGE_DATA_URI}},
    ]

    result = pipeline.pipe(
        user_message=content,
        model_id="multimodal_rag",
        messages=[{"role": "user", "content": content}],
        body={},
    )

    assert isinstance(result, str)
    assert "完全一致" in result  # クラッシュせず結果を返す


def test_extract_text_from_string_and_list():
    from multimodal_rag_bridge import Pipeline as P
    assert P._extract_text("  hello  ", []) == "hello"
    listed = [{"type": "text", "text": "赤い車"}, {"type": "image_url", "image_url": {"url": "x"}}]
    assert P._extract_text(listed, []) == "赤い車"
    # user_message が空でも messages 側から拾う
    assert P._extract_text([], [{"role": "user", "content": "からメッセージ"}]) == "からメッセージ"


def test_pipe_image_exact_hash_match_is_top_and_no_external_send(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(
        ImageHashIndex, "query",
        lambda self, image_bytes, max_distance: [_hash_match("registered.jpg", "exact", 0)],
    )
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("query.jpg"))
    # KB returns zero; total is driven by the hash exact match alone.
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(0, []))

    result = pipeline.pipe(
        user_message="",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert "![" in result
    assert "http://localhost:5100/registered.jpg" in result
    assert "完全一致" in result
    # 7.1 must not perform any external send or notice.
    assert "プライバシー" not in result
    assert "外部" not in result


def test_pipe_text_query_renders_thumbnails_and_summary(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    query_called = []
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: query_called.append(1) or [])
    upload_called = []
    monkeypatch.setattr(ImgpushClient, "upload", lambda *a, **kw: upload_called.append(1) or _upload_result())
    items = [
        {"filename": "red.jpg", "title": "赤い車", "text": "赤い車の画像。", "source": "doc-1", "score": 0.9},
        {"filename": "blue.jpg", "title": "青い車", "text": "青い車の画像。", "source": "doc-2", "score": 0.7},
    ]
    monkeypatch.setattr(
        DifyWorkflowBridge, "run",
        lambda self, inputs, files, user_id: _outputs(2, items, "赤と青の車が見つかりました。"),
    )

    result = pipeline.pipe(
        user_message="車の画像",
        model_id="multimodal_rag",
        messages=_text_messages("車の画像"),
        body={},
    )

    assert "http://localhost:5100/red.jpg" in result
    assert "http://localhost:5100/blue.jpg" in result
    assert "赤と青の車が見つかりました。" in result
    # No image -> hash lookup and imgpush upload must be skipped.
    assert len(query_called) == 0
    assert len(upload_called) == 0


def test_pipe_filters_low_score_kb_items_and_triggers_not_found(monkeypatch):
    # 無関係画像/クエリで低スコアのKB結果しか無い場合は total==0 とし、フォールバック判定へ回す。
    pipeline = _make_pipeline(monkeypatch)  # 既定 MIN_SCORE=0.35
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    items = [{"filename": "x.jpg", "title": "x", "text": "t", "source": "s", "score": 0.28}]
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(1, items))

    result = pipeline.pipe(
        user_message="無関係な語",
        model_id="multimodal_rag",
        messages=_text_messages("無関係な語"),
        body={},
    )

    assert "見つかりません" in result  # total==0 → 該当なし（テキストのみ）


def test_pipe_min_score_boundary_keeps_ge_and_drops_below(monkeypatch):
    pipeline = _make_pipeline(monkeypatch, MULTIMODAL_RAG_MIN_SCORE="0.35")
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    items = [
        {"filename": "keep.jpg", "title": "k", "text": "t", "source": "s", "score": 0.35},
        {"filename": "drop.jpg", "title": "d", "text": "t", "source": "s", "score": 0.34},
    ]
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(2, items))

    result = pipeline.pipe(
        user_message="車",
        model_id="multimodal_rag",
        messages=_text_messages("車"),
        body={},
    )

    assert "http://localhost:5100/keep.jpg" in result
    assert "drop.jpg" not in result


def test_strip_think_removes_closed_and_unclosed_blocks():
    from multimodal_rag_bridge import _strip_think
    assert _strip_think("<think>reasoning</think>本文です") == "本文です"
    # 未閉じ（推論が途中で切れた）→ それ以降を落とす
    assert _strip_think("前半<think>途中で切れた推論") == "前半"
    assert _strip_think("") == ""


def test_pipe_strips_think_from_summary(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    items = [{"filename": "a.jpg", "title": "A", "text": "t", "source": "s", "score": 0.5}]
    summary = "<think>長い推論トレース...\nDraft 1...\nDraft 2...</think>登録情報に基づく赤い車です。"
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, i, f, u: _outputs(1, items, summary))

    result = pipeline.pipe("車", "multimodal_rag", _text_messages("車"), {})

    assert "<think>" not in result
    assert "推論トレース" not in result
    assert "登録情報に基づく赤い車です。" in result


def test_pipe_does_not_upload_query_image_when_local_result_sufficient(monkeypatch):
    # ローカルで充足（ハッシュ一致）した画像クエリでは、imgpushへ公開アップロードしない
    # （不要な公開・ディスク増を避ける）。アップロードはフォールバック分岐でのみ行う。
    pipeline = _make_pipeline(monkeypatch)
    upload_calls = []
    monkeypatch.setattr(
        ImgpushClient, "upload",
        lambda self, b, m: upload_calls.append(1) or _upload_result("q.jpg", public=True),
    )
    monkeypatch.setattr(
        ImageHashIndex, "query",
        lambda self, image_bytes, max_distance: [_hash_match("registered.jpg", "exact", 0)],
    )
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, i, f, u: _outputs(0, []))

    result = pipeline.pipe("", "multimodal_rag", _image_messages(), {})

    assert len(upload_calls) == 0  # ローカル充足 → アップロードしない
    assert "完全一致" in result


def test_pipe_uploads_query_image_only_on_fallback(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    upload_calls = []
    monkeypatch.setattr(
        ImgpushClient, "upload",
        lambda self, b, m: upload_calls.append(1) or _upload_result("q.jpg", public=True),
    )
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, i, f, u: _outputs(0, []))
    monkeypatch.setattr(DifyChatBridge, "ask", lambda self, q, u: "web結果")

    pipeline.pipe("", "multimodal_rag", _image_messages(), {})

    assert len(upload_calls) == 1  # フォールバック時のみアップロード


def test_pipe_image_query_uses_higher_threshold_and_falls_back(monkeypatch):
    # 画像クエリはキャプション対キャプションのベースラインが高いため、
    # 0.35程度のKB一致は「弱い」とみなし（画像用閾値0.5未満）フォールバックへ回す。
    pipeline = _make_pipeline(monkeypatch)  # MIN_SCORE=0.35 / MIN_SCORE_IMAGE=0.5
    monkeypatch.setattr(OllamaCaptionClient, "generate_caption", lambda self, b: "無関係画像の説明")
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])  # ハッシュ一致なし
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("q.jpg", public=True))
    items = [{"filename": "kb.jpg", "title": "x", "text": "t", "source": "s", "score": 0.35}]
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, i, f, u: _outputs(1, items))
    ask_called = []
    monkeypatch.setattr(DifyChatBridge, "ask", lambda self, q, u: ask_called.append(q) or "web結果")

    result = pipeline.pipe("", "multimodal_rag", _image_messages(), {})

    # 0.35 < 0.5 なので弱一致は棄却 → フォールバック発火
    assert len(ask_called) == 1
    assert "外部" in result


def test_pipe_dedupes_same_filename_preferring_hash_match(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(
        ImageHashIndex, "query",
        lambda self, image_bytes, max_distance: [_hash_match("same.jpg", "exact", 0)],
    )
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result())
    items = [
        {"filename": "same.jpg", "title": "重複", "text": "KB側の重複。", "source": "doc", "score": 0.8},
        {"filename": "other.jpg", "title": "別画像", "text": "別の画像。", "source": "doc", "score": 0.6},
    ]
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(2, items))

    result = pipeline.pipe(
        user_message="",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert result.count("http://localhost:5100/same.jpg") == 1
    assert "http://localhost:5100/other.jpg" in result
    assert "完全一致" in result


def test_pipe_continues_kb_search_when_hash_index_read_fails(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    def boom(self, image_bytes, max_distance):
        raise OSError("index unreadable")

    monkeypatch.setattr(ImageHashIndex, "query", boom)
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result())
    items = [{"filename": "kb.jpg", "title": "KB", "text": "KBのみ。", "source": "doc", "score": 0.5}]
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(1, items))

    result = pipeline.pipe(
        user_message="",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert "http://localhost:5100/kb.jpg" in result


def test_pipe_captions_image_in_pipeline_and_sends_text_only_to_workflow(monkeypatch):
    # Difyのthinkingノードを避け、Pipelineがクエリ画像をキャプションして
    # query_text として渡す（query_image はワークフローへ渡さない）。
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(OllamaCaptionClient, "generate_caption", lambda self, b: "赤い車のキャプション")
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("query.jpg", public=True))
    captured = {}

    def fake_run(self, inputs, files, user_id):
        captured["inputs"] = inputs
        captured["files"] = files
        return _outputs(1, [{"filename": "kb.jpg", "title": "x", "text": "t", "source": "s", "score": 0.5}])

    monkeypatch.setattr(DifyWorkflowBridge, "run", fake_run)

    pipeline.pipe(
        user_message="猫",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert "猫" in captured["inputs"]["query_text"]
    assert "赤い車のキャプション" in captured["inputs"]["query_text"]
    assert "query_image" not in captured["inputs"]
    assert captured["files"] == []


def test_pipe_returns_string_and_does_not_raise_on_request_exception(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result())

    def boom(self, inputs, files, user_id):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(DifyWorkflowBridge, "run", boom)

    result = pipeline.pipe(
        user_message="猫",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert isinstance(result, str)


def test_workflow_bridge_run_posts_blocking_and_returns_outputs(monkeypatch):
    bridge = DifyWorkflowBridge(base_url="http://dify-api:5001/v1", api_key="k", timeout=30)
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"outputs": {"count": 1, "items": "[]", "summary": "s"}}}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["auth"] = headers.get("Authorization")
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    outputs = bridge.run({"query_text": "x"}, [], "user-1")

    assert captured["url"].endswith("/workflows/run")
    assert captured["json"]["response_mode"] == "blocking"
    assert captured["auth"] == "Bearer k"
    assert outputs == {"count": 1, "items": "[]", "summary": "s"}


def test_workflow_bridge_run_surfaces_error_body(monkeypatch):
    bridge = DifyWorkflowBridge(base_url="http://dify-api:5001/v1", api_key="k", timeout=5)

    class FakeResponse:
        status_code = 400
        text = '{"message":"retrieval_mode Input should be single or multiple"}'

        def raise_for_status(self):
            raise requests.exceptions.HTTPError("400 Client Error")

        def json(self):
            return {}

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())

    with pytest.raises(requests.exceptions.RequestException, match="retrieval_mode"):
        bridge.run({"query_text": "x"}, [], "u")


# --- タスク7.2: フォールバック制御と通知・エラー処理 ---


def test_pipe_image_zero_total_falls_back_with_both_notices(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("q.jpg", public=True))
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(0, []))
    captured = {}

    def fake_ask(self, query, user_id):
        captured["query"] = query
        return "Webで3件の類似画像が見つかりました。"

    monkeypatch.setattr(DifyChatBridge, "ask", fake_ask)

    result = pipeline.pipe(
        user_message="",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    # 発火先へは公開URLを渡す（要件4.5）
    assert captured["query"] == "https://public.example.com/q.jpg"
    # フォールバック通知＋外部送信通知を前置（要件4.3, 4.4）
    assert "Web逆画像検索" in result
    assert "外部" in result
    assert "Webで3件の類似画像が見つかりました。" in result


def test_pipe_text_only_zero_total_returns_not_found_without_fallback(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    ask_called = []
    monkeypatch.setattr(DifyChatBridge, "ask", lambda *a, **kw: ask_called.append(1) or "")
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(0, []))

    result = pipeline.pipe(
        user_message="存在しない語",
        model_id="multimodal_rag",
        messages=_text_messages("存在しない語"),
        body={},
    )

    assert isinstance(result, str) and len(result) > 0
    assert len(ask_called) == 0  # フォールバック不可（要件5.2）
    assert "Web逆画像検索" not in result


def test_pipe_returns_error_string_when_workflow_raises(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result())

    def boom(self, inputs, files, user_id):
        raise requests.exceptions.ConnectionError("dify down")

    monkeypatch.setattr(DifyWorkflowBridge, "run", boom)

    result = pipeline.pipe(
        user_message="猫",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert isinstance(result, str)
    assert "失敗" in result


def test_pipe_fallback_web_search_failure_keeps_notices_and_returns_string(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("q.jpg", public=True))
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(0, []))

    def boom(self, query, user_id):
        raise requests.exceptions.ConnectionError("serp down")

    monkeypatch.setattr(DifyChatBridge, "ask", boom)

    result = pipeline.pipe(
        user_message="",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert isinstance(result, str)
    # 外部送信を試みた事実の通知は保持する（要件4.4）
    assert "外部" in result


def test_pipe_uses_reverse_image_search_api_key_for_fallback(monkeypatch):
    pipeline = _make_pipeline(monkeypatch, DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY="ris-key-xyz")
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("q.jpg", public=True))
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(0, []))
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"answer": "ok"}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["auth"] = headers.get("Authorization")
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    pipeline.pipe(
        user_message="",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert captured["url"].endswith("/chat-messages")
    assert captured["auth"] == "Bearer ris-key-xyz"


# --- タスク7.3: 登録確認と外部送信ゼロ不変条件 ---


def test_pipeline_is_registerable_with_expected_identity(monkeypatch):
    # pipelines ランタイムが /models へ列挙するための最小要件を満たすこと。
    pipeline = _make_pipeline(monkeypatch)
    assert pipeline.id == "multimodal_rag"
    assert isinstance(pipeline.name, str) and pipeline.name
    assert callable(pipeline.pipe)


def test_default_hash_index_path_is_under_pipelines_mount(monkeypatch):
    # ハッシュ副インデックスの既定パスは pipelines コンテナのバインドマウント配下で読める必要がある。
    for key in [
        "DIFY_API_BASE_URL",
        "DIFY_MULTIMODAL_RAG_APP_API_KEY",
        "DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY",
        "IMGPUSH_INTERNAL_URL",
        "IMGPUSH_BROWSER_BASE_URL",
        "IMGPUSH_PUBLIC_BASE_URL",
        "MULTIMODAL_RAG_HASH_INDEX_PATH",
        "MULTIMODAL_RAG_PHASH_MAX_DISTANCE",
        "REQUEST_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)

    pipeline = Pipeline()

    assert pipeline.valves.MULTIMODAL_RAG_HASH_INDEX_PATH.startswith("/app/pipelines/")
    # .env.example の既定値と一致していること（共有パスの単一の真実）。
    assert pipeline.valves.MULTIMODAL_RAG_HASH_INDEX_PATH == (
        "/app/pipelines/data/multimodal_rag_hash_index.json"
    )
    assert pipeline.valves.MULTIMODAL_RAG_PHASH_MAX_DISTANCE == 8


def test_no_external_send_when_hash_match_satisfies_query(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    ask_called = []
    monkeypatch.setattr(DifyChatBridge, "ask", lambda *a, **kw: ask_called.append(1) or "")
    monkeypatch.setattr(
        ImageHashIndex, "query",
        lambda self, image_bytes, max_distance: [_hash_match("registered.jpg", "exact", 0)],
    )
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("q.jpg", public=True))
    # KB は0件でも、ハッシュ一致で total>=1 のため外部送信は発生してはならない。
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(0, []))

    result = pipeline.pipe(
        user_message="",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert len(ask_called) == 0
    assert "外部" not in result


def test_no_external_send_when_kb_satisfies_query(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    ask_called = []
    monkeypatch.setattr(DifyChatBridge, "ask", lambda *a, **kw: ask_called.append(1) or "")
    monkeypatch.setattr(ImageHashIndex, "query", lambda *a, **kw: [])
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("q.jpg", public=True))
    items = [{"filename": "kb.jpg", "title": "KB", "text": "t", "source": "s", "score": 0.6}]
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(1, items))

    result = pipeline.pipe(
        user_message="猫",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert len(ask_called) == 0
    assert "外部" not in result


def test_no_external_send_via_requests_when_local_satisfies(monkeypatch):
    # requests レベルでも reverse_image_search(/chat-messages) が呼ばれないことを担保する。
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(
        ImageHashIndex, "query",
        lambda self, image_bytes, max_distance: [_hash_match("registered.jpg", "exact", 0)],
    )
    monkeypatch.setattr(ImgpushClient, "upload", lambda self, b, m: _upload_result("q.jpg", public=True))
    monkeypatch.setattr(DifyWorkflowBridge, "run", lambda self, inputs, files, user_id: _outputs(0, []))
    posted_urls = []
    monkeypatch.setattr(requests, "post", lambda url, **kw: posted_urls.append(url))

    pipeline.pipe(
        user_message="",
        model_id="multimodal_rag",
        messages=_image_messages(),
        body={},
    )

    assert all("/chat-messages" not in url for url in posted_urls)
