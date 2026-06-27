"""
title: Image Search Bridge
author: AgentPlatform
version: 0.1.0
description: 画像検索ワークフロー（image_search）へのテキストクエリを中継するPipeline
requirements: requests, pydantic
"""

import os

import requests
from pydantic import BaseModel


class DifyChatBridge:
    def __init__(self, base_url: str, api_key: str, timeout: int):
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
        DIFY_IMAGE_SEARCH_APP_API_KEY: str
        REQUEST_TIMEOUT_SECONDS: int

    def __init__(self):
        self.id = "image_search"
        self.name = "Image Search"
        self.valves = self.Valves(
            DIFY_API_BASE_URL=os.getenv(
                "DIFY_API_BASE_URL", "http://dify-api:5001/v1"
            ),
            DIFY_IMAGE_SEARCH_APP_API_KEY=os.getenv(
                "DIFY_IMAGE_SEARCH_APP_API_KEY", ""
            ),
            REQUEST_TIMEOUT_SECONDS=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")),
        )

    def pipe(self, user_message: str, model_id: str, messages: list, body: dict) -> str:
        user_id = DifyChatBridge.resolve_user_id(body)
        bridge = DifyChatBridge(
            base_url=self.valves.DIFY_API_BASE_URL,
            api_key=self.valves.DIFY_IMAGE_SEARCH_APP_API_KEY,
            timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
        )
        try:
            return bridge.ask(user_message, user_id)
        except requests.exceptions.RequestException as exc:
            return f"⚠️ 画像検索の実行に失敗しました: {exc}"
