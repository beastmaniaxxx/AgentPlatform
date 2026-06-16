import requests

from _dify_search_bridge import DifyChatBridge
from image_search_bridge import Pipeline


def _make_pipeline(monkeypatch, **env):
    defaults = {
        "DIFY_API_BASE_URL": "http://dify-api:5001/v1",
        "DIFY_IMAGE_SEARCH_APP_API_KEY": "test-image-key",
        "REQUEST_TIMEOUT_SECONDS": "30",
    }
    defaults.update(env)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)
    return Pipeline()


def test_pipeline_id_is_image_search(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    assert pipeline.id == "image_search"


def test_valves_load_from_environment_variables(monkeypatch):
    pipeline = _make_pipeline(monkeypatch, DIFY_IMAGE_SEARCH_APP_API_KEY="my-image-key")
    assert pipeline.valves.DIFY_IMAGE_SEARCH_APP_API_KEY == "my-image-key"
    assert pipeline.valves.DIFY_API_BASE_URL == "http://dify-api:5001/v1"
    assert pipeline.valves.REQUEST_TIMEOUT_SECONDS == 30


def test_pipe_returns_answer_from_dify(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)
    captured = {}

    def fake_ask(self_bridge, query, user_id):
        captured["query"] = query
        captured["user_id"] = user_id
        return "![](https://example.com/a.jpg)\n\n![](https://example.com/b.jpg)"

    monkeypatch.setattr(DifyChatBridge, "ask", fake_ask)

    result = pipeline.pipe(
        user_message="猫の画像",
        model_id="image_search",
        messages=[{"role": "user", "content": "猫の画像"}],
        body={"user": {"id": "user-123"}},
    )

    assert "![](https://example.com/a.jpg)" in result
    assert captured["query"] == "猫の画像"
    assert captured["user_id"] == "user-123"


def test_pipe_returns_error_message_on_connection_error(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    def fake_ask(self_bridge, query, user_id):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(DifyChatBridge, "ask", fake_ask)

    result = pipeline.pipe(
        user_message="test",
        model_id="image_search",
        messages=[{"role": "user", "content": "test"}],
        body={"user": {"id": "user-123"}},
    )

    assert isinstance(result, str)
    assert "⚠️" in result
    assert "画像検索" in result


def test_pipe_returns_error_message_on_timeout(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    def fake_ask(self_bridge, query, user_id):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(DifyChatBridge, "ask", fake_ask)

    result = pipeline.pipe(
        user_message="test",
        model_id="image_search",
        messages=[{"role": "user", "content": "test"}],
        body={},
    )

    assert isinstance(result, str)
    assert "⚠️" in result


def test_pipe_does_not_reraise_exception(monkeypatch):
    pipeline = _make_pipeline(monkeypatch)

    def fake_ask(self_bridge, query, user_id):
        raise requests.exceptions.RequestException("generic error")

    monkeypatch.setattr(DifyChatBridge, "ask", fake_ask)

    result = pipeline.pipe(
        user_message="test",
        model_id="image_search",
        messages=[{"role": "user", "content": "test"}],
        body={},
    )

    assert isinstance(result, str)


def test_pipe_uses_image_search_api_key_not_generic(monkeypatch):
    pipeline = _make_pipeline(monkeypatch, DIFY_IMAGE_SEARCH_APP_API_KEY="image-specific-key")
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"answer": "ok"}

    def fake_post(url, headers=None, **kwargs):
        captured["auth"] = headers.get("Authorization", "")
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    pipeline.pipe(
        user_message="test",
        model_id="image_search",
        messages=[{"role": "user", "content": "test"}],
        body={},
    )

    assert captured["auth"] == "Bearer image-specific-key"
