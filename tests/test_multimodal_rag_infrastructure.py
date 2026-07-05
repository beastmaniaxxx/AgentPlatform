from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "docker" / "docker-compose.yml"
ENV_EXAMPLE_PATH = ROOT / "docker" / ".env.example"
PIPELINES_REQUIREMENTS_PATH = ROOT / "pipelines" / "requirements.txt"


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


def test_xinference_service_and_volume_are_removed_from_compose():
    compose = _load_compose()

    services = compose["services"]
    volumes = compose["volumes"]

    assert "xinference" not in services
    assert all("xinference" not in service_name.lower() for service_name in services)
    assert "xinference-data" not in volumes


def test_multimodal_rag_environment_variables_are_documented():
    keys = _load_env_example_keys()

    assert "XINFERENCE_PORT" not in keys
    assert {
        "IMGPUSH_BROWSER_BASE_URL",
        "DIFY_MULTIMODAL_RAG_APP_API_KEY",
        "DIFY_DATASET_API_KEY",
        "MULTIMODAL_RAG_DATASET_ID",
        "MULTIMODAL_RAG_CAPTION_MODEL",
        "MULTIMODAL_RAG_HASH_INDEX_PATH",
        "MULTIMODAL_RAG_PHASH_MAX_DISTANCE",
    }.issubset(keys)


def test_multimodal_rag_env_example_uses_caption_and_hash_defaults():
    env_example = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")

    assert "Xinference" not in env_example
    assert "IMGPUSH_BROWSER_BASE_URL=http://localhost:5100" in env_example
    assert "MULTIMODAL_RAG_CAPTION_MODEL=" in env_example
    assert (
        "MULTIMODAL_RAG_HASH_INDEX_PATH=/app/pipelines/data/multimodal_rag_hash_index.json"
        in env_example
    )
    assert "MULTIMODAL_RAG_PHASH_MAX_DISTANCE=8" in env_example


def test_pipeline_requirements_include_image_hash_dependencies():
    requirements = PIPELINES_REQUIREMENTS_PATH.read_text(encoding="utf-8")

    assert "Pillow" in requirements
    assert "imagehash" in requirements
