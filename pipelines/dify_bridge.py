"""
title: Dify Bridge
author: AgentPlatform
version: 0.1.0
description: Open WebUIのチャットメッセージをDifyワークフローへ中継するPipeline
requirements: requests, pydantic
"""

import os

import requests
from pydantic import BaseModel


class Pipeline:
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
        """
        payload = {
            "query": user_message,
            "inputs": {},
            "response_mode": "blocking",
            "user": self._resolve_user_id(body),
        }

        try:
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

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.valves.DIFY_APP_API_KEY}"}

    @staticmethod
    def _resolve_user_id(body: dict) -> str:
        user = (body or {}).get("user") or {}
        return user.get("id") or user.get("email") or "open-webui-user"

    @staticmethod
    def _connection_error_message(exc: Exception) -> str:
        return f"⚠️ Dify環境への接続に失敗しました: {exc}"
