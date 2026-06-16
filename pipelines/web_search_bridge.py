"""
title: Web Search Bridge
author: AgentPlatform
version: 0.1.0
description: ワード検索ワークフロー（web_search）へのテキストクエリを中継するPipeline
requirements: requests, pydantic
"""

import os

import requests
from pydantic import BaseModel

from _dify_search_bridge import DifyChatBridge


class Pipeline:
    class Valves(BaseModel):
        DIFY_API_BASE_URL: str
        DIFY_WEB_SEARCH_APP_API_KEY: str
        REQUEST_TIMEOUT_SECONDS: int

    def __init__(self):
        self.id = "web_search"
        self.name = "Web Search"
        self.valves = self.Valves(
            DIFY_API_BASE_URL=os.getenv(
                "DIFY_API_BASE_URL", "http://dify-api:5001/v1"
            ),
            DIFY_WEB_SEARCH_APP_API_KEY=os.getenv("DIFY_WEB_SEARCH_APP_API_KEY", ""),
            REQUEST_TIMEOUT_SECONDS=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")),
        )

    def pipe(self, user_message: str, model_id: str, messages: list, body: dict) -> str:
        user_id = DifyChatBridge.resolve_user_id(body)
        bridge = DifyChatBridge(
            base_url=self.valves.DIFY_API_BASE_URL,
            api_key=self.valves.DIFY_WEB_SEARCH_APP_API_KEY,
            timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
        )
        try:
            return bridge.ask(user_message, user_id)
        except requests.exceptions.RequestException as exc:
            return f"⚠️ Web検索の実行に失敗しました: {exc}"
