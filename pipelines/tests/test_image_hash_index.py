import hashlib
import json
from io import BytesIO

from PIL import Image, ImageDraw

from image_hash_index import HashEntry, ImageHashIndex


def _png_bytes(pattern="diagonal", size=(64, 64)):
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    if pattern == "diagonal":
        for offset in range(-size[1], size[0], 8):
            draw.line((offset, 0, offset + size[1], size[1]), fill="black", width=3)
    elif pattern == "cross":
        draw.rectangle((0, 0, size[0] - 1, size[1] - 1), fill="black")
        draw.line((0, 0, size[0], size[1]), fill="white", width=4)
        draw.line((0, size[1], size[0], 0), fill="white", width=4)
    else:
        draw.ellipse((8, 8, size[0] - 8, size[1] - 8), fill="black")

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _resized_png_bytes(image_bytes):
    image = Image.open(BytesIO(image_bytes))
    image = image.resize((60, 60)).resize((64, 64))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_compute_returns_sha256_phash_and_dhash(tmp_path):
    image_bytes = _png_bytes("diagonal")
    index = ImageHashIndex(tmp_path / "index.json")

    hashes = index.compute(image_bytes)

    assert hashes.sha256 == hashlib.sha256(image_bytes).hexdigest()
    assert len(hashes.phash) == 16
    assert len(hashes.dhash) == 16


def test_query_returns_empty_when_index_file_does_not_exist(tmp_path):
    index = ImageHashIndex(tmp_path / "missing.json")

    assert index.query(_png_bytes("diagonal"), max_distance=8) == []


def test_add_persists_entry_and_skips_duplicate_sha(tmp_path):
    index_path = tmp_path / "index.json"
    image_bytes = _png_bytes("diagonal")
    index = ImageHashIndex(index_path)
    hashes = index.compute(image_bytes)
    entry = HashEntry(
        filename="diagonal.png",
        sha256=hashes.sha256,
        phash=hashes.phash,
        dhash=hashes.dhash,
        title="diagonal",
    )

    assert index.add(entry) is True
    assert index.add(entry) is False

    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["entries"] == [entry.to_dict()]


def test_query_returns_exact_match_first_then_near_matches_by_distance(tmp_path):
    index_path = tmp_path / "index.json"
    index = ImageHashIndex(index_path)
    original = _png_bytes("diagonal")
    near = _resized_png_bytes(original)

    original_hashes = index.compute(original)
    near_hashes = index.compute(near)
    index.add(
        HashEntry(
            filename="near.png",
            sha256=near_hashes.sha256,
            phash=near_hashes.phash,
            dhash=near_hashes.dhash,
            title="near",
        )
    )
    index.add(
        HashEntry(
            filename="original.png",
            sha256=original_hashes.sha256,
            phash=original_hashes.phash,
            dhash=original_hashes.dhash,
            title="original",
        )
    )

    matches = index.query(original, max_distance=8)

    assert [match.entry.filename for match in matches] == ["original.png", "near.png"]
    assert matches[0].match_type == "exact"
    assert matches[0].distance == 0
    assert matches[1].match_type == "near"
    assert matches[1].entry.sha256 != original_hashes.sha256
    assert matches[1].distance <= 8


def test_query_excludes_unrelated_images(tmp_path):
    index = ImageHashIndex(tmp_path / "index.json")
    query = _png_bytes("diagonal")
    unrelated = _png_bytes("cross")
    unrelated_hashes = index.compute(unrelated)
    index.add(
        HashEntry(
            filename="cross.png",
            sha256=unrelated_hashes.sha256,
            phash=unrelated_hashes.phash,
            dhash=unrelated_hashes.dhash,
            title="cross",
        )
    )

    assert index.query(query, max_distance=4) == []


def test_load_ignores_corrupt_index_as_empty_for_query(tmp_path):
    index_path = tmp_path / "index.json"
    index_path.write_text("{not json", encoding="utf-8")
    index = ImageHashIndex(index_path)

    assert index.query(_png_bytes("diagonal"), max_distance=8) == []
