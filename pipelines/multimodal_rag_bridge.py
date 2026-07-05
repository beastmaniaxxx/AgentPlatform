"""
title: Multimodal RAG Bridge
author: AgentPlatform
version: 0.1.0
description: 自鯖内マルチモーダルRAG（ローカルハッシュ照合＋caption方式テキストKB検索）を中継するPipeline
requirements: requests, pydantic, Pillow, imagehash
"""

from __future__ import annotations

import base64
import json
import os
from typing import Optional

import requests
from pydantic import BaseModel

from image_hash_index import HashMatch, ImageHashIndex
from imgpush_client import ImgpushClient


_INPUT_PROMPT = (
    "検索するにはテキストまたは画像を入力してください。"
    "自鯖内の登録画像から、関連する画像・情報を検索します。"
)

# 自鯖内に該当が無い場合の応答。フォールバック制御（タスク7.2）で拡張する。
_NO_RESULT_MESSAGE = "自鯖内に該当する画像・情報が見つかりませんでした。"


class DifyWorkflowBridge:
    """Dify workflowモードアプリ（multimodal_rag）を `/workflows/run` で実行する。"""

    def __init__(self, base_url: str, api_key: str, timeout: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def run(self, inputs: dict, files: list, user_id: str) -> dict:
        response = requests.post(
            f"{self._base_url}/workflows/run",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "inputs": inputs,
                "files": files,
                "response_mode": "blocking",
                "user": user_id,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json().get("data", {}) or {}
        return data.get("outputs", {}) or {}

    @staticmethod
    def resolve_user_id(body: dict) -> str:
        user = (body or {}).get("user") or {}
        return user.get("id") or user.get("email") or "open-webui-user"


class Pipeline:
    class Valves(BaseModel):
        DIFY_API_BASE_URL: str
        DIFY_MULTIMODAL_RAG_APP_API_KEY: str
        IMGPUSH_INTERNAL_URL: str
        IMGPUSH_BROWSER_BASE_URL: str
        MULTIMODAL_RAG_HASH_INDEX_PATH: str
        MULTIMODAL_RAG_PHASH_MAX_DISTANCE: int
        REQUEST_TIMEOUT_SECONDS: int

    def __init__(self) -> None:
        self.id = "multimodal_rag"
        self.name = "Multimodal RAG"
        self.valves = self.Valves(
            DIFY_API_BASE_URL=os.getenv("DIFY_API_BASE_URL", "http://dify-api:5001/v1"),
            DIFY_MULTIMODAL_RAG_APP_API_KEY=os.getenv("DIFY_MULTIMODAL_RAG_APP_API_KEY", ""),
            IMGPUSH_INTERNAL_URL=os.getenv("IMGPUSH_INTERNAL_URL", "http://imgpush:5000"),
            IMGPUSH_BROWSER_BASE_URL=os.getenv("IMGPUSH_BROWSER_BASE_URL", "http://localhost:5100"),
            MULTIMODAL_RAG_HASH_INDEX_PATH=os.getenv(
                "MULTIMODAL_RAG_HASH_INDEX_PATH", "/data/multimodal_rag/hash_index.json"
            ),
            MULTIMODAL_RAG_PHASH_MAX_DISTANCE=int(os.getenv("MULTIMODAL_RAG_PHASH_MAX_DISTANCE", "6")),
            REQUEST_TIMEOUT_SECONDS=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")),
        )

    def pipe(self, user_message: str, model_id: str, messages: list, body: dict) -> str:
        """テキスト/画像を ハッシュ照合＋自鯖内KB検索へ統合し、統一フォーマットで返す。

        常に文字列を返し、例外を呼び出し元へ伝播しない。
        """
        user_id = DifyWorkflowBridge.resolve_user_id(body)
        text = (user_message or "").strip()

        try:
            image = self._extract_image(messages)
        except ValueError:
            image = None

        if not text and image is None:
            return _INPUT_PROMPT

        try:
            hash_matches: list[HashMatch] = []
            query_image_url: Optional[str] = None
            if image is not None:
                hash_matches = self._lookup_hash_matches(image["bytes"])
                query_image_url = self._upload_query_image(image)

            outputs = self._run_workflow(text, query_image_url, user_id)
            kb_count, kb_items = self._parse_outputs(outputs)
            total = len(hash_matches) + kb_count

            if total <= 0:
                # 自鯖内0件。Webフォールバックはタスク7.2で実装する。
                return _NO_RESULT_MESSAGE

            return self._render_results(hash_matches, kb_items, outputs.get("summary", ""))
        except (ValueError, requests.exceptions.RequestException) as exc:
            return f"⚠️ 自鯖内検索の実行に失敗しました: {exc}"

    def _lookup_hash_matches(self, image_bytes: bytes) -> list[HashMatch]:
        # 索引の読み込み/ハッシュ算出に失敗しても検索は止めず、空一致としてKB検索を継続する。
        try:
            index = ImageHashIndex(self.valves.MULTIMODAL_RAG_HASH_INDEX_PATH)
            return index.query(image_bytes, self.valves.MULTIMODAL_RAG_PHASH_MAX_DISTANCE)
        except Exception:  # noqa: BLE001 - 索引障害で検索全体を止めないための意図的な握り
            return []

    def _upload_query_image(self, image: dict) -> str:
        client = ImgpushClient(
            internal_url=self.valves.IMGPUSH_INTERNAL_URL,
            browser_base_url=self.valves.IMGPUSH_BROWSER_BASE_URL,
            timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
        )
        result = client.upload(image["bytes"], image["mime_type"])
        return result.internal_url

    def _run_workflow(self, text: str, query_image_url: Optional[str], user_id: str) -> dict:
        bridge = DifyWorkflowBridge(
            base_url=self.valves.DIFY_API_BASE_URL,
            api_key=self.valves.DIFY_MULTIMODAL_RAG_APP_API_KEY,
            timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
        )
        inputs: dict = {"query_text": text}
        files: list = []
        if query_image_url:
            file_ref = {
                "type": "image",
                "transfer_method": "remote_url",
                "url": query_image_url,
            }
            inputs["query_image"] = file_ref
            files.append(file_ref)
        return bridge.run(inputs, files, user_id)

    @staticmethod
    def _parse_outputs(outputs: dict) -> tuple[int, list]:
        try:
            count = int(outputs.get("count", 0) or 0)
        except (TypeError, ValueError):
            count = 0

        items_raw = outputs.get("items", "[]")
        if isinstance(items_raw, str):
            try:
                items = json.loads(items_raw)
            except (TypeError, ValueError):
                items = []
        else:
            items = items_raw or []
        if not isinstance(items, list):
            items = []
        return count, items

    def _render_results(self, hash_matches: list[HashMatch], kb_items: list, summary: str) -> str:
        seen: set[str] = set()
        blocks: list[str] = []

        for match in hash_matches:
            filename = match.entry.filename
            if not filename or filename in seen:
                continue
            seen.add(filename)
            blocks.append(self._hash_block(match))

        for item in kb_items:
            filename = item.get("filename") if isinstance(item, dict) else None
            if not filename or filename in seen:
                continue
            seen.add(filename)
            blocks.append(self._kb_block(item))

        if not blocks:
            return _NO_RESULT_MESSAGE

        parts = [f"🔎 自鯖内で {len(blocks)} 件の関連画像が見つかりました。", "\n\n".join(blocks)]
        if (summary or "").strip():
            parts.append(f"**要約**: {summary.strip()}")
        return "\n\n".join(parts)

    def _hash_block(self, match: HashMatch) -> str:
        filename = match.entry.filename
        title = match.entry.title or filename
        url = self._browser_url(filename)
        if match.match_type == "exact":
            badge = "✅ 完全一致（登録済みの同一画像）"
        else:
            badge = f"🟡 視覚的に酷似（ハッシュ距離 {match.distance}）"
        return f"![{title}]({url})\n- {badge}\n- ファイル名: `{filename}`"

    def _kb_block(self, item: dict) -> str:
        filename = item.get("filename", "")
        title = item.get("title") or filename
        url = self._browser_url(filename)
        lines = [f"![{title}]({url})"]
        text = (item.get("text") or "").strip()
        if text:
            lines.append(f"- {text}")
        source = (item.get("source") or "").strip()
        if source:
            lines.append(f"- 出典: {source}")
        return "\n".join(lines)

    def _browser_url(self, filename: str) -> str:
        base = self.valves.IMGPUSH_BROWSER_BASE_URL.rstrip("/")
        return f"{base}/{filename}"

    @staticmethod
    def _extract_image(messages: list) -> Optional[dict]:
        if not messages:
            return None
        content = messages[-1].get("content")
        if not isinstance(content, list):
            return None
        for item in content:
            if item.get("type") == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url:
                    return Pipeline._decode_data_uri(url)
        return None

    @staticmethod
    def _decode_data_uri(data_uri: str) -> dict:
        try:
            header, _, encoded = data_uri.partition(",")
            mime_type = header[len("data:"):].split(";")[0] or "application/octet-stream"
            return {"bytes": base64.b64decode(encoded), "mime_type": mime_type}
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"data URI のデコードに失敗しました: {exc}") from exc
