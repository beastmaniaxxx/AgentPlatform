import pytest
import requests

from _dify_search_bridge import DifyChatBridge


def _make_bridge(**kwargs):
    defaults = {
        "base_url": "http://dify-api:5001/v1",
        "api_key": "test-key",
        "timeout": 30,
    }
    defaults.update(kwargs)
    return DifyChatBridge(**defaults)


def test_ask_sends_query_and_returns_answer(monkeypatch):
    bridge = _make_bridge()
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"answer": "検索結果です", "conversation_id": "conv-1"}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    result = bridge.ask("Python 最新機能", "user-123")

    assert result == "検索結果です"
    assert captured["url"] == "http://dify-api:5001/v1/chat-messages"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["query"] == "Python 最新機能"
    assert captured["json"]["response_mode"] == "blocking"
    assert captured["json"]["user"] == "user-123"
    assert captured["timeout"] == 30


def test_ask_sends_empty_inputs_dict(monkeypatch):
    bridge = _make_bridge()
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
    bridge.ask("test", "user-123")

    assert captured["json"]["inputs"] == {}


def test_ask_raises_on_connection_error(monkeypatch):
    bridge = _make_bridge()

    def fake_post(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.exceptions.RequestException):
        bridge.ask("query", "user-123")


def test_ask_raises_on_timeout(monkeypatch):
    bridge = _make_bridge()

    def fake_post(*args, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.exceptions.RequestException):
        bridge.ask("query", "user-123")


def test_ask_raises_on_http_error_status(monkeypatch):
    bridge = _make_bridge()

    class FakeResponse:
        status_code = 401

        def raise_for_status(self):
            raise requests.exceptions.HTTPError("401 Unauthorized")

        def json(self):
            return {}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.exceptions.RequestException):
        bridge.ask("query", "user-123")


def test_resolve_user_id_extracts_id():
    body = {"user": {"id": "user-abc", "email": "a@b.com"}}
    assert DifyChatBridge.resolve_user_id(body) == "user-abc"


def test_resolve_user_id_falls_back_to_email():
    body = {"user": {"email": "a@b.com"}}
    assert DifyChatBridge.resolve_user_id(body) == "a@b.com"


def test_resolve_user_id_falls_back_to_default_string():
    assert DifyChatBridge.resolve_user_id({}) == "open-webui-user"
    assert DifyChatBridge.resolve_user_id(None) == "open-webui-user"
