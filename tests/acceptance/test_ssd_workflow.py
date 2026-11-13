"""Offline integration of structured/raw inputs, scheduler and public result APIs."""

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from scene_completion.api.application import create_app
from scene_completion.application import ssd_revision_service as ssd_results
from scene_completion.application.execution import Execution, build_pipeline
from scene_completion.application.project_service import Workbench
from scene_completion.infrastructure.storage import read_json
from scene_completion.inputs.documents.input_bundles import apply, discover
from scene_completion.inputs.documents.source_documents import read_project_documents
from scene_completion.inputs.provenance.ssd_sources import Sources, api_contracts
from scene_completion.review.offline.ssd_review import _parse
from tests.support.paths import ROOT
from tests.support.workflow import fake_pipeline

DATASET = ROOT / "datasets/mini-mall/输入文件"


def imported_project(tmp_path, service=None):
    service = service or Workbench(tmp_path / "projects")
    sources = {
        role: [{"name": name, "content": (DATASET / name).read_text(encoding="utf-8")}]
        for role, name in (("RR", "系统需求_spec.md"), ("SR", "功能设计_spec.md"))
    }
    project = service.create({"name": "SSD mini", "sources": sources, "review_mode": "auto"})
    root = service.run_dir(project["id"])
    preview, files = discover(directory=str(DATASET))
    assert any(row["name"] == "api_extraction.json" for row in files.values())
    assert {"系统需求_spec.md", "功能设计_spec.md"} <= {row["name"] for row in files.values()}
    adopted = apply(service, root, preview, files, adopt_partial=True)
    assert adopted["saved"]
    return service, project["id"], root


def execute(root, case_ids=None, explicit=True):
    metadata = read_json(root / "project.json")
    docs = {
        role: read_project_documents(
            root, metadata["sources"][role], "test" if role == "test" else "existing"
        )
        for role in ("RR", "SR", "test")
    }
    config = {"max_concurrency": 3, "adaptive_concurrency": False}
    if explicit:
        config["workflow_mode"] = "ssd"
    execution = Execution(root / "run", config=config, case_ids=case_ids, supplied_only=True)
    assert execution.client is None and execution.mode == "packets"
    build_pipeline(execution, docs["RR"], docs["SR"], docs["test"])
    manifest = execution.finish()
    return execution, manifest


def test_structured_default_pipeline_five_cases_cache_and_manual_revision(tmp_path):
    _, _, root = imported_project(tmp_path)
    first, manifest = execute(root, explicit=False)
    assert manifest["workflow"] == "ssd-case-v1"
    assert manifest["execution_complete"]
    assert manifest["pending_count"] > 0 and not manifest["complete"]
    assert manifest["recommendation"] == {"enabled": False}
    assert not manifest["global_analysis"]["complete"]
    tasks = first.scheduler.state["tasks"]
    expected = {
        f"UC-{n:03d}:{stage}"
        for n in range(1, 6)
        for stage in ("ssd-prepare", "ssd-resolve", "ssd-compare")
    }
    assert set(first.scheduler.tasks) == expected
    assert all(tasks[key]["status"] == "passed" for key in expected)
    assert not list((root / "run/packets").glob("*.json"))
    index = ssd_results.index(root)
    assert len(index["cases"]) == 5
    assert manifest["metrics"] == index["metrics"]
    current = ssd_results.editor(root, "UC-002")
    documents = {doc["name"]: doc for doc in current["bundle"]["documents"]}
    for name, role in (
        ("系统需求_spec.md", "RR"),
        ("功能设计_spec.md", "SR"),
        ("recovered_usecases.json", "test"),
    ):
        assert documents[name]["role"] == role
        assert documents[name]["content"] == (DATASET / name).read_text(encoding="utf-8")
    bundle = deepcopy(current["bundle"])
    record = bundle["channels"]["E"]["concerns"][0]
    record["condition"] = "运行后人工确认"
    updated = ssd_results.save_revision(
        root, "UC-002", {"base_revision": current["revision"], "bundle": bundle}
    )
    before = {key: (tasks[key]["identity"], tasks[key]["output_file"]) for key in expected}
    again, second = execute(root, explicit=False)
    assert second["execution_complete"]
    after = {
        key: (
            again.scheduler.state["tasks"][key]["identity"],
            again.scheduler.state["tasks"][key]["output_file"],
        )
        for key in expected
    }
    # Human edits invalidate only that case's comparison stage, even when a
    # no-model run leaves its semantic pairs visible for subsequent analysis.
    assert {key for key in expected if before[key] != after[key]} == {"UC-002:ssd-compare"}
    retained = ssd_results.editor(root, "UC-002")
    assert retained["revision"] == updated["revision"]
    assert (
        next(r for r in retained["bundle"]["channels"]["E"]["concerns"] if r["id"] == record["id"])[
            "condition"
        ]
        == "运行后人工确认"
    )


def test_supplied_g_alias_runs_exact_case_from_preview(tmp_path):
    service, rid, root = imported_project(tmp_path)
    preview = service.supplied_case_preview(rid, ["G-002"])
    assert preview["accepted"] == ["G-002"]
    selected = next(row for row in preview["cases"] if row["case_id"] == "G-002")
    assert selected["name"] == "查询商品列表"
    execution, manifest = execute(root, ["G-002"])
    assert manifest["execution_complete"]
    assert manifest["ssd_cases"] == ["UC-002"]
    assert set(execution.scheduler.tasks) == {
        "UC-002:ssd-prepare",
        "UC-002:ssd-resolve",
        "UC-002:ssd-compare",
    }
    assert ssd_results.index(root)["cases"][0]["name"] == selected["name"]


@pytest.mark.parametrize("malformed_json", [False, True])
def test_one_case_failure_does_not_block_other_cases(tmp_path, malformed_json):
    _, _, root = imported_project(tmp_path)
    snapshot = root / read_json(root / "imports/ssd-input.json")["path"]
    broken = next(snapshot.glob("行为模型/*/更新商品/SysOperation.json"))
    value = read_json(broken)
    value["operations"] = {}
    broken.write_text(
        "{ invalid json" if malformed_json else json.dumps(value, ensure_ascii=False),
        encoding="utf-8",
    )
    execution, manifest = execute(root)
    tasks = execution.scheduler.state["tasks"]
    failed = [
        key
        for key, task in tasks.items()
        if key.endswith(":ssd-prepare") and task["status"] in {"failed", "rejected"}
    ]
    assert len(failed) == 1
    if not malformed_json:
        assert failed == ["UC-003:ssd-prepare"]
    assert not manifest["execution_complete"]
    assert all(tasks[f"UC-{n:03d}:ssd-compare"]["status"] == "passed" for n in (1, 2, 4, 5))
    assert {c["id"] for c in ssd_results.index(root)["cases"]} == {
        "UC-001",
        "UC-002",
        "UC-004",
        "UC-005",
    }


def test_editor_revision_conflict_and_offline_http_contract(tmp_path):
    app = create_app(tmp_path / "projects")
    _, rid, root = imported_project(tmp_path, app.state.workbench)
    execute(root, ["UC-002"])
    base = f"/api/projects/{rid}"
    with TestClient(app) as client:
        index = client.get(base + "/ssd-results")
        assert index.status_code == 200
        assert index.json()["cases"][0]["id"] == "UC-002"
        response = client.get(base + "/results/UC-002/editor")
        assert response.status_code == 200
        original = response.json()
        edited = deepcopy(original["bundle"])
        edited["channels"]["E"]["concerns"][0]["condition"] = "在线修改"
        body = {"base_revision": original["revision"], "bundle": edited}
        saved = client.post(base + "/results/UC-002/revisions", json=body)
        assert saved.status_code == 200
        conflict = client.post(base + "/results/UC-002/revisions", json=body)
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["current_revision"] == saved.json()["revision"]
        history = client.get(base + "/results/UC-002/revisions").json()["history"]
        assert len(history) >= 2
        exported = client.post(base + "/ssd-review/export", json={"case_ids": ["UC-002"]})
        assert exported.status_code == 200 and "text/html" in exported.headers["content-type"]
        assert "attachment" in exported.headers["content-disposition"]
        feedback = _parse(exported.text)
        feedback["cases"][0]["bundle"]["channels"]["E"]["concerns"][0]["condition"] = "离线修改"
        content = json.dumps(feedback, ensure_ascii=False)
        preview = client.post(base + "/ssd-review/preview", json={"content": content})
        assert preview.status_code == 200 and preview.json()["cases"][0]["status"] == "ready"
        applied = client.post(
            base + "/ssd-review/apply", json={"content": content, "case_ids": ["UC-002"]}
        )
        assert applied.status_code == 200 and applied.json()["cases"][0]["status"] == "applied"
        repeated = client.post(base + "/ssd-review/apply", json={"content": content})
        assert repeated.status_code == 200 and repeated.json()["cases"][0]["status"] == "unchanged"


def test_raw_inputs_use_legacy_adapter_then_new_workflow_with_semantic_mock(tmp_path):
    rr, sr, tests, mocks = fake_pipeline(tmp_path)
    rr[0]["lines"][-1]["text"] = "Platform查询的资源不存在"
    line = rr[0]["lines"][-1]
    mocks["existing-branches"] = {
        "branches": [
            {
                "id": "existing-unavailable",
                "case_hint": "UC-X",
                "description": "Platform查询的资源不存在",
                "operation_hint": "查询记忆库列表",
                "party_hint": "Platform",
                "scenario_type": "exception",
                "behavior_interaction_id": "sr-call",
                "source_refs": [
                    {
                        "source_id": rr[0]["source_id"],
                        "line_start": line["number"],
                        "line_end": line["number"],
                        "quote": line["text"],
                    }
                ],
            }
        ]
    }
    semantic_calls = []

    def semantic(packet):
        semantic_calls.append(packet)
        return {
            "decisions": [
                {
                    "left_id": pair["left"]["id"],
                    "right_id": pair["right"]["id"],
                    "status": "partial",
                    "reason": "离线fixture部分对应",
                }
                for pair in packet["input"]["pairs"]
            ]
        }

    mocks["ssd-semantic-compare"] = semantic
    mocks["ssd-resolve"] = {"resolved_ids": [], "concerns": [], "scenarios": []}
    # This source cannot be reliably located/classified from the fixture; an
    # available semantic runner must preserve it rather than manufacture GT.
    mocks["ssd-resolve"] = {"concerns": [], "scenarios": [], "resolved_ids": []}
    execution = Execution(
        tmp_path / "run", mocks=mocks, config={"workflow_mode": "ssd", "max_concurrency": 3}
    )
    build_pipeline(execution, rr, sr, tests)
    manifest = execution.finish()
    assert manifest["workflow"] == "ssd-case-v1" and manifest["execution_complete"]
    assert "UC-X:ssd-compare" in execution.scheduler.tasks
    forbidden = [
        key for key in execution.scheduler.tasks if key.startswith("global-") or "recommend" in key
    ]
    assert not forbidden, forbidden
    view = ssd_results.editor(tmp_path, "UC-X")
    documents = {doc["id"]: doc for doc in view["bundle"]["documents"]}
    for items, role in ((rr, "RR"), (sr, "SR"), (tests, "test")):
        for original in items:
            doc = documents[original["source_id"]]
            assert doc["role"] == role
            assert doc["content"].splitlines() == [line["text"] for line in original["lines"]]
    assert {s["id"] for s in view["bundle"]["steps"]} == {"rr-call", "sr-call"}
    assert view["bundle"]["channels"]["GT"]["pending"]
    assert not view["bundle"]["channels"]["GT"]["scenarios"]
    assert semantic_calls
    assert any(
        d["status"] == "partial" and d["origin"] == "auto" for d in view["bundle"]["decisions"]
    )


def test_function_tree_qualified_fields_keep_request_and_response_separate(tmp_path):
    tree = {
        "functions": [
            {
                "ucId": "UC-X",
                "rrLayer": {"commands": []},
                "srLayer": {
                    "commands": [
                        {
                            "apiId": "API-X",
                            "attributes": [
                                {
                                    "name": "body.name",
                                    "type": "string",
                                    "tags": ["必填"],
                                    "constraints": [{"rule": "长度 1-20"}],
                                },
                                {
                                    "name": "response.name",
                                    "type": "string",
                                    "tags": ["成功响应"],
                                    "constraints": [{"rule": "长度 1-50"}],
                                },
                                {
                                    "name": "body.quantity",
                                    "type": "integer",
                                    "tags": ["可选"],
                                    "constraints": [{"rule": "1 <= quantity <= 100"}],
                                },
                                {
                                    "name": "tagged",
                                    "type": "boolean",
                                    "tags": ["成功响应"],
                                    "constraints": [],
                                },
                            ],
                        }
                    ]
                },
            }
        ]
    }
    (tmp_path / "功能树.json").write_text(json.dumps(tree), encoding="utf-8")
    # The first declaration represents already imported API JSON: request and
    # response fields with the same leaf name must each retain their own limits.
    (tmp_path / "api_extraction.json").write_text(
        json.dumps(
            {
                "apis": [
                    {
                        "API序号": "API-X",
                        "方法": "POST",
                        "资源路径": "/x",
                        "API请求参数": "body.name（必填；类型: string）",
                        "API成功响应参数": "response.name（必填；类型: string）",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    fields = api_contracts(Sources(tmp_path), tree)["API-X"]["fields"]
    lookup = {(field["location"], field["name"]): field for field in fields}
    assert len(fields) == len(lookup) == 4
    request, response = lookup[("body", "name")], lookup[("response", "name")]
    assert any(
        rule["kind"] == "length" and "20" in str(rule["value"]) for rule in request["constraints"]
    )
    assert not any("50" in str(rule["value"]) for rule in request["constraints"])
    assert any(
        rule["kind"] == "length" and "50" in str(rule["value"]) for rule in response["constraints"]
    )
    assert not any("20" in str(rule["value"]) for rule in response["constraints"])
    assert lookup[("body", "quantity")]["required"] is False
    assert ("response", "tagged") in lookup
