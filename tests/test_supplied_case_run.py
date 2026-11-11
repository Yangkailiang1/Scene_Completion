import base64
from pathlib import Path

import pytest

from scene_completion.analysis.interaction_enrichment import resolved_api_id
from scene_completion.analysis.result_views import ResultView
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
    params = read_json(p / "run" / first["api-parameters"]["output_file"])["payload"]["apis"]
    assert [a["id"] for a in params] == ["SR::API-SR-01"]
    assert all(r["kind"] == "success" for r in params[0]["responses"])
    assert (
        "SR::API-SR-01 未提供失败响应"
        in read_json(p / "run/run_manifest.json")["supplied_sr_api_pending"]
    )

    result = ResultView(p)
    assert not result.test_source_changed
    assert result.evaluation_scope == "SR"
    assert [item["name"] for item in result.cases()] == ["创建商品"]
    assert result.global_detail()["status"] == "本轮未运行全局分析"

    second = run(["G-001", "G-002"])
    assert second["G-002:fused-ssd"]["status"] == "passed"
    for key in ("G-001:fused-ssd", "G-001:api-parameters", "G-001:existing-branches-source"):
        assert second[key]["identity"] == first[key]["identity"]
        assert second[key]["output_file"] == first[key]["output_file"]


def test_empty_admission_does_not_launch_workbench(supplied_project):
    service, rid, p = supplied_project
    with pytest.raises(ValueError, match="没有通过正式校验"):
        service.start(rid, {"supplied_only": True, "case_ids": ["missing"]})
    assert not (p / "job.json").exists()
