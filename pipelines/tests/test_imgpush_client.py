import base64
from io import BytesIO

import pytest
import requests
from PIL import Image

from mmrag_lib.imgpush_client import ImageValidationError, ImgpushClient


def _image_bytes(format_name):
    output = BytesIO()
    image = Image.new("RGB", (1, 1), color=(255, 0, 0))
    image.save(output, format=format_name)
    return output.getvalue()


JPEG_BYTES = _image_bytes("JPEG")
PNG_BYTES = _image_bytes("PNG")
GIF_BYTES = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")


def _make_client(
    internal_url="http://imgpush:5000",
    browser_base_url="http://localhost:5100",
    public_base_url="https://public.example.com",
    timeout=10,
):
    return ImgpushClient(
        internal_url=internal_url,
        browser_base_url=browser_base_url,
        public_base_url=public_base_url,
        timeout=timeout,
    )


class FakeResponse:
    def __init__(self, status_code=200, filename="abc.jpg"):
        self.status_code = status_code
        self._filename = filename

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)

    def json(self):
        return {"filename": self._filename}


@pytest.mark.parametrize(
    "mime_type",
    ["image/jpeg", "image/jpg"],
)
def test_validate_image_accepts_allowed_types_under_2mb(mime_type):
    _make_client().validate_image(JPEG_BYTES, mime_type)


@pytest.mark.parametrize(
    ("image_bytes", "mime_type"),
    [(PNG_BYTES, "image/png"), (GIF_BYTES, "image/gif")],
)
def test_validate_image_accepts_allowed_image_bytes(image_bytes, mime_type):
    _make_client().validate_image(image_bytes, mime_type)


@pytest.mark.parametrize(
    "mime_type",
    ["image/webp", "text/plain", "application/octet-stream", ""],
)
def test_validate_image_rejects_unsupported_types(mime_type):
    with pytest.raises(ImageValidationError, match="JPG/PNG/GIF"):
        _make_client().validate_image(b"image", mime_type)


def test_validate_image_rejects_invalid_image_bytes_even_with_allowed_mime_type():
    with pytest.raises(ImageValidationError, match="JPG/PNG/GIF"):
        _make_client().validate_image(b"not actually an image", "image/jpeg")


def test_validate_image_rejects_images_over_2mb():
    with pytest.raises(ImageValidationError, match="2MB"):
        _make_client().validate_image(b"x" * (2 * 1024 * 1024 + 1), "image/jpeg")


def test_upload_returns_internal_browser_and_public_urls(monkeypatch):
    client = _make_client(
        internal_url="http://imgpush:5000/",
        browser_base_url="http://localhost:5100/",
        public_base_url="https://public.example.com/",
    )
    captured = {}

    def fake_post(url, files=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["files"] = files
        captured["timeout"] = timeout
        captured["kwargs"] = kwargs
        return FakeResponse(filename="abc.jpg")

    monkeypatch.setattr(requests, "post", fake_post)

    result = client.upload(JPEG_BYTES, "image/jpeg")

    assert result.filename == "abc.jpg"
    assert result.internal_url == "http://imgpush:5000/abc.jpg"
    assert result.browser_url == "http://localhost:5100/abc.jpg"
    assert result.public_url == "https://public.example.com/abc.jpg"
    assert captured["url"] == "http://imgpush:5000/"
    assert captured["files"]["file"] == ("upload", JPEG_BYTES, "image/jpeg")
    assert captured["timeout"] == 10
    assert "headers" not in captured["kwargs"]


def test_upload_returns_none_public_url_when_public_base_url_is_empty(monkeypatch):
    client = _make_client(public_base_url="")

    def fake_post(url, files=None, timeout=None, **kwargs):
        return FakeResponse(filename="img.png")

    monkeypatch.setattr(requests, "post", fake_post)

    result = client.upload(PNG_BYTES, "image/png")

    assert result.internal_url == "http://imgpush:5000/img.png"
    assert result.browser_url == "http://localhost:5100/img.png"
    assert result.public_url is None


def test_upload_validates_image_before_posting(monkeypatch):
    client = _make_client()
    called = []

    def fake_post(*args, **kwargs):
        called.append(1)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(ImageValidationError):
        client.upload(b"not supported", "image/webp")

    assert called == []


def test_upload_raises_request_exception_on_connection_error(monkeypatch):
    client = _make_client()

    def fake_post(*args, **kwargs):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.exceptions.RequestException):
        client.upload(JPEG_BYTES, "image/jpeg")


def test_upload_raises_request_exception_on_http_error(monkeypatch):
    client = _make_client()

    def fake_post(*args, **kwargs):
        return FakeResponse(status_code=500)

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.exceptions.RequestException):
        client.upload(JPEG_BYTES, "image/jpeg")
