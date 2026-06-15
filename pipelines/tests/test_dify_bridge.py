import base64

import requests

from dify_bridge import Pipeline

ONE_PIXEL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _make_pipeline(monkeypatch, **env):
    defaults = {
        "DIFY_API_BASE_URL": "http://dify-api:5001/v1",
        "DIFY_APP_API_KEY": "test-app-api-key",
        "REQUEST_TIMEOUT_SECONDS": "30",
    }
    defaults.update(env)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)
    return Pipeline()


def _image_message(text=None):
    content = []
    if text is not None:
        content.append({"type": "text", "text": text})
    content.append(
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{ONE_PIXEL_PNG_BASE64}"},
        }
    )
    return [{"role": "user", "content": content}]


def test_valves_load_from_environment_variables(monkeypatch):
    pipeline = _make_pipeline(
        monkeypatch,
        DIFY_API_BASE_URL="http://dify-api:5001/v1",
        DIFY_APP_API_KEY="my-secret-key",
        REQUEST_TIMEOUT_SECONDS="45",
    )

    assert pipeline.valves.DIFY_API_BASE_URL == "http://dify-api:5001/v1"
    assert pipeline.valves.DIFY_APP_API_KEY == "my-secret-key"
    assert pipeline.valves.REQUEST_TIMEOUT_SECONDS == 45


def test_pipe_sends_text_message_and_returns_answer(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"answer": "こんにちは", "conversation_id": "conv-1"}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    result = pipeline.pipe(
        user_message="こんにちは",
        model_id="dify_bridge",
        messages=[{"role": "user", "content": "こんにちは"}],
        body={"user": {"id": "user-123"}},
    )

    assert result == "こんにちは"
    assert captured["url"] == "http://dify-api:5001/v1/chat-messages"
    assert captured["headers"]["Authorization"] == "Bearer test-app-api-key"
    assert captured["json"]["query"] == "こんにちは"
    assert captured["json"]["response_mode"] == "blocking"
    assert captured["json"]["user"] == "user-123"
    assert captured["timeout"] == 30


def test_pipe_returns_error_message_on_connection_error(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    def fake_post(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "post", fake_post)

    result = pipeline.pipe(
        user_message="こんにちは",
        model_id="dify_bridge",
        messages=[{"role": "user", "content": "こんにちは"}],
        body={"user": {"id": "user-123"}},
    )

    assert isinstance(result, str)
    assert "Dify" in result


def test_pipe_returns_error_message_on_timeout(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    def fake_post(*args, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(requests, "post", fake_post)

    result = pipeline.pipe(
        user_message="こんにちは",
        model_id="dify_bridge",
        messages=[{"role": "user", "content": "こんにちは"}],
        body={"user": {"id": "user-123"}},
    )

    assert isinstance(result, str)
    assert "Dify" in result


def test_pipe_returns_error_message_on_http_error_status(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    class FakeResponse:
        status_code = 401

        def raise_for_status(self):
            raise requests.exceptions.HTTPError("401 Unauthorized")

        def json(self):
            return {}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    result = pipeline.pipe(
        user_message="こんにちは",
        model_id="dify_bridge",
        messages=[{"role": "user", "content": "こんにちは"}],
        body={"user": {"id": "user-123"}},
    )

    assert isinstance(result, str)
    assert "Dify" in result


def test_pipe_falls_back_to_default_user_when_body_has_no_user(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"answer": "ok"}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    pipeline.pipe(
        user_message="hello",
        model_id="dify_bridge",
        messages=[{"role": "user", "content": "hello"}],
        body={},
    )

    assert captured["json"]["user"]


def test_pipe_uploads_image_then_sends_chat_message_with_file_reference(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    calls = []

    class FakeUploadResponse:
        status_code = 201

        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "file-123"}

    class FakeChatResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"answer": "画像を受け取りました"}

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        if url.endswith("/files/upload"):
            return FakeUploadResponse()
        return FakeChatResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    result = pipeline.pipe(
        user_message="この画像を見て",
        model_id="dify_bridge",
        messages=_image_message(text="この画像を見て"),
        body={"user": {"id": "user-123"}},
    )

    assert result == "画像を受け取りました"
    assert calls[0]["url"] == "http://dify-api:5001/v1/files/upload"
    assert calls[0]["files"]["file"][1] == base64.b64decode(ONE_PIXEL_PNG_BASE64)
    assert calls[0]["data"]["user"] == "user-123"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-app-api-key"
    assert calls[1]["url"] == "http://dify-api:5001/v1/chat-messages"
    assert calls[1]["json"]["files"] == [
        {"type": "image", "transfer_method": "local_file", "upload_file_id": "file-123"}
    ]
    assert calls[1]["json"]["query"] == "この画像を見て"


def test_pipe_text_only_message_does_not_call_files_upload(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    calls = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"answer": "ok"}

    def fake_post(url, **kwargs):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    pipeline.pipe(
        user_message="hello",
        model_id="dify_bridge",
        messages=[{"role": "user", "content": "hello"}],
        body={"user": {"id": "user-123"}},
    )

    assert calls == ["http://dify-api:5001/v1/chat-messages"]


def test_pipe_image_only_message_uses_placeholder_query(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    captured = {}

    class FakeUploadResponse:
        status_code = 201

        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "file-456"}

    class FakeChatResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"answer": "ok"}

    def fake_post(url, json=None, **kwargs):
        if url.endswith("/chat-messages"):
            captured["json"] = json
            return FakeChatResponse()
        return FakeUploadResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    pipeline.pipe(
        user_message="",
        model_id="dify_bridge",
        messages=_image_message(text=None),
        body={"user": {"id": "user-123"}},
    )

    assert captured["json"]["query"] == Pipeline.IMAGE_ONLY_QUERY_TEXT


def test_pipe_returns_error_message_on_invalid_image_data(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,A"},
                },
            ],
        }
    ]

    result = pipeline.pipe(
        user_message="",
        model_id="dify_bridge",
        messages=messages,
        body={"user": {"id": "user-123"}},
    )

    assert isinstance(result, str)
    assert "画像" in result


def test_pipe_returns_error_and_skips_chat_messages_when_upload_fails(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        raise requests.exceptions.ConnectionError("upload failed")

    monkeypatch.setattr(requests, "post", fake_post)

    result = pipeline.pipe(
        user_message="この画像を見て",
        model_id="dify_bridge",
        messages=_image_message(text="この画像を見て"),
        body={"user": {"id": "user-123"}},
    )

    assert isinstance(result, str)
    assert "Dify" in result
    assert calls == ["http://dify-api:5001/v1/files/upload"]
