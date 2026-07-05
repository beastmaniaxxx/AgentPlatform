#!/usr/bin/env python
"""画像をハッシュ索引とDifyテキストKBへ登録するCLI。"""

import argparse
import base64
from dataclasses import dataclass
import mimetypes
import os
from pathlib import Path
import socket
import sys
from typing import Callable, Mapping
from urllib.parse import urlparse, urlunparse

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "pipelines"
DEFAULT_ENV_PATH = REPO_ROOT / "docker" / ".env"

if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))

from mmrag_lib.image_hash_index import HashEntry, HashMatch, ImageHashes, ImageHashIndex  # noqa: E402
from mmrag_lib.imgpush_client import ImageValidationError, ImgpushClient  # noqa: E402


DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_OLLAMA_BASE_URL = "http://ollama:11434"
DEFAULT_DIFY_API_BASE_URL = "http://dify-api:5001/v1"


@dataclass(frozen=True)
class RegisterSummary:
    processed: int = 0
    registered: int = 0
    skipped: int = 0
    failed: int = 0

    def with_processed(self) -> "RegisterSummary":
        return RegisterSummary(
            processed=self.processed + 1,
            registered=self.registered,
            skipped=self.skipped,
            failed=self.failed,
        )

    def with_registered(self) -> "RegisterSummary":
        return RegisterSummary(
            processed=self.processed,
            registered=self.registered + 1,
            skipped=self.skipped,
            failed=self.failed,
        )

    def with_skipped(self) -> "RegisterSummary":
        return RegisterSummary(
            processed=self.processed,
            registered=self.registered,
            skipped=self.skipped + 1,
            failed=self.failed,
        )

    def with_failed(self) -> "RegisterSummary":
        return RegisterSummary(
            processed=self.processed,
            registered=self.registered,
            skipped=self.skipped,
            failed=self.failed + 1,
        )


class RegisterConfigError(RuntimeError):
    """登録CLIの設定不足または入力不備。"""


class OllamaCaptionClient:
    def __init__(self, base_url: str, model: str, timeout: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def generate_caption(self, image_bytes: bytes) -> str:
        response = requests.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": (
                    "この画像を自鯖内ナレッジベース検索に使うため、"
                    "主要な被写体、色、構図、文字、雰囲気を日本語で簡潔に説明してください。"
                ),
                "images": [base64.b64encode(image_bytes).decode("ascii")],
                "stream": False,
            },
            timeout=self._timeout,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            detail = (response.text or "").strip()[:500]
            raise RuntimeError(
                f"Ollamaキャプション生成に失敗しました（HTTP {response.status_code}, "
                f"model={self._model}）: {detail}。Vision対応モデルを指定してください。"
            ) from exc
        caption = response.json().get("response", "").strip()
        if not caption:
            raise RuntimeError("Ollama Visionのキャプションが空でした。")
        return caption


class DifyDatasetClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        dataset_id: str,
        timeout: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._dataset_id = dataset_id
        self._timeout = timeout

    def create_document(self, name: str, text: str) -> dict:
        response = requests.post(
            f"{self._base_url}/datasets/{self._dataset_id}/document/create-by-text",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "name": name,
                "text": text,
                "indexing_technique": "high_quality",
                "process_rule": {"mode": "automatic"},
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {}


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def merged_env(env_file: Path) -> dict[str, str]:
    values = load_env_file(env_file)
    values.update({key: value for key, value in os.environ.items() if value})
    return values


def build_document_text(
    title: str,
    filename: str,
    caption: str,
    image_url: str,
) -> str:
    return "\n".join(
        [
            f"title: {title}",
            f"filename: {filename}",
            f"caption: {caption}",
            "",
            f"![{title}]({image_url})",
        ]
    )


def register_directory(
    image_dir: Path,
    *,
    imgpush_client,
    hash_index,
    caption_client,
    dataset_client,
    logger: Callable[[str], None] = print,
    phash_max_distance: int = 0,
) -> RegisterSummary:
    summary = RegisterSummary()
    for image_path in _iter_candidate_files(image_dir):
        summary = summary.with_processed()
        try:
            image_bytes = image_path.read_bytes()
            mime_type = _guess_mime_type(image_path)
            imgpush_client.validate_image(image_bytes, mime_type)
        except ImageValidationError as exc:
            logger(f"スキップ: {image_path.name}: {exc}")
            summary = summary.with_skipped()
            continue
        except OSError as exc:
            logger(f"失敗: {image_path.name}: {exc}")
            summary = summary.with_failed()
            continue

        try:
            hashes = hash_index.compute(image_bytes)
            if _has_same_sha(hash_index, image_bytes, hashes.sha256, phash_max_distance):
                logger(f"スキップ: {image_path.name}: 登録済みSHAです。")
                summary = summary.with_skipped()
                continue

            upload_result = imgpush_client.upload(image_bytes, mime_type)
            caption = caption_client.generate_caption(image_bytes)
            title = image_path.stem
            document_text = build_document_text(
                title=title,
                filename=upload_result.filename,
                caption=caption,
                image_url=upload_result.internal_url,
            )
            dataset_client.create_document(title, document_text)
            hash_index.add(
                HashEntry(
                    filename=upload_result.filename,
                    sha256=hashes.sha256,
                    phash=hashes.phash,
                    dhash=hashes.dhash,
                    title=title,
                )
            )
            logger(f"登録: {image_path.name} -> {upload_result.filename}")
            summary = summary.with_registered()
        except Exception as exc:
            logger(f"失敗: {image_path.name}: {exc}")
            summary = summary.with_failed()

    return summary


def build_clients(env: Mapping[str, str], timeout: int):
    required = [
        "DIFY_DATASET_API_KEY",
        "MULTIMODAL_RAG_DATASET_ID",
        "MULTIMODAL_RAG_CAPTION_MODEL",
        "MULTIMODAL_RAG_HASH_INDEX_PATH",
        "IMGPUSH_INTERNAL_URL",
        "IMGPUSH_BROWSER_BASE_URL",
    ]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise RegisterConfigError("必須設定が未入力です: " + ", ".join(missing))

    imgpush_client = ImgpushClient(
        internal_url=env["IMGPUSH_INTERNAL_URL"],
        browser_base_url=env["IMGPUSH_BROWSER_BASE_URL"],
        public_base_url=env.get("IMGPUSH_PUBLIC_BASE_URL", ""),
        timeout=timeout,
    )
    hash_index = ImageHashIndex(env["MULTIMODAL_RAG_HASH_INDEX_PATH"])
    caption_client = OllamaCaptionClient(
        base_url=env.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        model=env["MULTIMODAL_RAG_CAPTION_MODEL"],
        timeout=timeout,
    )
    dataset_client = DifyDatasetClient(
        base_url=env.get("DIFY_API_BASE_URL", DEFAULT_DIFY_API_BASE_URL),
        api_key=env["DIFY_DATASET_API_KEY"],
        dataset_id=env["MULTIMODAL_RAG_DATASET_ID"],
        timeout=timeout,
    )
    return imgpush_client, hash_index, caption_client, dataset_client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="画像ディレクトリをmultimodal-ragのDify KBとハッシュ索引へ登録します。"
    )
    parser.add_argument(
        "image_dir",
        type=Path,
        help="登録対象の画像ファイル、または画像を含むディレクトリ",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_PATH,
        help="環境変数ファイル。既定: docker/.env",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="imgpush/Ollama/Dify APIのタイムアウト秒数。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.image_dir.exists():
        print(f"NG: 画像パスが見つかりません: {args.image_dir}")
        return 1

    try:
        env = merged_env(args.env_file)
        env = _resolve_endpoints_for_execution(env, REPO_ROOT)
        imgpush_client, hash_index, caption_client, dataset_client = build_clients(
            env,
            timeout=args.timeout,
        )
        summary = register_directory(
            args.image_dir,
            imgpush_client=imgpush_client,
            hash_index=hash_index,
            caption_client=caption_client,
            dataset_client=dataset_client,
            logger=print,
            phash_max_distance=int(env.get("MULTIMODAL_RAG_PHASH_MAX_DISTANCE", "0")),
        )
    except RegisterConfigError as exc:
        print(f"NG: {exc}")
        return 1

    print(
        "完了: "
        f"processed={summary.processed}, "
        f"registered={summary.registered}, "
        f"skipped={summary.skipped}, "
        f"failed={summary.failed}"
    )
    return 1 if summary.failed else 0


def _host_resolvable(url: str) -> bool:
    """URLのホスト名がこの環境で名前解決できるか。127.0.0.1/localhost は常にTrue。"""
    host = urlparse(url).hostname
    if not host:
        return True
    try:
        socket.gethostbyname(host)
        return True
    except OSError:
        return False


def _to_localhost(url: str, port: str) -> str:
    """コンテナ名URLを 127.0.0.1:<port> へ置き換える（scheme/path は維持）。"""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(netloc=f"127.0.0.1:{port}"))


def _resolve_endpoints_for_execution(env: Mapping[str, str], repo_root: Path) -> dict[str, str]:
    """ホスト実行時、コンテナ名URLとコンテナ内パスをホストから到達可能な値へ自動変換する。

    コンテナ内実行（サービス名が解決できる/`/app/pipelines` が存在する）では変換しない。
    ユーザーが明示した 127.0.0.1 系の値はそのまま使われる。
    """
    resolved = dict(env)

    for url_key, port_key, default_port in (
        ("IMGPUSH_INTERNAL_URL", "IMGPUSH_PORT", "5100"),
        ("DIFY_API_BASE_URL", "DIFY_API_PORT", "5001"),
        ("OLLAMA_BASE_URL", "OLLAMA_HOST_PORT", "11435"),
    ):
        url = resolved.get(url_key, "")
        if url and not _host_resolvable(url):
            resolved[url_key] = _to_localhost(url, resolved.get(port_key, default_port))

    hash_path = resolved.get("MULTIMODAL_RAG_HASH_INDEX_PATH", "")
    container_prefix = "/app/pipelines/"
    if hash_path.startswith(container_prefix) and not Path("/app/pipelines").exists():
        relative = hash_path[len(container_prefix):]
        resolved["MULTIMODAL_RAG_HASH_INDEX_PATH"] = str(repo_root / "pipelines" / relative)

    return resolved


def _iter_candidate_files(image_dir: Path) -> list[Path]:
    if image_dir.is_file():
        return [image_dir]
    return sorted(path for path in image_dir.rglob("*") if path.is_file())


def _guess_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    return mime_type or "application/octet-stream"


def _has_same_sha(
    hash_index,
    image_bytes: bytes,
    sha256: str,
    phash_max_distance: int,
) -> bool:
    for match in hash_index.query(image_bytes, max_distance=phash_max_distance):
        if match.entry.sha256 == sha256:
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
