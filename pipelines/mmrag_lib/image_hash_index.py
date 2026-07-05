"""multimodal-rag用のローカル画像ハッシュ副インデックス。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from io import BytesIO
from pathlib import Path
import tempfile

import imagehash
from PIL import Image


INDEX_VERSION = 1


@dataclass(frozen=True)
class ImageHashes:
    sha256: str
    phash: str
    dhash: str


@dataclass(frozen=True)
class HashEntry:
    filename: str
    sha256: str
    phash: str
    title: str
    dhash: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "HashEntry":
        return cls(
            filename=str(data["filename"]),
            sha256=str(data["sha256"]),
            phash=str(data["phash"]),
            dhash=str(data.get("dhash", "")),
            title=str(data.get("title", "")),
        )

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "phash": self.phash,
            "dhash": self.dhash,
            "title": self.title,
        }


@dataclass(frozen=True)
class HashMatch:
    entry: HashEntry
    match_type: str
    distance: int


class ImageHashIndex:
    def __init__(self, index_path: str | Path) -> None:
        self._index_path = Path(index_path)

    def compute(self, image_bytes: bytes) -> ImageHashes:
        with Image.open(BytesIO(image_bytes)) as image:
            normalized = image.convert("RGB")
            return ImageHashes(
                sha256=hashlib.sha256(image_bytes).hexdigest(),
                phash=str(imagehash.phash(normalized)),
                dhash=str(imagehash.dhash(normalized)),
            )

    def add(self, entry: HashEntry) -> bool:
        entries = self._load_entries()
        if any(existing.sha256 == entry.sha256 for existing in entries):
            return False

        entries.append(entry)
        self._write_entries(entries)
        return True

    def query(self, image_bytes: bytes, max_distance: int) -> list[HashMatch]:
        query_hashes = self.compute(image_bytes)
        exact_matches: list[HashMatch] = []
        near_matches: list[HashMatch] = []

        for entry in self._load_entries():
            if entry.sha256 == query_hashes.sha256:
                exact_matches.append(HashMatch(entry=entry, match_type="exact", distance=0))
                continue

            distance = self._hash_distance(query_hashes.phash, entry.phash)
            if distance <= max_distance:
                near_matches.append(
                    HashMatch(entry=entry, match_type="near", distance=distance)
                )

        near_matches.sort(key=lambda match: (match.distance, match.entry.filename))
        return exact_matches + near_matches

    def _load_entries(self) -> list[HashEntry]:
        if not self._index_path.exists():
            return []

        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            return [
                HashEntry.from_dict(entry)
                for entry in data.get("entries", [])
                if isinstance(entry, dict)
            ]
        except (OSError, ValueError, KeyError, TypeError):
            return []

    def _write_entries(self, entries: list[HashEntry]) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": INDEX_VERSION,
            "entries": [entry.to_dict() for entry in entries],
        }

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self._index_path.parent,
            delete=False,
        ) as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_path = Path(temp_file.name)

        temp_path.replace(self._index_path)

    @staticmethod
    def _hash_distance(left: str, right: str) -> int:
        return imagehash.hex_to_hash(left) - imagehash.hex_to_hash(right)
