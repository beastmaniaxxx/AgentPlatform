from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "docker" / "docker-compose.yml"
ENV_EXAMPLE_PATH = ROOT / "docker" / ".env.example"


def _load_compose():
    with COMPOSE_PATH.open(encoding="utf-8") as compose_file:
        return yaml.safe_load(compose_file)


def _load_env_example_keys():
    keys = set()
    for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0])
    return keys


def test_xinference_service_is_declared_for_multimodal_rag():
    compose = _load_compose()

    services = compose["services"]
    assert "xinference" in services

    xinference = services["xinference"]
    assert xinference["image"] == "xprobe/xinference:latest"
    assert xinference["networks"] == ["agentplatform-net"]
    assert xinference["ports"] == ["127.0.0.1:${XINFERENCE_PORT}:9997"]
    assert "xinference-data:/root/.xinference" in xinference["volumes"]
    assert "xinference-data" in compose["volumes"]


def test_xinference_service_requests_gpu_devices():
    compose = _load_compose()
    xinference = compose["services"]["xinference"]

    devices = xinference["deploy"]["resources"]["reservations"]["devices"]
    assert devices == [
        {
            "driver": "nvidia",
            "count": "all",
            "capabilities": ["gpu"],
        }
    ]


def test_multimodal_rag_environment_variables_are_documented():
    keys = _load_env_example_keys()

    assert {
        "XINFERENCE_PORT",
        "IMGPUSH_BROWSER_BASE_URL",
        "DIFY_MULTIMODAL_RAG_APP_API_KEY",
        "DIFY_DATASET_API_KEY",
        "MULTIMODAL_RAG_DATASET_ID",
    }.issubset(keys)
