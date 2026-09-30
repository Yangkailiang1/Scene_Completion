import re

from scene_completion.assessment import (
    build_crud_dependency_graph,
    extract_reference_test_scenarios,
    extract_reference_test_scenarios_from_json,
    score_scenario_matches,
)
from pathlib import Path


def test_extract_reference_test_spec_markdown_and_validation():
    markdown = """| 编号 | 场景名称 | 类型 | 前置条件 | 触发条件 | 关联需求 | 测试目标 | 预期结果 | 来源定位 |
|---|---|---|---|---|---|---|---|---|
| TEST-1 | 正常浏览 | 正常 | 服务可用 | 请求列表 | UC-1/API-1 | 验证列表 | HTTP 200 | spec.md:1 |
"""
    extracted = extract_reference_test_scenarios(markdown)
    assert extracted["valid"]
    assert extracted["scenario_count"] == 1
    assert extracted["scenarios"][0]["scenario_type"] == "normal"
    assert extract_reference_test_scenarios_from_json(extracted)["valid"]


def test_crud_dependency_graph_uses_same_entity_and_correct_direction():
    model = {
        "use_cases": [
            {"use_case_id": "UC-C", "name": "创建商品"},
            {"use_case_id": "UC-R", "name": "读取商品"},
            {"use_case_id": "UC-U", "name": "更新商品"},
            {"use_case_id": "UC-C2", "name": "创建订单"},
        ],
        "use_case_entity_operations": [
            {"operation_id": "c", "use_case_id": "UC-C", "entity": "Product", "operation": "C"},
            {"operation_id": "c-sku", "use_case_id": "UC-C", "entity": "SKU", "operation": "C"},
            {"operation_id": "self-r", "use_case_id": "UC-C", "entity": "Product", "operation": "R"},
            {"operation_id": "r", "use_case_id": "UC-R", "entity": "Product", "operation": "R", "source_location": "spec:2"},
            {"operation_id": "u", "use_case_id": "UC-R", "entity": "SKU", "operation": "U", "source_location": "spec:3"},
            {"operation_id": "unrelated", "use_case_id": "UC-C2", "entity": "Order", "operation": "C"},
        ],
    }
    graph = build_crud_dependency_graph(model)
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["from_use_case"] == "UC-R"
    assert graph["edges"][0]["to_use_case"] == "UC-C"
    assert graph["edges"][0]["labels"] == "R->C,U->C"
    assert graph["edges"][0]["entities"] == ["Product", "SKU"]
    assert len(graph["four_tuples"]) == 2
    assert '"UC-R" -> "UC-C" [label="R->C,U->C"]' in graph["dot"]
    assert "digraph G {" in graph["dot"]


def test_match_metrics_full_partial_unmatched_and_one_to_many():
    reference = {"scenarios": [{"test_scenario_id": "T1"}, {"test_scenario_id": "T2"}, {"test_scenario_id": "T3"}]}
    generated = {"scenarios": [{"scenario_id": "G1"}, {"scenario_id": "G2"}, {"scenario_id": "G3"}]}
    matches = {"matches": [
        {"test_scenario_id": "T1", "generated_scenario_id": "G1", "match_status": "full", "evidence": "覆盖完整行为"},
        {"test_scenario_id": "T1", "generated_scenario_id": "G2", "match_status": "full", "evidence": "另一个场景共同覆盖"},
        {"test_scenario_id": "T2", "generated_scenario_id": "G3", "match_status": "partial", "evidence": "缺少异常恢复步骤"},
        {"test_scenario_id": "T3", "generated_scenario_id": "G3", "match_status": "unmatched", "evidence": "行为不相符"},
    ]}
    report = score_scenario_matches(reference, generated, matches)
    assert report["valid"]
    assert report["metrics"]["test_scenario_coverage"] == {"numerator": 1, "denominator": 3, "rate": 1 / 3}
    assert report["metrics"]["auto_adoption_proxy"]["numerator"] == 2
    assert report["metrics"]["auto_adoption_proxy"]["denominator"] == 3
    assert report["metrics"]["partial_match_test_scenarios"] == 1
    assert report["metrics"]["unmatched_test_scenarios"] == ["T3"]


def test_terminal_cloud_reference_test_spec_covers_14_use_cases_and_7_ar_groups():
    root = Path(__file__).resolve().parents[1]
    spec = root / "终端云例子" / "test_spec.md"
    source = root / "终端云例子" / "功能设计Delta_spec.md"
    extracted = extract_reference_test_scenarios(spec.read_text(encoding="utf-8"))
    assert extracted["valid"], extracted["errors"]
    scenarios = extracted["scenarios"]
    assert len(scenarios) == 89
    assert {item["scenario_type"] for item in scenarios} == {"normal", "exception", "optional"}
    assert sum(item["scenario_type"] == "normal" for item in scenarios) == 14
    assert sum(item["scenario_type"] == "optional" for item in scenarios) == 19
    assert sum(item["scenario_type"] == "exception" for item in scenarios) == 56
    use_cases = {token for item in scenarios for token in re.findall(r"UCG-\d{3}-UC\d{3}", item["requirements"])}
    ar_groups = {token for item in scenarios for token in re.findall(r"AR-\d{2}", item["requirements"])}
    assert len(use_cases) == 14
    assert ar_groups == {f"AR-{index:02d}" for index in range(1, 8)}
    max_line = len(source.read_text(encoding="utf-8").splitlines())
    for item in scenarios:
        match = re.search(r":(\d+)(?:-(\d+))?", item["source_location"])
        assert match, item["source_location"]
        assert int(match.group(1)) <= max_line
        assert int(match.group(2) or match.group(1)) <= max_line
