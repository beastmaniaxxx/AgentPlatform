from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "multimodal-rag-setup.md"


def _doc():
    return DOC_PATH.read_text(encoding="utf-8")


def test_setup_guide_exists_and_references_kb_setup_doc():
    doc = _doc()
    # task2 の KB セットアップ手順へ導線を張り、重複させない。
    assert "multimodal-rag-dify-kb-setup.md" in doc


def test_setup_guide_covers_workflow_import_and_app_key():
    doc = _doc()
    assert "workflows/multimodal_rag.yml" in doc
    assert "workflow" in doc.lower()
    assert "DIFY_MULTIMODAL_RAG_APP_API_KEY" in doc


def test_setup_guide_covers_hash_index_shared_path():
    doc = _doc()
    assert "MULTIMODAL_RAG_HASH_INDEX_PATH" in doc
    assert "/app/pipelines/data/multimodal_rag_hash_index.json" in doc
    assert "MULTIMODAL_RAG_PHASH_MAX_DISTANCE" in doc


def test_setup_guide_covers_image_registration_and_pipeline_registration():
    doc = _doc()
    assert "scripts/register_multimodal_kb.py" in doc
    assert "restart pipelines" in doc
    assert "multimodal_rag" in doc
    assert "/models" in doc


def test_setup_guide_covers_fallback_wiring():
    doc = _doc()
    assert "DIFY_REVERSE_IMAGE_SEARCH_APP_API_KEY" in doc
    assert "IMGPUSH_PUBLIC_BASE_URL" in doc
    assert "reverse_image_search" in doc


def test_setup_guide_covers_e2e_verification_paths():
    doc = _doc()
    # 完全一致・準一致・意味関連・フォールバックのE2E確認が記載されていること（要件2.1-2.3, 2.5, 4.5）。
    assert "完全一致" in doc
    assert "準一致" in doc
    assert "フォールバック" in doc
    assert "外部送信" in doc
