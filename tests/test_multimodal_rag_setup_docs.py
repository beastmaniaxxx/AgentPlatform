from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "multimodal-rag-dify-kb-setup.md"


def test_task2_setup_doc_covers_manual_dify_and_ollama_steps():
    doc = DOC_PATH.read_text(encoding="utf-8")

    assert "Ollama" in doc
    assert "Dify管理画面" in doc
    assert "テキストKB" in doc
    assert "hybrid" in doc
    assert "weighted score" in doc
    assert "Dataset APIキー" in doc
    assert "MULTIMODAL_RAG_CAPTION_MODEL" in doc
    assert "DIFY_DATASET_API_KEY" in doc
    assert "MULTIMODAL_RAG_DATASET_ID" in doc
    assert "scripts/check_multimodal_rag_setup.py" in doc
