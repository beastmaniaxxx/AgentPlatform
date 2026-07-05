#!/usr/bin/env python
"""multimodal-rag task 2 のDify KB設定を検証するCLI。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = REPO_ROOT / "docker" / ".env"
REQUIRED_ENV_KEYS = [
    "DIFY_DATASET_API_KEY",
    "MULTIMODAL_RAG_DATASET_ID",
    "MULTIMODAL_RAG_CAPTION_MODEL",
]


class SetupCheckError(RuntimeError):
    """セットアップ検証で復旧可能な不備を検出した。"""


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise SetupCheckError(f".env ファイルが見つかりません: {path}")

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_required_settings(env: Mapping[str, str]) -> list[str]:
    return [key for key in REQUIRED_ENV_KEYS if not env.get(key)]


def resolve_api_base_url(env: Mapping[str, str], override: str | None) -> str:
    if override:
        return override.rstrip("/")

    configured = env.get("DIFY_API_BASE_URL", "").rstrip("/")
    if configured and "://dify-api:" not in configured:
        return configured

    port = env.get("DIFY_API_PORT", "5001")
    return f"http://127.0.0.1:{port}/v1"


def check_dataset_api(
    base_url: str,
    api_key: str,
    dataset_id: str,
    timeout: int,
) -> dict:
    url = f"{base_url.rstrip('/')}/datasets/{dataset_id}/documents"
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            params={"page": 1, "limit": 1},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise SetupCheckError(f"Dataset API の疎通に失敗しました: {exc}") from exc

    try:
        return response.json()
    except ValueError:
        return {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="multimodal-ragのDifyテキストKB/Dataset API設定を検証します。"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_PATH,
        help="検証対象の.envファイルパス。既定: docker/.env",
    )
    parser.add_argument(
        "--api-base-url",
        default=None,
        help=(
            "ホストから到達できるDify API URL。未指定時はDIFY_API_PORTから"
            "http://127.0.0.1:<port>/v1 を組み立てます。"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Dataset API疎通確認のタイムアウト秒数。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        env = load_env_file(args.env_file)
        missing = validate_required_settings(env)
        if missing:
            raise SetupCheckError(
                "必須設定が未入力です: " + ", ".join(missing)
            )

        base_url = resolve_api_base_url(env, args.api_base_url)
        dataset = check_dataset_api(
            base_url=base_url,
            api_key=env["DIFY_DATASET_API_KEY"],
            dataset_id=env["MULTIMODAL_RAG_DATASET_ID"],
            timeout=args.timeout,
        )
    except SetupCheckError as exc:
        print(f"NG: {exc}")
        return 1

    dataset_name = dataset.get("name") or "(name unavailable)"
    print("OK: multimodal-rag のDify Dataset API設定に疎通しました。")
    print(f"Dataset: {dataset_name}")
    print(f"Caption model: {env['MULTIMODAL_RAG_CAPTION_MODEL']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
