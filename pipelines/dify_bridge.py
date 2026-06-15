"""
title: Dify Bridge
author: AgentPlatform
version: 0.1.0
description: Open WebUIのチャットメッセージをDifyワークフローへ中継するPipeline
requirements: requests, pydantic
"""

import base64
import mimetypes
import os

import requests
from pydantic import BaseModel


class Pipeline:
    IMAGE_ONLY_QUERY_TEXT = "画像を受信しました。内容を確認してください。"

    class Valves(BaseModel):
        DIFY_API_BASE_URL: str
        DIFY_APP_API_KEY: str
        REQUEST_TIMEOUT_SECONDS: int

    def __init__(self):
        self.id = "dify_bridge"
        self.name = "Dify Bridge"
        self.valves = self.Valves(
            DIFY_API_BASE_URL=os.getenv(
                "DIFY_API_BASE_URL", "http://dify-api:5001/v1"
            ),
            DIFY_APP_API_KEY=os.getenv("DIFY_APP_API_KEY", ""),
            REQUEST_TIMEOUT_SECONDS=int(
                os.getenv("REQUEST_TIMEOUT_SECONDS", "60")
            ),
        )

    def pipe(self, user_message: str, model_id: str, messages: list, body: dict) -> str:
        """Open WebUIからのメッセージをDify Chat APIへ中継する。

        pipe()は同期的にDify APIの応答を待つ。この間、Open WebUIは標準の
        処理中インジケーターを表示するため、別途の中間状態送信は行わない。
        Dify API呼び出しの例外は伝播させず、ユーザー向けのエラーメッセージ
        文字列を返す。

        メッセージに画像（data URI形式のimage_url）が含まれる場合は、
        `/files/upload`でアップロードしたうえで`upload_file_id`を
        `chat-messages`の`files`に含めて転送する。アップロードに失敗した
        場合は`chat-messages`を呼び出さずエラーメッセージを返す。
        """
        user_id = self._resolve_user_id(body)

        try:
            text, image = self._extract_content(messages)
        except ValueError as exc:
            return self._invalid_image_message(exc)

        payload = {
            "inputs": {},
            "response_mode": "blocking",
            "user": user_id,
        }

        try:
            if image is not None:
                payload["files"] = [
                    {
                        "type": "image",
                        "transfer_method": "local_file",
                        "upload_file_id": self._upload_file(image, user_id),
                    }
                ]
                payload["query"] = text or self.IMAGE_ONLY_QUERY_TEXT
            else:
                payload["query"] = user_message

            response = requests.post(
                f"{self.valves.DIFY_API_BASE_URL}/chat-messages",
                headers=self._headers(),
                json=payload,
                timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            return self._connection_error_message(exc)

        return response.json().get("answer", "")

    def _upload_file(self, image: dict, user_id: str) -> str:
        extension = mimetypes.guess_extension(image["mime_type"]) or ""
        response = requests.post(
            f"{self.valves.DIFY_API_BASE_URL}/files/upload",
            headers=self._headers(),
            files={"file": (f"upload{extension}", image["bytes"], image["mime_type"])},
            data={"user": user_id},
            timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["id"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.valves.DIFY_APP_API_KEY}"}

    @staticmethod
    def _resolve_user_id(body: dict) -> str:
        user = (body or {}).get("user") or {}
        return user.get("id") or user.get("email") or "open-webui-user"

    @staticmethod
    def _extract_content(messages: list):
        """直近のメッセージからテキストと画像（あれば）を抽出する。

        `content`が文字列の場合はテキストのみのメッセージとして扱う。
        `content`がリストの場合（OpenAI Vision形式）は、`text`項目を連結し、
        最初の`image_url`項目をdata URIとしてデコードする。
        """
        if not messages:
            return "", None

        content = messages[-1].get("content")
        if not isinstance(content, list):
            return content or "", None

        text_parts = []
        image = None
        for item in content:
            item_type = item.get("type")
            if item_type == "text":
                text_parts.append(item.get("text", ""))
            elif item_type == "image_url" and image is None:
                url = item.get("image_url", {}).get("url", "")
                if url:
                    image = Pipeline._decode_data_uri(url)

        return " ".join(part for part in text_parts if part).strip(), image

    @staticmethod
    def _decode_data_uri(data_uri: str) -> dict:
        header, _, encoded = data_uri.partition(",")
        mime_type = header[len("data:"):].split(";")[0] or "application/octet-stream"
        return {"bytes": base64.b64decode(encoded), "mime_type": mime_type}

    @staticmethod
    def _connection_error_message(exc: Exception) -> str:
        return f"⚠️ Dify環境への接続に失敗しました: {exc}"

    @staticmethod
    def _invalid_image_message(exc: Exception) -> str:
        return f"⚠️ 画像の処理に失敗しました: {exc}"
