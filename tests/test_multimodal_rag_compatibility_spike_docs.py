from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPIKE_DOC_PATH = ROOT / "docs" / "multimodal-rag-compatibility-spike.md"
RESEARCH_PATH = ROOT / ".kiro" / "specs" / "multimodal-rag" / "research.md"


def test_compatibility_spike_guide_covers_manual_gate_steps():
    text = SPIKE_DOC_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "Xinference",
        "Dify",
        "Visionタグ付きマルチモーダルKB",
        "text→image",
        "image→image",
        "image→text",
        "DIFY_DATASET_API_KEY",
        "MULTIMODAL_RAG_DATASET_ID",
        "research.md",
    ]
    for phrase in required_phrases:
        assert phrase in text


def test_research_file_contains_spike_result_template():
    text = RESEARCH_PATH.read_text(encoding="utf-8")

    required_phrases = [
        "Phase 0 互換性スパイク結果",
        "実施状態",
        "採用モデルID",
        "text→image",
        "image→image",
        "image→text",
        "Rerank",
        "代替判断",
    ]
    for phrase in required_phrases:
        assert phrase in text
