"""Colleague input is independent test evidence, never a positive SSD import."""

import json
from copy import deepcopy

import pytest

from scene_completion.analysis.test_alignment import as_records, known_catalogue
from scene_completion.analysis.validation import validate_result
from scene_completion.inputs.recovered_tests import catalogue, json_cases
from scene_completion.inputs.source_documents import read_documents, validate_evidence
from scene_completion.inputs.test_sources import preview
from scene_completion.workflow.task_partitions import split_task


def usecase(cid="REC-1", name="查询资源"):
    return {
        "id": cid,
        "name": name,
        "purpose": "查询指定资源列表",
        "actors": ["调用平台"],
        "main_success": ["读取集合并返回分页结果"],
        "extensions": [
            {
                "id": "EXT-1",
                "scene_id": "SC@bad",
                "condition": "无效类型",
                "expected_result": "返回错误 HTTP 400",
                "note": "分叉点未确定",
                "evidence": ["EV@UNSEEN-L999"],
            },
            {
                "id": "EXT-2",
                "condition": "未提供可选条件",
                "expected_result": "使用默认值，成功返回",
                "note": "成功备选",
            },
            {
                "id": "EXT-3",
                "condition": "空值",
                "expected_result": "空值处理策略待确认",
                "note": "是否属于异常未定",
            },
            {"id": "EXT-4", "condition": "自行选择排序", "expected_result": "成功", "type": "可选"},
        ],
    }


def document(value=None, pretty=True, ascii=False):
    text = json.dumps(
        value if value is not None else [usecase()],
        ensure_ascii=ascii,
        indent=2 if pretty else None,
    )
    return {
        "source_id": "uploaded-json",
        "name": "colleague.json",
        "channel": "test",
        "lines": [{"number": n, "text": s} for n, s in enumerate(text.splitlines(), 1)],
    }


@pytest.mark.parametrize(
    "pretty,ascii", [(True, False), (False, False), (True, True), (False, True)]
)
def test_json_keeps_types_ids_and_real_file_evidence(pretty, ascii):
    d = document(pretty=pretty, ascii=ascii)
    cat = known_catalogue([d])
    assert [t["scenario_type"] for t in cat["tests"]] == [
        "exception",
        "normal",
        "pending",
        "optional",
    ]
    assert [t["id"] for t in cat["tests"]] == ["REC-1::EXT-" + str(n) for n in range(1, 5)]
    assert preview([d])["counts"] == {"exception": 1, "normal": 1, "optional": 1, "pending": 1}
    assert cat["tests"][0]["source_location"]["json_pointer"] == "/0/extensions/0"
    assert cat["tests"][0]["source_location"]["scene_id"] == "SC@bad"
    assert all(
        ref["source_id"] == "uploaded-json" for t in cat["tests"] for ref in t["source_refs"]
    )
    assert not any("EV@" in ref["source_id"] for t in cat["tests"] for ref in t["source_refs"])
    for t in cat["tests"]:
        validate_evidence(t["source_refs"], [d])
    validate_result("test-inventory", cat, {"test-documents": [d]})
    record = as_records(cat, [d])[0]
    assert record["source_location"] == cat["tests"][0]["source_location"]
    # A branch with an unresolved fork is still an exception if its outcome fails.
    assert cat["tests"][0]["scenario_type"] == "exception"


def test_multiple_cases_can_reuse_extension_ids_without_implicit_case_alignment():
    from scene_completion.analysis.test_alignment import exact_alignment

    cat = known_catalogue([document([usecase(), usecase("REC-2", "更新资源")])])
    assert len({t["id"] for t in cat["tests"]}) == 8
    inputs = {
        "test-inventory": cat,
        "rr-cases": {"cases": [{"id": "REC-1", "name": "完全不同目标"}]},
        "sr-cases": {"cases": []},
        "case-groups": {
            "groups": [{"id": "G", "rr_ids": ["REC-1"], "sr_ids": [], "status": "confirmed"}]
        },
    }
    assert exact_alignment(inputs) is None


@pytest.mark.parametrize(
    "wrapper,pointer",
    [
        (None, "/extensions/0"),
        ("usecases", "/usecases/0/extensions/0"),
        ("use_cases", "/use_cases/0/extensions/0"),
        ("cases", "/cases/0/extensions/0"),
    ],
)
def test_json_wrapper_or_single_case_still_points_into_the_uploaded_file(wrapper, pointer):
    value = {wrapper: [usecase()]} if wrapper else usecase()
    d = document(value)
    cat = known_catalogue([d])
    assert len(cat["tests"]) == 4 and cat["tests"][0]["source_location"]["json_pointer"] == pointer
    validate_evidence(cat["tests"][0]["source_refs"], [d])


@pytest.mark.parametrize(
    "value",
    [
        [usecase(), usecase()],
        [],
        [{"id": "X", "extensions": []}],
        [{**usecase(), "extensions": [usecase()["extensions"][0]] * 2}],
    ],
)
def test_invalid_or_duplicate_json_is_reported_before_project_creation(value):
    with pytest.raises(ValueError):
        catalogue(document(value), strict=True)


def test_duplicate_properties_and_nonfinite_values_are_rejected():
    with pytest.raises(ValueError, match="重复属性"):
        json_cases('{"id":"x","id":"y"}')
    with pytest.raises(ValueError, match="非有限"):
        json_cases("[NaN]")
    empty = known_catalogue([document([{**usecase(), "extensions": []}])])
    assert empty["tests"] == [] and empty["pending"]
    validate_result(
        "test-inventory", empty, {"test-documents": [document([{**usecase(), "extensions": []}])]}
    )


def test_minified_json_partition_has_only_current_exception_and_literal_citation():
    d = document([usecase(), usecase("OTHER", "其他任务")], pretty=False)
    cat = known_catalogue([d])
    original = deepcopy(d)
    units = split_task(
        "test-concerns", {"test-documents": [d], "tests": [d], "test-inventory": cat}
    )
    assert len(units) == 2
    for _, inputs in units:
        assert "tests" not in inputs
        assert len(inputs["test-inventory"]["tests"]) == 1
        t = inputs["test-inventory"]["tests"][0]
        assert t["scenario_type"] == "exception"
        validate_evidence(t["source_refs"], inputs["test-documents"])
        text = inputs["test-documents"][0]["lines"][0]["text"]
        assert "EXT-2" not in text and "SC@bad" in text
        assert inputs["test-documents"][0]["lines"][0]["number"] == 1
    direct = split_task("test-concerns", {"test-documents": [d]})
    assert [k for k, _ in direct] == [k for k, _ in units]
    assert d == original


def test_minified_scenario_source_is_not_misclassified_by_other_types_on_the_same_line():
    from scene_completion.domain.scenario_types import filter_scenarios
    from scene_completion.inputs.test_sources import referenced_record_ids
    from tests.test_workflow import scenario

    d = document(pretty=False)
    cat = known_catalogue([d])
    inputs = {"test-documents": [d], "test-inventory": cat}
    first = cat["tests"][0]
    sc = {**scenario(), "source_refs": first["source_refs"]}
    parsed = as_records(cat, [d])
    assert referenced_record_ids(first["source_refs"], parsed) == {first["id"]}
    assert filter_scenarios({"scenarios": [sc]}, inputs, "test-ground-truth")["scenarios"]
    for test in cat["tests"][1:]:
        sc["source_refs"] = test["source_refs"]
        assert not filter_scenarios({"scenarios": [sc]}, inputs, "test-ground-truth")["scenarios"]


def test_json_upload_versions_and_generic_input_import_use_same_independent_channel(tmp_path):
    from fastapi.testclient import TestClient

    from scene_completion.api.application import create_app
    from scene_completion.inputs.artifact_imports import receive, role_hint, view

    text = "\ufeff" + json.dumps([usecase()], ensure_ascii=False)
    source = {"name": "arbitrary.json", "content": text}
    app = create_app(tmp_path / "data")
    client = TestClient(app)
    p = client.post("/api/test-sources/preview", json={"sources": [source]})
    assert p.status_code == 200 and p.json()["valid"] and p.json()["counts"]["exception"] == 1
    body = {
        "name": "JSON test",
        "sources": {
            "RR": [{"name": "r.md", "content": "RR"}],
            "SR": [{"name": "s.md", "content": "SR"}],
            "test": [source],
        },
        "evaluation_scope": "SR",
    }
    result = client.post("/api/projects", json=body)
    assert result.status_code == 200, result.text
    project = app.state.workbench.run_dir(result.json()["id"])
    meta = json.loads((project / "project.json").read_text())
    assert meta["evaluation_scope"] == "SR"
    original = project / meta["sources"]["test"][0]["path"]
    assert original.suffix == ".json" and original.read_text() == text
    assert len(known_catalogue(read_documents([original], "test"))["tests"]) == 4
    assert role_hint("api-map.json", text.lstrip("\ufeff")) == "test"
    imported = receive(project, [{"name": "another.json", "content": text}])
    row = view(project, imported["received"][0]["id"])
    assert row["role"] == "test" and row["test_preview"]["counts"]["exception"] == 1
    assert row["artifacts"] == []  # test main_success cannot become a positive SSD
    assert (
        client.post("/api/projects", json={**body, "evaluation_scope": "/ms/"}).status_code == 400
    )


def test_json_inventory_node_completes_with_no_model_call(tmp_path):
    from scene_completion.infrastructure.storage import read_json
    from scene_completion.workflow.engine import Execution

    class Client:
        config = {}

        def model(self, *a):
            return "no-paid-model-needed"

        def agent(self, p):
            raise AssertionError("Structured test catalogue must not call LLM")

    ex = Execution(tmp_path / "run", mode="external", client=Client())
    ex.add("test-inventory", "test-inventory", static={"test-documents": [document()]})
    result = ex.finish()
    assert result["complete"]
    node = ex.scheduler.state["tasks"]["test-inventory"]
    value = read_json(tmp_path / "run" / node["output_file"])["payload"]
    assert (
        len(value["tests"]) == 4
        and value["tests"][0]["source_location"]["json_pointer"] == "/0/extensions/0"
    )
