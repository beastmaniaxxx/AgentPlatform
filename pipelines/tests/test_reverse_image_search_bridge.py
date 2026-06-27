import base64

import pytest
import requests

from image_uploader import ImgpushUploader
from reverse_image_search_bridge import DifyChatBridge, Pipeline, _PRIVACY_NOTICE

FAKE_IMAGE_B64 = base64.b64encode(b"fakeimagedata").decode()
FAKE_IMAGE_DATA_URI = f"data:image/jpeg;base64,{FAKE_IMAGE_B64}"


def _make_image_messages():
    return [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": FAKE_IMAGE_DATA_URI}}
    ]}]


def _make_text_messages(text="hello"):
    return [{"role": "user", "content": text}]


def _make_pipeline(monkeypatch, **env):
    defaults = {
        "DIFY_API_BASE_URL": "http://dify-api:5001/v1",
        "DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY": "test-ris-key",
        "IMGPUSH_INTERNAL_URL": "http://imgpush:5000",
        "IMGPUSH_PUBLIC_BASE_URL": "https://example.com",
        "REQUEST_TIMEOUT_SECONDS": "30",
    }
    defaults.update(env)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)
    return Pipeline()


def test_pipeline_id_is_reverse_image_search(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    assert pipeline.id == "reverse_image_search"


def test_valves_load_from_environment_variables(monkeypatch):
    pipeline = _make_pipeline(monkeypatch, IMGPUSH_PUBLIC_BASE_URL="https://my-tunnel.example.com")
    assert pipeline.valves.IMGPUSH_PUBLIC_BASE_URL == "https://my-tunnel.example.com"
    assert pipeline.valves.IMGPUSH_INTERNAL_URL == "http://imgpush:5000"
    assert pipeline.valves.DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY == "test-ris-key"
    assert pipeline.valves.REQUEST_TIMEOUT_SECONDS == 30


def test_pipe_returns_attachment_prompt_when_no_image(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    upload_called = []
    ask_called = []
    monkeypatch.setattr(ImgpushUploader, "upload", lambda *a, **kw: upload_called.append(1) or "")
    monkeypatch.setattr(DifyChatBridge, "ask", lambda *a, **kw: ask_called.append(1) or "")

    result = pipeline.pipe(
        user_message="検索して",
        model_id="reverse_image_search",
        messages=_make_text_messages("検索して"),
        body={},
    )

    assert isinstance(result, str)
    assert len(result) > 0
    assert len(upload_called) == 0
    assert len(ask_called) == 0


def test_pipe_does_not_call_imgpush_or_dify_when_no_image(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    upload_called = []
    ask_called = []
    monkeypatch.setattr(ImgpushUploader, "upload", lambda *a, **kw: upload_called.append(1) or "")
    monkeypatch.setattr(DifyChatBridge, "ask", lambda *a, **kw: ask_called.append(1) or "")

    pipeline.pipe(
        user_message="text only",
        model_id="reverse_image_search",
        messages=_make_text_messages("text only"),
        body={},
    )

    assert len(upload_called) == 0
    assert len(ask_called) == 0


def test_pipe_with_image_calls_upload_then_ask(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    call_order = []

    def fake_upload(self, image_bytes, mime_type):
        call_order.append("upload")
        assert image_bytes == b"fakeimagedata"
        assert mime_type == "image/jpeg"
        return "https://example.com/abc.jpg"

    def fake_ask(self, query, user_id):
        call_order.append("ask")
        assert query == "https://example.com/abc.jpg"
        return "3件の類似画像が見つかりました。"

    monkeypatch.setattr(ImgpushUploader, "upload", fake_upload)
    monkeypatch.setattr(DifyChatBridge, "ask", fake_ask)

    result = pipeline.pipe(
        user_message="",
        model_id="reverse_image_search",
        messages=_make_image_messages(),
        body={},
    )

    assert call_order == ["upload", "ask"]
    assert "3件の類似画像" in result


def test_pipe_prepends_privacy_notice_on_success(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    monkeypatch.setattr(ImgpushUploader, "upload", lambda *a, **kw: "https://example.com/img.jpg")
    monkeypatch.setattr(DifyChatBridge, "ask", lambda *a, **kw: "検索結果です。")

    result = pipeline.pipe(
        user_message="",
        model_id="reverse_image_search",
        messages=_make_image_messages(),
        body={},
    )

    assert result.startswith(_PRIVACY_NOTICE)
    assert "検索結果です。" in result


def test_pipe_prepends_privacy_notice_on_request_exception(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    def fake_upload(self, image_bytes, mime_type):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(ImgpushUploader, "upload", fake_upload)

    result = pipeline.pipe(
        user_message="",
        model_id="reverse_image_search",
        messages=_make_image_messages(),
        body={},
    )

    assert result.startswith(_PRIVACY_NOTICE)
    assert isinstance(result, str)


def test_pipe_prepends_privacy_notice_on_value_error(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    def fake_upload(self, image_bytes, mime_type):
        raise ValueError("IMGPUSH_PUBLIC_BASE_URL が未設定です。")

    monkeypatch.setattr(ImgpushUploader, "upload", fake_upload)

    result = pipeline.pipe(
        user_message="",
        model_id="reverse_image_search",
        messages=_make_image_messages(),
        body={},
    )

    assert result.startswith(_PRIVACY_NOTICE)
    assert isinstance(result, str)


def test_pipe_does_not_reraise_request_exception(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    monkeypatch.setattr(ImgpushUploader, "upload",
                        lambda *a, **kw: (_ for _ in ()).throw(requests.exceptions.RequestException("err")))

    result = pipeline.pipe(
        user_message="",
        model_id="reverse_image_search",
        messages=_make_image_messages(),
        body={},
    )

    assert isinstance(result, str)


def test_pipe_does_not_reraise_value_error(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    def fake_upload(self, image_bytes, mime_type):
        raise ValueError("some value error")

    monkeypatch.setattr(ImgpushUploader, "upload", fake_upload)

    result = pipeline.pipe(
        user_message="",
        model_id="reverse_image_search",
        messages=_make_image_messages(),
        body={},
    )

    assert isinstance(result, str)


def test_pipe_uses_reverse_image_search_api_key(monkeypatch):
    pipeline = _make_pipeline(monkeypatch, DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY="ris-specific-key")
    captured = {}

    monkeypatch.setattr(ImgpushUploader, "upload", lambda *a, **kw: "https://example.com/img.jpg")

    class FakeResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"answer": "ok"}

    def fake_post(url, headers=None, **kwargs):
        captured["auth"] = headers.get("Authorization", "")
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    pipeline.pipe(
        user_message="",
        model_id="reverse_image_search",
        messages=_make_image_messages(),
        body={},
    )

    assert captured["auth"] == "Bearer ris-specific-key"


def test_pipe_does_not_attach_user_id_to_imgpush(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    captured_upload_args = {}

    def fake_upload(self, image_bytes, mime_type):
        captured_upload_args["image_bytes"] = image_bytes
        captured_upload_args["mime_type"] = mime_type
        return "https://example.com/img.jpg"

    monkeypatch.setattr(ImgpushUploader, "upload", fake_upload)
    monkeypatch.setattr(DifyChatBridge, "ask", lambda *a, **kw: "ok")

    pipeline.pipe(
        user_message="",
        model_id="reverse_image_search",
        messages=_make_image_messages(),
        body={"user": {"id": "user-secret-id", "email": "user@example.com"}},
    )

    assert "user-secret-id" not in str(captured_upload_args.get("image_bytes", b""))
    assert "user@example.com" not in str(captured_upload_args.get("image_bytes", b""))
