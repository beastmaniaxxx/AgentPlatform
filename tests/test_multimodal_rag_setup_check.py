import importlib.util
from pathlib import Path

import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "check_multimodal_rag_setup.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_multimodal_rag_setup", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_env_file_reads_required_multimodal_rag_values(tmp_path):
    module = _load_module()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "DIFY_DATASET_API_KEY=dataset-key",
                "MULTIMODAL_RAG_DATASET_ID=dataset-id",
                "MULTIMODAL_RAG_CAPTION_MODEL=qwen2.5vl:7b",
            ]
        ),
        encoding="utf-8",
    )

    env = module.load_env_file(env_file)

    assert env["DIFY_DATASET_API_KEY"] == "dataset-key"
    assert env["MULTIMODAL_RAG_DATASET_ID"] == "dataset-id"
    assert env["MULTIMODAL_RAG_CAPTION_MODEL"] == "qwen2.5vl:7b"


def test_validate_required_settings_reports_missing_values():
    module = _load_module()

    missing = module.validate_required_settings(
        {
            "DIFY_DATASET_API_KEY": "",
            "MULTIMODAL_RAG_DATASET_ID": "dataset-id",
        }
    )

    assert missing == ["DIFY_DATASET_API_KEY", "MULTIMODAL_RAG_CAPTION_MODEL"]


def test_resolve_api_base_url_prefers_host_port_when_docker_url_is_configured():
    module = _load_module()

    base_url = module.resolve_api_base_url(
        {
            "DIFY_API_BASE_URL": "http://dify-api:5001/v1",
            "DIFY_API_PORT": "5501",
        },
        override=None,
    )

    assert base_url == "http://127.0.0.1:5501/v1"


def test_check_dataset_api_sends_bearer_token_and_dataset_id(monkeypatch):
    module = _load_module()
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "{}"

        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "dataset-id", "name": "multimodal-rag"}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)

    result = module.check_dataset_api(
        "http://127.0.0.1:5001/v1",
        "dataset-key",
        "dataset-id",
        timeout=7,
    )

    assert result["id"] == "dataset-id"
    assert captured["url"] == "http://127.0.0.1:5001/v1/datasets/dataset-id/documents"
    assert captured["headers"] == {"Authorization": "Bearer dataset-key"}
    assert captured["params"] == {"page": 1, "limit": 1}
    assert captured["timeout"] == 7


def test_check_dataset_api_wraps_request_failures(monkeypatch):
    module = _load_module()

    def fake_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(module.SetupCheckError, match="Dataset API"):
        module.check_dataset_api(
            "http://127.0.0.1:5001/v1",
            "dataset-key",
            "dataset-id",
            timeout=7,
        )
