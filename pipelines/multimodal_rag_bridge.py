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
import re
import sys
from typing import Optional

import requests
from pydantic import BaseModel

# Open WebUI Pipelines のローダーはトップレベル .py のみ走査する。共有ヘルパーは
# サブパッケージ mmrag_lib に置く（走査対象外）。ローダー実行時にこのファイルの
# ディレクトリを sys.path へ加え、mmrag_lib を解決できるようにする。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mmrag_lib.image_hash_index import HashMatch, ImageHashIndex
from mmrag_lib.imgpush_client import ImgpushClient, ImgpushUploadResult
from mmrag_lib.ollama_caption import OllamaCaptionClient


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think(text: str) -> str:
    """thinkingモデルの推論トレース(<think>...</think>)を除去する。

    未閉じの <think>（推論が途中で切れた場合）は、それ以降を全て落とす。
    Open WebUI が <think> を思考ブロック扱いして本文を隠す問題を防ぐ。
    """
    if not text:
        return text
    text = _THINK_BLOCK.sub("", text)
    lowered = text.lower()
    idx = lowered.find("<think>")
    if idx != -1:
        text = text[:idx]
    return text.strip()


_INPUT_PROMPT = (
    "検索するにはテキストまたは画像を入力してください。"
    "自鯖内の登録画像から、関連する画像・情報を検索します。"
)

# 自鯖内0件かつフォールバック不可（画像なし、または公開到達URL未設定）の応答。
_NO_RESULT_MESSAGE = "自鯖内に該当する画像・情報が見つかりませんでした。"

# フォールバック発火時に応答先頭へ前置する通知（要件4.3, 4.4）。
_FALLBACK_NOTICE = (
    "🔄 自鯖内では十分な結果が得られなかったため、Web逆画像検索（reverse_image_search）に"
    "切り替えます。\n"
)
_EXTERNAL_SEND_NOTICE = (
    "⚠️ **外部送信通知**: 入力画像は一時的に外部から参照可能なURLとして公開され、"
    "第三者の検索サービス（SerpAPI）へ送信されます。\n\n"
)


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
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            detail = (response.text or "").strip()[:500]
            raise requests.exceptions.HTTPError(f"{exc} | Dify応答: {detail}") from exc
        data = response.json().get("data", {}) or {}
        return data.get("outputs", {}) or {}

    @staticmethod
    def resolve_user_id(body: dict) -> str:
        user = (body or {}).get("user") or {}
        return user.get("id") or user.get("email") or "open-webui-user"


class DifyChatBridge:
    """フォールバック先の reverse_image_search（advanced-chatアプリ）を実行する。"""

    def __init__(self, base_url: str, api_key: str, timeout: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def ask(self, query: str, user_id: str) -> str:
        response = requests.post(
            f"{self._base_url}/chat-messages",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "inputs": {},
                "query": query,
                "response_mode": "blocking",
                "user": user_id,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json().get("answer", "")


class Pipeline:
    class Valves(BaseModel):
        DIFY_API_BASE_URL: str
        DIFY_MULTIMODAL_RAG_APP_API_KEY: str
        DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY: str
        OLLAMA_BASE_URL: str
        MULTIMODAL_RAG_CAPTION_MODEL: str
        IMGPUSH_INTERNAL_URL: str
        IMGPUSH_BROWSER_BASE_URL: str
        IMGPUSH_PUBLIC_BASE_URL: str
        MULTIMODAL_RAG_HASH_INDEX_PATH: str
        MULTIMODAL_RAG_PHASH_MAX_DISTANCE: int
        MULTIMODAL_RAG_MIN_SCORE: float
        REQUEST_TIMEOUT_SECONDS: int

    def __init__(self) -> None:
        self.id = "multimodal_rag"
        self.name = "Multimodal RAG"
        self.valves = self.Valves(
            DIFY_API_BASE_URL=os.getenv("DIFY_API_BASE_URL", "http://dify-api:5001/v1"),
            DIFY_MULTIMODAL_RAG_APP_API_KEY=os.getenv("DIFY_MULTIMODAL_RAG_APP_API_KEY", ""),
            DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY=os.getenv(
                "DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY", ""
            ),
            OLLAMA_BASE_URL=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
            MULTIMODAL_RAG_CAPTION_MODEL=os.getenv("MULTIMODAL_RAG_CAPTION_MODEL", ""),
            IMGPUSH_INTERNAL_URL=os.getenv("IMGPUSH_INTERNAL_URL", "http://imgpush:5000"),
            IMGPUSH_BROWSER_BASE_URL=os.getenv("IMGPUSH_BROWSER_BASE_URL", "http://localhost:5100"),
            IMGPUSH_PUBLIC_BASE_URL=os.getenv("IMGPUSH_PUBLIC_BASE_URL", ""),
            # 既定は pipelines コンテナのバインドマウント配下（登録スクリプトと共有・.env.example と一致）。
            MULTIMODAL_RAG_HASH_INDEX_PATH=os.getenv(
                "MULTIMODAL_RAG_HASH_INDEX_PATH",
                "/app/pipelines/data/multimodal_rag_hash_index.json",
            ),
            MULTIMODAL_RAG_PHASH_MAX_DISTANCE=int(os.getenv("MULTIMODAL_RAG_PHASH_MAX_DISTANCE", "8")),
            # KB意味検索の関連度下限。これ未満のKB結果は「該当なし」とみなしフォールバック判定に含めない。
            MULTIMODAL_RAG_MIN_SCORE=float(os.getenv("MULTIMODAL_RAG_MIN_SCORE", "0.28")),
            REQUEST_TIMEOUT_SECONDS=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")),
        )

    def pipe(self, user_message: str, model_id: str, messages: list, body: dict) -> str:
        """テキスト/画像を ハッシュ照合＋自鯖内KB検索へ統合し、統一フォーマットで返す。

        常に文字列を返し、例外を呼び出し元へ伝播しない。
        """
        user_id = DifyWorkflowBridge.resolve_user_id(body)
        text = self._extract_text(user_message, messages)

        try:
            image = self._extract_image(messages)
        except ValueError:
            image = None

        if not text and image is None:
            return _INPUT_PROMPT

        try:
            hash_matches: list[HashMatch] = []
            upload_result: Optional[ImgpushUploadResult] = None
            if image is not None:
                hash_matches = self._lookup_hash_matches(image["bytes"])
                upload_result = self._upload_query_image(image)  # フォールバック公開URL用
                # クエリ画像のキャプションはPipelineがOllamaを直接呼んで生成する
                # （Difyのthinkingノードは<think>推論を本文へ混入させ検索クエリを汚染するため）。
                caption = self._caption_query_image(image["bytes"])
                if caption:
                    text = f"{text}\n{caption}".strip() if text else caption

            # 検索クエリは常にテキスト（ユーザー入力＋画像キャプション）。ワークフローは
            # テキスト経路でKB検索する（画像はワークフローへ渡さない）。
            outputs = self._run_workflow(text, None, user_id)
            _, kb_items = self._parse_outputs(outputs)
            # 関連度下限でKB結果を絞り込む（multipleモードは常に上位を返しスコアで自動フィルタ
            # されないため、Pipeline側で足切りしてフォールバック判定の精度を担保する）。
            kb_items = self._filter_by_score(kb_items)
            total = len(hash_matches) + len(kb_items)

            if total <= 0:
                # 自鯖内0件。画像があればWeb逆画像検索へフォールバックする（要件4.2-4.5, 5.2）。
                return self._handle_no_local_result(upload_result, user_id)

            return self._render_results(
                hash_matches, kb_items, _strip_think(outputs.get("summary", ""))
            )
        except (ValueError, requests.exceptions.RequestException) as exc:
            return f"⚠️ 自鯖内検索の実行に失敗しました: {exc}"

    def _lookup_hash_matches(self, image_bytes: bytes) -> list[HashMatch]:
        # 索引の読み込み/ハッシュ算出に失敗しても検索は止めず、空一致としてKB検索を継続する。
        try:
            index = ImageHashIndex(self.valves.MULTIMODAL_RAG_HASH_INDEX_PATH)
            return index.query(image_bytes, self.valves.MULTIMODAL_RAG_PHASH_MAX_DISTANCE)
        except Exception:  # noqa: BLE001 - 索引障害で検索全体を止めないための意図的な握り
            return []

    def _upload_query_image(self, image: dict) -> ImgpushUploadResult:
        client = ImgpushClient(
            internal_url=self.valves.IMGPUSH_INTERNAL_URL,
            browser_base_url=self.valves.IMGPUSH_BROWSER_BASE_URL,
            public_base_url=self.valves.IMGPUSH_PUBLIC_BASE_URL,
            timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
        )
        # imgpush(internal)への保存とURL文字列の組み立てのみ。外部送信は行わない。
        return client.upload(image["bytes"], image["mime_type"])

    def _caption_query_image(self, image_bytes: bytes) -> str:
        # 登録時と同一方式（Ollama直呼び・think無効）でクリーンにキャプションする。
        # 失敗しても検索は止めず、ハッシュ照合＋テキストで継続する。
        try:
            client = OllamaCaptionClient(
                base_url=self.valves.OLLAMA_BASE_URL,
                model=self.valves.MULTIMODAL_RAG_CAPTION_MODEL,
                timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
            )
            return client.generate_caption(image_bytes)
        except Exception:  # noqa: BLE001 - キャプション障害で検索全体を止めない
            return ""

    def _handle_no_local_result(
        self, upload_result: Optional[ImgpushUploadResult], user_id: str
    ) -> str:
        # 画像なし（テキストのみ0件）はフォールバック不可（要件5.2）。
        if upload_result is None or not upload_result.public_url:
            return _NO_RESULT_MESSAGE

        # 外部送信を伴うため、通知を必ず前置する（要件4.3, 4.4）。送信失敗時も通知は保持する。
        prefix = f"{_FALLBACK_NOTICE}{_EXTERNAL_SEND_NOTICE}"
        try:
            answer = _strip_think(self._fallback_web_search(upload_result.public_url, user_id))
        except requests.exceptions.RequestException as exc:
            return f"{prefix}⚠️ Web逆画像検索の実行に失敗しました: {exc}"
        return f"{prefix}{answer}"

    def _fallback_web_search(self, public_url: str, user_id: str) -> str:
        # 発火・制御は本Pipelineが所有し、Web検索ロジックはreverse_image_searchへ委譲する（要件4.5）。
        bridge = DifyChatBridge(
            base_url=self.valves.DIFY_API_BASE_URL,
            api_key=self.valves.DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY,
            timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
        )
        return bridge.ask(public_url, user_id)

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

    def _filter_by_score(self, kb_items: list) -> list:
        threshold = self.valves.MULTIMODAL_RAG_MIN_SCORE
        kept = []
        for item in kb_items:
            if not isinstance(item, dict):
                continue
            try:
                score = float(item.get("score", 0) or 0)
            except (TypeError, ValueError):
                score = 0.0
            if score >= threshold:
                kept.append(item)
        return kept

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
    def _extract_text(user_message, messages: list) -> str:
        """user_message（文字列 or マルチモーダルなcontentリスト）からテキストを抽出する。

        Open WebUI は画像付きメッセージで user_message を
        [{"type":"text",...}, {"type":"image_url",...}] のリストで渡す。
        空のときは messages[-1].content からも拾う。
        """
        def _from_content(content) -> str:
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = [
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                return "\n".join(part for part in parts if part).strip()
            return ""

        text = _from_content(user_message)
        if not text and messages:
            text = _from_content(messages[-1].get("content"))
        return text

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
