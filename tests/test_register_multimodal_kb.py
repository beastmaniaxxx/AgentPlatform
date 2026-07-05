import importlib.util
import json
from io import BytesIO
from pathlib import Path

import pytest
import requests
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "register_multimodal_kb.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("register_multimodal_kb", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _image_bytes(format_name="PNG", color=(255, 0, 0)):
    output = BytesIO()
    image = Image.new("RGB", (8, 8), color=color)
    image.save(output, format=format_name)
    return output.getvalue()


class FakeUploadResult:
    filename = "red.png"
    internal_url = "http://imgpush:5000/red.png"
    browser_url = "http://localhost:5100/red.png"
    public_url = None


def test_register_directory_skips_invalid_images_and_continues(tmp_path):
    module = _load_module()
    valid_path = tmp_path / "red.png"
    invalid_path = tmp_path / "note.txt"
    valid_path.write_bytes(_image_bytes())
    invalid_path.write_text("not image", encoding="utf-8")
    events = []

    class FakeImgpushClient:
        def validate_image(self, image_bytes, mime_type):
            if mime_type == "text/plain":
                raise module.ImageValidationError("unsupported")

        def upload(self, image_bytes, mime_type):
            events.append(("upload", mime_type))
            return FakeUploadResult()

    class FakeHashIndex:
        def compute(self, image_bytes):
            return module.ImageHashes("sha-red", "phash-red", "dhash-red")

        def query(self, image_bytes, max_distance):
            return []

        def add(self, entry):
            events.append(("index", entry.filename, entry.sha256, entry.title))
            return True

    class FakeCaptionClient:
        def generate_caption(self, image_bytes):
            events.append(("caption", len(image_bytes)))
            return "赤い画像"

    class FakeDatasetClient:
        def create_document(self, name, text):
            events.append(("dataset", name, text))
            return {"id": "doc-red"}

    summary = module.register_directory(
        tmp_path,
        imgpush_client=FakeImgpushClient(),
        hash_index=FakeHashIndex(),
        caption_client=FakeCaptionClient(),
        dataset_client=FakeDatasetClient(),
        logger=lambda message: events.append(("log", message)),
    )

    assert summary == module.RegisterSummary(processed=2, registered=1, skipped=1, failed=0)
    assert ("upload", "image/png") in events
    assert any(event[0] == "dataset" and "filename: red.png" in event[2] for event in events)
    assert any(event[0] == "index" and event[1:] == ("red.png", "sha-red", "red") for event in events)
    assert any(event[0] == "log" and "スキップ" in event[1] for event in events)


def test_register_directory_skips_existing_sha_without_upload_or_dataset(tmp_path):
    module = _load_module()
    image_path = tmp_path / "red.png"
    image_path.write_bytes(_image_bytes())

    class FakeHashIndex:
        def compute(self, image_bytes):
            return module.ImageHashes("sha-red", "phash-red", "dhash-red")

        def query(self, image_bytes, max_distance):
            return [
                module.HashMatch(
                    entry=module.HashEntry(
                        filename="red.png",
                        sha256="sha-red",
                        phash="phash-red",
                        dhash="dhash-red",
                        title="red",
                    ),
                    match_type="exact",
                    distance=0,
                )
            ]

        def add(self, entry):
            raise AssertionError("existing image must not be added")

    class FakeImgpushClient:
        def validate_image(self, image_bytes, mime_type):
            pass

        def upload(self, image_bytes, mime_type):
            raise AssertionError("upload must not be called")

    class FailingClient:
        def __getattr__(self, name):
            raise AssertionError(f"{name} must not be called")

    summary = module.register_directory(
        tmp_path,
        imgpush_client=FakeImgpushClient(),
        hash_index=FakeHashIndex(),
        caption_client=FailingClient(),
        dataset_client=FailingClient(),
        logger=lambda message: None,
    )

    assert summary == module.RegisterSummary(processed=1, registered=0, skipped=1, failed=0)


def test_register_directory_does_not_add_index_when_dataset_api_fails(tmp_path):
    module = _load_module()
    image_path = tmp_path / "red.png"
    image_path.write_bytes(_image_bytes())
    added_entries = []

    class FakeImgpushClient:
        def validate_image(self, image_bytes, mime_type):
            pass

        def upload(self, image_bytes, mime_type):
            return FakeUploadResult()

    class FakeHashIndex:
        def compute(self, image_bytes):
            return module.ImageHashes("sha-red", "phash-red", "dhash-red")

        def query(self, image_bytes, max_distance):
            return []

        def add(self, entry):
            added_entries.append(entry)
            return True

    class FakeCaptionClient:
        def generate_caption(self, image_bytes):
            return "赤い画像"

    class FailingDatasetClient:
        def create_document(self, name, text):
            raise requests.exceptions.ConnectionError("refused")

    summary = module.register_directory(
        tmp_path,
        imgpush_client=FakeImgpushClient(),
        hash_index=FakeHashIndex(),
        caption_client=FakeCaptionClient(),
        dataset_client=FailingDatasetClient(),
        logger=lambda message: None,
    )

    assert summary == module.RegisterSummary(processed=1, registered=0, skipped=0, failed=1)
    assert added_entries == []


def test_ollama_caption_client_sends_image_and_model(monkeypatch):
    module = _load_module()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "赤い車の画像"}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    caption = module.OllamaCaptionClient(
        base_url="http://ollama:11434",
        model="gemma-vision",
        timeout=9,
    ).generate_caption(b"image-bytes")

    assert caption == "赤い車の画像"
    assert captured["url"] == "http://ollama:11434/api/generate"
    assert captured["json"]["model"] == "gemma-vision"
    assert captured["json"]["stream"] is False
    assert captured["json"]["images"] == ["aW1hZ2UtYnl0ZXM="]
    assert captured["timeout"] == 9


def test_dataset_client_creates_document_by_text(monkeypatch):
    module = _load_module()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"document": {"id": "doc-red"}}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    result = module.DifyDatasetClient(
        base_url="http://dify-api:5001/v1",
        api_key="dataset-key",
        dataset_id="dataset-id",
        timeout=8,
    ).create_document("red", "caption")

    assert result == {"document": {"id": "doc-red"}}
    assert captured["url"] == (
        "http://dify-api:5001/v1/datasets/dataset-id/document/create-by-text"
    )
    assert captured["headers"] == {"Authorization": "Bearer dataset-key"}
    assert captured["json"] == {
        "name": "red",
        "text": "caption",
        "indexing_technique": "high_quality",
        "process_rule": {"mode": "automatic"},
    }
    assert captured["timeout"] == 8


def test_build_document_text_contains_caption_image_link_and_metadata():
    module = _load_module()

    text = module.build_document_text(
        title="red",
        filename="red.png",
        caption="赤い画像",
        image_url="http://imgpush:5000/red.png",
    )

    assert "title: red" in text
    assert "filename: red.png" in text
    assert "caption: 赤い画像" in text
    assert "![red](http://imgpush:5000/red.png)" in text
