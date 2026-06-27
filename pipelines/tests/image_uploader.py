"""
title: Imgpush Uploader
author: AgentPlatform
version: 0.1.0
description: 画像バイトをimgpushへアップロードし、SerpAPIが到達可能な公開URLを返すヘルパー
requirements: requests
"""

import requests


class ImgpushUploader:
    def __init__(self, internal_url: str, public_base_url: str, timeout: int) -> None:
        self._internal_url = internal_url.rstrip("/")
        self._public_base_url = public_base_url
        self._timeout = timeout

    def upload(self, image_bytes: bytes, mime_type: str) -> str:
        """画像バイトをimgpushへアップロードし、公開URL（文字列）を返す。

        Returns:
            "{public_base_url}/{filename}" 形式の公開URL

        Raises:
            ValueError: public_base_url が未設定（空白のみを含む）の場合
            requests.exceptions.RequestException: imgpush接続/タイムアウト/HTTPエラー時
        """
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
