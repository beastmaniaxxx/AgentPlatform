import io

import pytest
import requests

from reverse_image_search_bridge import ImgpushUploader


def _make_uploader(internal_url="http://imgpush:5000", public_base_url="https://example.com", timeout=10):
    return ImgpushUploader(internal_url=internal_url, public_base_url=public_base_url, timeout=timeout)


class FakeResponse:
    def __init__(self, status_code=200, filename="abc.jpg"):
        self.status_code = status_code
        self._filename = filename

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)

    def json(self):
        return {"filename": self._filename}


def test_upload_returns_public_url(monkeypatch):
    uploader = _make_uploader(public_base_url="https://example.com")

    def fake_post(url, files=None, timeout=None, **kwargs):
        return FakeResponse(filename="abc.jpg")

    monkeypatch.setattr(requests, "post", fake_post)

    result = uploader.upload(b"imagedata", "image/jpeg")
    assert result == "https://example.com/abc.jpg"


def test_upload_strips_trailing_slash_from_base_url(monkeypatch):
    uploader = _make_uploader(public_base_url="https://example.com/")

    def fake_post(url, files=None, timeout=None, **kwargs):
        return FakeResponse(filename="img.png")

    monkeypatch.setattr(requests, "post", fake_post)

    result = uploader.upload(b"imagedata", "image/png")
    assert result == "https://example.com/img.png"
    assert "//" not in result.replace("://", "")


def test_upload_raises_value_error_when_public_base_url_is_empty(monkeypatch):
    uploader = _make_uploader(public_base_url="")
    with pytest.raises(ValueError):
        uploader.upload(b"imagedata", "image/jpeg")


def test_upload_raises_value_error_when_public_base_url_is_whitespace(monkeypatch):
    uploader = _make_uploader(public_base_url="   ")
    with pytest.raises(ValueError):
        uploader.upload(b"imagedata", "image/jpeg")


def test_upload_raises_request_exception_on_connection_error(monkeypatch):
    uploader = _make_uploader()

    def fake_post(url, files=None, timeout=None, **kwargs):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.exceptions.RequestException):
        uploader.upload(b"imagedata", "image/jpeg")


def test_upload_raises_request_exception_on_timeout(monkeypatch):
    uploader = _make_uploader()

    def fake_post(url, files=None, timeout=None, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.exceptions.RequestException):
        uploader.upload(b"imagedata", "image/jpeg")


def test_upload_raises_request_exception_on_http_error(monkeypatch):
    uploader = _make_uploader()

    def fake_post(url, files=None, timeout=None, **kwargs):
        return FakeResponse(status_code=500)

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.exceptions.RequestException):
        uploader.upload(b"imagedata", "image/jpeg")


def test_upload_posts_to_internal_url(monkeypatch):
    uploader = _make_uploader(internal_url="http://imgpush:5000")
    captured = {}

    def fake_post(url, files=None, timeout=None, **kwargs):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    uploader.upload(b"imagedata", "image/jpeg")

    assert captured["url"] == "http://imgpush:5000/"


def test_upload_sends_file_as_multipart_with_field_name_file(monkeypatch):
    uploader = _make_uploader()
    captured = {}

    def fake_post(url, files=None, timeout=None, **kwargs):
        captured["files"] = files
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    uploader.upload(b"imagedata", "image/jpeg")

    assert "file" in captured["files"]


def test_upload_does_not_send_user_identifying_info(monkeypatch):
    uploader = _make_uploader()
    captured = {}

    def fake_post(url, files=None, timeout=None, **kwargs):
        captured["kwargs"] = kwargs
        captured["files"] = files
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    uploader.upload(b"imagedata", "image/jpeg")

    assert "headers" not in captured["kwargs"] or not any(
        k.lower() in ("authorization", "x-user-id", "x-user-email")
        for k in (captured["kwargs"].get("headers") or {})
    )
