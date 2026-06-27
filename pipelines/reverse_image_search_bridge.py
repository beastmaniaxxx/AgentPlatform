"""
title: Reverse Image Search Bridge
author: AgentPlatform
version: 0.1.0
description: 逆画像検索ワークフロー（reverse_image_search）へ画像を中継するPipeline
requirements: requests, pydantic
"""

import base64
import os
from typing import Optional

import requests
from pydantic import BaseModel


class ImgpushUploader:
    def __init__(self, internal_url: str, public_base_url: str, timeout: int) -> None:
        self._internal_url = internal_url.rstrip("/")
        self._public_base_url = public_base_url
        self._timeout = timeout

    def upload(self, image_bytes: bytes, mime_type: str) -> str:
        if not (self._public_base_url or "").strip():
            raise ValueError(
                "IMGPUSH_PUBLIC_BASE_URL が未設定です。"
                "imgpushを公開到達可能にした後、公開ベースURLを設定してください。"
            )
        response = requests.post(
            f"{self._internal_url}/",
            files={"file": ("upload", image_bytes, mime_type)},
            timeout=self._timeout,
        )
        response.raise_for_status()
        filename = response.json()["filename"]
        base = self._public_base_url.rstrip("/")
        return f"{base}/{filename}"


_PRIVACY_NOTICE = (
    "⚠️ **プライバシー通知**: アップロードされた画像は一時的に外部から参照可能なURLとして公開され、"
    "第三者の検索サービス（SerpAPI）へ送信されます。\n\n"
)


class DifyChatBridge:
    def __init__(self, base_url: str, api_key: str, timeout: int) -> None:
        self._base_url = base_url
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

    @staticmethod
    def resolve_user_id(body: dict) -> str:
        user = (body or {}).get("user") or {}
        return user.get("id") or user.get("email") or "open-webui-user"


class Pipeline:
    class Valves(BaseModel):
        DIFY_API_BASE_URL: str
        DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY: str
        IMGPUSH_INTERNAL_URL: str
        IMGPUSH_PUBLIC_BASE_URL: str
        REQUEST_TIMEOUT_SECONDS: int

    def __init__(self) -> None:
        self.id = "reverse_image_search"
        self.name = "Reverse Image Search"
        self.valves = self.Valves(
            DIFY_API_BASE_URL=os.getenv("DIFY_API_BASE_URL", "http://dify-api:5001/v1"),
            DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY=os.getenv(
                "DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY", ""
            ),
            IMGPUSH_INTERNAL_URL=os.getenv("IMGPUSH_INTERNAL_URL", "http://imgpush:5000"),
            IMGPUSH_PUBLIC_BASE_URL=os.getenv("IMGPUSH_PUBLIC_BASE_URL", ""),
            REQUEST_TIMEOUT_SECONDS=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")),
        )

    def pipe(self, user_message: str, model_id: str, messages: list, body: dict) -> str:
        """画像付きメッセージを逆画像検索フローへ中継し、通知+結果またはエラー文字列を返す。

        画像を検知した全経路（成功/エラー）でプライバシー通知を応答先頭に前置する。
        例外は呼び出し元に伝播しない。
        """
        user_id = DifyChatBridge.resolve_user_id(body)

        try:
            image = self._extract_image(messages)
        except ValueError as exc:
            return f"{_PRIVACY_NOTICE}⚠️ 画像の処理に失敗しました: {exc}"

        if image is None:
            return "画像を添付してから送信してください。逆画像検索を実行するには画像が必要です。"

        try:
            uploader = ImgpushUploader(
                internal_url=self.valves.IMGPUSH_INTERNAL_URL,
                public_base_url=self.valves.IMGPUSH_PUBLIC_BASE_URL,
                timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
            )
            public_url = uploader.upload(image["bytes"], image["mime_type"])

            bridge = DifyChatBridge(
                base_url=self.valves.DIFY_API_BASE_URL,
                api_key=self.valves.DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY,
                timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
            )
            answer = bridge.ask(public_url, user_id)
            return f"{_PRIVACY_NOTICE}{answer}"
        except ValueError as exc:
            return f"{_PRIVACY_NOTICE}⚠️ 逆画像検索の実行に失敗しました: {exc}"
        except requests.exceptions.RequestException as exc:
            return f"{_PRIVACY_NOTICE}⚠️ 逆画像検索の実行に失敗しました: {exc}"

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
        except Exception as exc:
            raise ValueError(f"data URI のデコードに失敗しました: {exc}") from exc
