import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scene_completion.analysis.interaction_enrichment import resolved_api_id
from scene_completion.analysis.result_views import ResultView
from scene_completion.api.application import create_app
from scene_completion.infrastructure.storage import read_json
from scene_completion.inputs.input_bundles import apply, discover
from scene_completion.inputs.source_documents import read_project_documents
from scene_completion.workflow.engine import Execution, build_pipeline
from scene_completion.workflow.project_service import Workbench


def test_sr_only_contract_never_applies_to_rr_even_on_same_endpoint():
    api = {"id": "SR::Example", "source_layer": "SR", "method": "POST", "address": "/example"}
    i = {
        "direction": "request",
        "layer": "RR",
        "api_id": "SR::Example",
        "operation": {"name": "POST /example"},
    }
    inputs = {"api-parameters": {"apis": [api]}}
    assert resolved_api_id(i, inputs) is None
    assert resolved_api_id({**i, "layer": "SR"}, inputs) == "SR::Example"


@pytest.fixture
def supplied_project(tmp_path):
    dataset = Path(__file__).resolve().parents[1] / "datasets/mini-mall/输入文件"
    if not dataset.is_dir():
        pytest.skip("The development fixture is excluded from the portable package")
    preview, files = discover(directory=str(dataset))
    assert "api_extraction" not in files
    assert "api_extraction" not in preview["missing"]
    service = Workbench(tmp_path)
    sources = {
        layer: [
            {
                "name": files[layer]["name"],
                "content": base64.b64decode(files[layer]["content_base64"]).decode("utf-8-sig"),
            }
        ]
        for layer in ("RR", "SR")
    }
    project = service.create({"name": "mini", "sources": sources, "review_mode": "auto"})
    p = service.run_dir(project["id"])
    # Simulate an existing project with a separately adopted legacy API file.
    old_preview, old_files = discover(
        paths={"api_extraction": str(dataset / "api_extraction.json")}
    )
    apply(service, p, old_preview, old_files, adopt_partial=True)
    apply(service, p, preview, files, adopt_partial=True)
    return service, project["id"], p


def test_supplied_dag_limits_sr_imports_and_reuses_case_when_appended(supplied_project):
    service, rid, p = supplied_project
    plan = service.supplied_case_preview(rid, ["G-001"])
    assert plan["accepted"] == ["G-001"]
    assert len(plan["cases"]) == 5
    project = read_json(p / "project.json")
    documents = {
        role: read_project_documents(
            p, project["sources"][role], "test" if role == "test" else "existing"
        )
        for role in ("RR", "SR", "test")
    }

    def run(case_ids):
        ex = Execution(p / "run", case_ids=case_ids, supplied_only=True)
        build_pipeline(ex, documents["RR"], documents["SR"], documents["test"])
        ex.finish()
        return ex.scheduler.state["tasks"]

    first = run(["G-001"])
    assert first["G-001:fused-ssd"]["status"] == "passed"
    assert first["G-001:rr-ssd"]["status"] == "passed"
    assert first["G-001:sr-ssd"]["status"] == "passed"
    assert first["G-001:existing-branches-source"]["status"] == "passed"
    assert first["api-index"]["status"] == "passed"
    assert not any(k.startswith(("rr-api-", "external-api-", "global-", "G-002:")) for k in first)
    assert "G-001:fused-ssd-source" not in first
    assert "G-001:interaction-normalize" not in first
    branch_path = first["G-001:existing-branches-source"]["output_file"]
    branches = read_json(p / "run" / branch_path)["payload"]["branches"]
    assert len(branches) == 2
    assert {b["behavior_step_id"] for b in branches} == {"S2", "S4"}
    assert all(b["id"].startswith("SR::ordered-") for b in branches)
    assert all(b["behavior_operation_id"] and b["behavior_interaction_id"] for b in branches)
    fused_path = first["G-001:fused-ssd"]["output_file"]
    fused = read_json(p / "run" / fused_path)["payload"]
    assert all(i["api_id"] is None for i in fused["interactions"] if i["layer"] == "RR")
    params = read_json(p / "run" / first["api-parameters"]["output_file"])["payload"]["apis"]
    assert [a["id"] for a in params] == ["SR::API-SR-01"]
    contract = params[0]
    assert contract["address"] == "/ms/v1/products"
    assert contract["responses"] == []
    assert {p["name"] for p in contract["parameters"]} == {"x-service-id", "x-merchant-id"}
    assert contract["source_refs"][0]["source_id"].endswith("-interfaces-facts-v1")
    assert len(contract["bound_interaction_ids"]) == 2
    linked = {i["id"]: i for i in fused["interactions"]}
    assert {linked[i]["direction"] for i in contract["bound_interaction_ids"]} == {
        "request",
        "return",
    }
    reused_id = {
        "layer": "SR",
        "api_id": "API-SR-01",
        "id": "another-interaction",
        "direction": "request",
        "operation": {"name": "POST /ms/v1/products"},
    }
    assert resolved_api_id(reused_id, {"api-parameters": {"apis": [contract]}}) is None
    pending = read_json(p / "run/run_manifest.json")["supplied_sr_api_pending"]
    assert "SR::API-SR-01 功能树未提供失败响应契约" in pending
    assert any("API-SR-01 · name" in note for note in pending)

    result = ResultView(p)
    assert not result.test_source_changed
    assert result.evaluation_scope == "SR"
    assert [item["name"] for item in result.cases()] == ["创建商品"]
    assert result.global_detail()["status"] == "本轮未运行全局分析"

    second = run(["G-001", "G-002"])
    assert second["G-002:fused-ssd"]["status"] == "passed"
    listing = read_json(p / "run" / second["G-002:api-parameters"]["output_file"])["payload"][
        "apis"
    ][0]
    keyword = next(p for p in listing["parameters"] if p["name"] == "keyword")
    assert keyword["location"] == "query" and keyword["required"] is False
    assert any(r["kind"] == "length" for r in keyword["constraints"])
    assert all(p["name"] != "pageSize" for p in listing["parameters"])
    for key in ("G-001:fused-ssd", "G-001:api-parameters", "G-001:existing-branches-source"):
        assert second[key]["identity"] == first[key]["identity"]
        assert second[key]["output_file"] == first[key]["output_file"]


def test_empty_admission_does_not_launch_workbench(supplied_project):
    service, rid, p = supplied_project
    with pytest.raises(ValueError, match="没有通过正式校验"):
        service.start(rid, {"supplied_only": True, "case_ids": ["missing"]})
    assert not (p / "job.json").exists()


def test_behavior_file_can_define_a_case_without_structure_catalogues(tmp_path):
    dataset = Path(__file__).resolve().parents[1] / "datasets/mini-mall/输入文件"
    paths = list((dataset / "行为模型").glob("*/创建商品/SysOperation.json"))
    if not paths:
        pytest.skip("The development fixture is excluded from the portable package")
    path = paths[0]
    uploads = [path, *sorted(path.parent.glob("behaviour/*/*.json"))]
    files = [
        {
            "name": file.name,
            "relative_path": file.relative_to(dataset).as_posix(),
            "content": file.read_text(encoding="utf8"),
        }
        for file in uploads
    ]
    tree = json.loads((dataset / "功能树.json").read_text(encoding="utf8"))
    create = next(item for item in tree["functions"] if item["name"] == "创建商品")
    create["srLayer"]["commands"][0]["attributes"].extend(
        [
            {"name": "response.name", "type": "string", "tags": ["成功响应"], "constraints": []},
            {
                "name": "body.quantity",
                "type": "integer",
                "tags": ["可选"],
                "constraints": [{"rule": "1 <= quantity <= 100"}, {"rule": "默认值 20"}],
            },
        ]
    )
    files.append({"name": "功能树.json", "content": json.dumps(tree, ensure_ascii=False)})
    with TestClient(create_app(tmp_path)) as client:
        response = client.post(
            "/api/projects/from-input-bundle",
            json={"name": "行为验收", "files": files, "adopt_partial": True, "review_mode": "auto"},
        )
        assert response.status_code == 200, response.text
        project = response.json()
        assert project["supplied_only_default"] is True
        assert not project["sources"]["RR"] and not project["sources"]["SR"]
        assert project["input_bundle"]["supplied_cases"]["sr_interface_count"] == 1
        (case_id,) = project["input_bundle"]["supplied_cases"]["accepted"]
        plan = client.get("/api/projects/" + project["id"] + "/import-plan").json()
        by_key = {node["target_key"]: node for node in plan["nodes"]}
        assert "rr-api-map" not in by_key
        assert by_key["api-map"]["input_bindings"][0]["name"] == "功能树.json"
        assert not any(node["stage"].startswith("global-") for node in plan["nodes"])
        sources = by_key[case_id + ":existing-branches-source"]["input_bindings"]
        assert len(sources) == 3 and all(source["mode"] == "reuse" for source in sources)
    run = tmp_path / project["id"] / "run"
    ex = Execution(run, supplied_only=True)
    build_pipeline(ex, [], [], [])
    ex.finish()
    tasks = ex.scheduler.state["tasks"]

    def payload(key):
        assert tasks[key]["status"] == "passed", tasks[key]
        return read_json(run / tasks[key]["output_file"])["payload"]

    assert payload("use-case-align")["groups"][0]["id"] == case_id
    assert payload("rr-use-cases")["cases"][0]["actors"] == ["商家"]
    assert len(payload(case_id + ":existing-branches-source")["branches"]) == 2
    api = payload(case_id + ":api-parameters")["apis"][0]
    quantity = next(p for p in api["parameters"] if p["name"] == "quantity")
    assert quantity["location"] == "body" and quantity["default"] == 20
    assert {(r["kind"], r["value"]) for r in quantity["constraints"]} == {
        ("minimum", 1),
        ("maximum", 100),
    }
    assert [p["name"] for p in api["responses"][0]["parameters"]] == ["name"]


def test_structure_actor_reference_is_optional_for_behavior_run(tmp_path):
    dataset = Path(__file__).resolve().parents[1] / "datasets/mini-mall/输入文件"
    source = dataset / "structure_model_fusion/SR/structure_model.json"
    if not source.is_file():
        pytest.skip("The development fixture is excluded from the portable package")
    value = json.loads(source.read_text(encoding="utf8"))
    case = next(e for e in value["entities"] if e["entity_type"] == "use_case")
    case["actors"] = ["rr-actor-001"]
    preview, _ = discover(files=[{"name": source.name, "content": json.dumps(value)}])
    assert preview["valid"]
