"""multimodal-rag: Ollama Vision による画像キャプション生成（登録と検索で共有）。

Dify の LLM ノードは thinking モデルの `<think>` 推論を本文へ混入させるため、
検索クエリが汚染される。Pipeline/登録スクリプトは本モジュールで Ollama を直接呼び、
`think=False`＋防御的な `<think>` 除去でクリーンなキャプションを得る。
登録時と検索時で同一プロンプト・同一方式にすることで、キャプション同士の比較精度も揃える。
"""

from __future__ import annotations

import base64
import re

import requests


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

CAPTION_PROMPT = (
    "この画像を自鯖内ナレッジベース検索に使うため、"
    "主要な被写体、色、構図、文字、雰囲気を日本語で簡潔に説明してください。"
    "説明文のみを出力し、前置きや思考過程は書かないでください。"
)


def strip_think(text: str) -> str:
    """thinkingモデルの `<think>...</think>`（未閉じ含む）を除去する。"""
    if not text:
        return text
    text = _THINK_BLOCK.sub("", text)
    idx = text.lower().find("<think>")
    if idx != -1:
        text = text[:idx]
    return text.strip()


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
                "prompt": CAPTION_PROMPT,
                "images": [base64.b64encode(image_bytes).decode("ascii")],
                "think": False,
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
        caption = strip_think(response.json().get("response", "").strip())
        if not caption:
            raise RuntimeError("Ollama Visionのキャプションが空でした。")
        return caption
