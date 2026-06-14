import requests

from dify_bridge import Pipeline


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
