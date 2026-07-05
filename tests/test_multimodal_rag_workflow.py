import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "workflows" / "multimodal_rag.yml"


def _load_workflow():
    with WORKFLOW_PATH.open(encoding="utf-8") as workflow_file:
        return yaml.safe_load(workflow_file)


def _nodes_by_id(workflow):
    return {node["id"]: node for node in workflow["workflow"]["graph"]["nodes"]}


def _normalizer_main():
    workflow = _load_workflow()
    normalize_node = _nodes_by_id(workflow)["normalize_results"]
    namespace = {}
    exec(normalize_node["data"]["code"], namespace)
    return namespace["main"]


def test_multimodal_rag_workflow_is_workflow_mode_with_expected_inputs():
    workflow = _load_workflow()
    start_node = _nodes_by_id(workflow)["start"]

    assert workflow["kind"] == "app"
    assert workflow["app"]["mode"] == "workflow"
    assert workflow["app"]["name"] == "multimodal_rag"

    variables = {variable["variable"]: variable for variable in start_node["data"]["variables"]}
    assert variables["query_text"]["type"] == "paragraph"
    assert variables["query_image"]["type"] == "file"
    assert variables["query_image"]["required"] is False


def test_multimodal_rag_workflow_contains_caption_retrieval_normalize_branch_summary_and_end():
    workflow = _load_workflow()
    nodes = _nodes_by_id(workflow)
    node_types = {node_id: node["data"]["type"] for node_id, node in nodes.items()}

    assert node_types["has_image"] == "if-else"
    assert node_types["caption_query_image"] == "llm"
    assert node_types["build_query_with_caption"] == "code"
    assert node_types["build_query_text_only"] == "code"
    assert node_types["retrieve_caption_kb"] == "knowledge-retrieval"
    assert node_types["retrieve_caption_kb_text"] == "knowledge-retrieval"
    assert node_types["normalize_results"] == "code"
    assert node_types["normalize_results_text"] == "code"
    assert node_types["check_count"] == "if-else"
    assert node_types["check_count_text"] == "if-else"
    assert node_types["summarize_results"] == "llm"
    assert node_types["summarize_results_text"] == "llm"
    assert node_types["end_results"] == "end"
    assert node_types["end_no_results"] == "end"
    assert node_types["end_results_text"] == "end"
    assert node_types["end_no_results_text"] == "end"

    retrieval = nodes["retrieve_caption_kb"]["data"]
    assert "hybrid" in json.dumps(retrieval, ensure_ascii=False).lower()
    assert "weighted" in json.dumps(retrieval, ensure_ascii=False).lower()
    # retrieval_mode は Dify の enum（single/multiple）のみ有効。'hybrid' は search_method 側。
    assert retrieval["retrieval_mode"] in ("single", "multiple")
    assert retrieval["query_variable_selector"] == ["build_query_with_caption", "query"]

    text_retrieval = nodes["retrieve_caption_kb_text"]["data"]
    assert text_retrieval["retrieval_mode"] in ("single", "multiple")
    assert text_retrieval["query_variable_selector"] == ["build_query_text_only", "query"]


def test_normalize_results_code_preserves_order_and_outputs_common_items():
    main = _normalizer_main()

    result = json.dumps(
        [
            {
                "metadata": {"filename": "red-car.jpg", "title": "赤い車"},
                "content": "caption: 赤い車の画像。",
                "score": 0.91,
                "source": "document-1",
            },
            {
                "metadata": {"filename": "blue-car.jpg"},
                "text": "caption: 青い車の画像。",
                "score": 0.72,
            },
        ],
        ensure_ascii=False,
    )

    normalized = main(result)
    items = json.loads(normalized["items"])

    assert normalized["count"] == 2
    assert [item["filename"] for item in items] == ["red-car.jpg", "blue-car.jpg"]
    assert items[0] == {
        "filename": "red-car.jpg",
        "title": "赤い車",
        "text": "caption: 赤い車の画像。",
        "source": "document-1",
        "score": 0.91,
    }


def test_multimodal_rag_workflow_edges_and_end_outputs_are_consistent():
    workflow = _load_workflow()
    node_ids = set(_nodes_by_id(workflow))

    for edge in workflow["workflow"]["graph"]["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids

    end_nodes = [
        node for node in workflow["workflow"]["graph"]["nodes"]
        if node["data"]["type"] == "end"
    ]
    assert end_nodes
    for node in end_nodes:
        output_variables = {output["variable"] for output in node["data"]["outputs"]}
        assert output_variables == {"count", "items", "summary"}


def test_all_end_node_outputs_use_variable_selectors_not_literals():
    # DifyのEndノードは value_selector（上流出力参照）のみを受け付け、定数 value を描画できない。
    # 定数 value を含むと管理画面が「コンポーネントのレンダリング中に予期しないエラー」で失敗する。
    workflow = _load_workflow()
    end_nodes = [
        node for node in workflow["workflow"]["graph"]["nodes"]
        if node["data"]["type"] == "end"
    ]
    assert end_nodes
    for node in end_nodes:
        for output in node["data"]["outputs"]:
            assert "value" not in output, (
                f"End node {node['id']} output {output.get('variable')} uses a literal 'value'"
            )
            selector = output.get("value_selector")
            assert isinstance(selector, list) and len(selector) == 2, (
                f"End node {node['id']} output {output.get('variable')} needs a 2-part value_selector"
            )


def test_zero_result_end_nodes_reference_normalize_outputs():
    workflow = _load_workflow()
    nodes = _nodes_by_id(workflow)

    for end_id, normalize_id in (
        ("end_no_results", "normalize_results"),
        ("end_no_results_text", "normalize_results_text"),
    ):
        outputs = {o["variable"]: o["value_selector"] for o in nodes[end_id]["data"]["outputs"]}
        assert outputs["count"] == [normalize_id, "count"]
        assert outputs["items"] == [normalize_id, "items"]
        assert outputs["summary"] == [normalize_id, "summary_seed"]


def test_normalize_extracts_filename_and_title_from_content_when_metadata_lacks_them():
    # Dify Knowledge Retrieval の metadata は _source/dataset_id 等のみで filename を持たない。
    # filename/title は本文テキストの "filename:"/"title:" 行から拾えること。
    main = _normalizer_main()

    result = json.dumps(
        [
            {
                "metadata": {"_source": "knowledge", "dataset_id": "ds-1", "document_id": "doc-1"},
                "content": "title: seed-red-car\nfilename: Gej3i.jpg\ncaption: 赤い車の画像。",
                "score": 0.39,
            }
        ],
        ensure_ascii=False,
    )

    normalized = main(result)
    items = json.loads(normalized["items"])

    assert normalized["count"] == 1
    assert items[0]["filename"] == "Gej3i.jpg"
    assert items[0]["title"] == "seed-red-car"


def test_normalize_results_code_skips_items_without_filename_and_returns_empty_output():
    main = _normalizer_main()

    normalized = main(
        json.dumps(
            [{"content": "filenameなし", "source": "document-source"}],
            ensure_ascii=False,
        )
    )

    assert normalized == {"count": 0, "items": "[]", "summary_seed": ""}


def test_multimodal_rag_workflow_does_not_reference_user_identity():
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "sys.user_id" not in workflow_text
    assert "sys.email" not in workflow_text
    assert "user_id" not in workflow_text
