"""
Dify Chat APIへのテキストクエリ中継を提供する共有ヘルパーモジュール。
web_search_bridge / image_search_bridge の両 Pipeline から使用される。
"""

import requests


class DifyChatBridge:
    def __init__(self, base_url: str, api_key: str, timeout: int):
        self._base_url = base_url
        self._api_key = api_key
        self._timeout = timeout

    def ask(self, query: str, user_id: str) -> str:
        """テキストクエリをDify Chat APIに送信し `answer` を返す。

        接続エラー・タイムアウト・非2xxレスポンス時は
        requests.exceptions.RequestException を発生させる。
        エラーメッセージへの変換は呼び出し元 Pipeline に委ねる。
        """
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
        """Open WebUI の body dict からユーザー識別子を解決する。"""
        user = (body or {}).get("user") or {}
        return user.get("id") or user.get("email") or "open-webui-user"
