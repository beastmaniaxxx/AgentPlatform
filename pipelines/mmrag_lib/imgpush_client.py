"""imgpushアップロードとマルチモーダルRAG用画像検証の共有ヘルパー。"""

from io import BytesIO
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError
import requests


MAX_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/gif"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "GIF"}


class ImageValidationError(ValueError):
    """画像形式またはサイズがmultimodal-ragの制約に違反している。"""


@dataclass(frozen=True)
class ImgpushUploadResult:
    filename: str
    internal_url: str
    browser_url: str
    public_url: str | None


class ImgpushClient:
    def __init__(
        self,
        internal_url: str,
        browser_base_url: str,
        public_base_url: str = "",
        timeout: int = 60,
    ) -> None:
        self._internal_url = internal_url.rstrip("/")
        self._browser_base_url = browser_base_url.rstrip("/")
        self._public_base_url = public_base_url.rstrip("/") if public_base_url.strip() else ""
        self._timeout = timeout

    def validate_image(self, image_bytes: bytes, mime_type: str) -> None:
        normalized_mime_type = (mime_type or "").lower()
        if normalized_mime_type not in ALLOWED_MIME_TYPES:
            raise ImageValidationError(
                "画像形式はJPG/PNG/GIFのみ対応しています。"
            )
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise ImageValidationError(
                "画像サイズは2MB以下にしてください。"
            )

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.verify()
                image_format = image.format
        except (UnidentifiedImageError, OSError) as exc:
            raise ImageValidationError(
                "画像形式はJPG/PNG/GIFのみ対応しています。"
            ) from exc

        if image_format not in ALLOWED_IMAGE_FORMATS:
            raise ImageValidationError(
                "画像形式はJPG/PNG/GIFのみ対応しています。"
            )

    def upload(self, image_bytes: bytes, mime_type: str) -> ImgpushUploadResult:
        self.validate_image(image_bytes, mime_type)

        response = requests.post(
            f"{self._internal_url}/",
            files={"file": ("upload", image_bytes, mime_type)},
            timeout=self._timeout,
        )
        response.raise_for_status()

        filename = response.json()["filename"]
        return ImgpushUploadResult(
            filename=filename,
            internal_url=self._build_url(self._internal_url, filename),
            browser_url=self._build_url(self._browser_base_url, filename),
            public_url=(
                self._build_url(self._public_base_url, filename)
                if self._public_base_url
                else None
            ),
        )

    @staticmethod
    def _build_url(base_url: str, filename: str) -> str:
        return f"{base_url.rstrip('/')}/{filename}"
