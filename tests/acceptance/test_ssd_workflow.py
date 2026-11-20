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
from scene_completion.review.offline.adoption import parse as _parse
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
        for stage in ("ssd-prepare", "ssd-resolve", "ssd-generate", "ssd-compare")
    } | {f"UC-{n:03d}:shared-services-merge" for n in range(1, 6)}
    assert set(first.scheduler.tasks) == expected
    assert all(tasks[key]["status"] == "passed" for key in expected)
    assert not list((root / "run/packets").glob("*.json"))
    index = ssd_results.index(root)
    assert len(index["cases"]) == 5
    from scene_completion.application.shared_service_service import index as project_index

    assert manifest["metrics"] == project_index(root)["metrics"]["overall"]["concern"]
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
        "UC-002:ssd-generate",
        "UC-002:ssd-compare",
        "UC-002:shared-services-merge",
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
        assert feedback["format"] == "business-adoption-v3"
        # Deterministic ready rows may be exported; unresolved model templates may not.
        for item in feedback["items"]:
            pending = set(item["bundle"].get("scenario_generation", {}).get("pending_ids", []))
            assert all(row["cells"]["G"][0]["id"] not in pending for row in item["rows"])
        assert feedback["excluded"]["unfinished"] > 0
        preview = client.post(base + "/ssd-review/preview", json={"content": exported.text})
        assert preview.status_code == 200
        assert all(r["status"] == "unchanged" for r in preview.json()["cases"])


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
    mocks["ssd-generate"] = lambda packet: {
        "analyses": [
            {"scenario_id": template["id"], "analysis": "离线固定模板分析"}
            for template in packet["input"]["templates"]
        ],
        "supplements": [],
    }
    mocks["project-structure"] = {"dependencies": [], "services": [], "pending": []}

    def project_identify(packet):
        anchors = packet["input"]["anchors"]
        if not anchors:
            return {
                "observations": [],
                "pending": [
                    {"source_record_id": row["id"], "reason": "离线fixture无项目锚点"}
                    for row in packet["input"]["records"]
                ],
                "excluded": [],
            }
        key = packet["input"]["allowed_keys"][0]
        return {
            "observations": [
                {
                    "source_record_id": row["id"],
                    "anchor_id": anchors[0]["id"],
                    "key": key,
                    "condition": row["condition"],
                    "expected": row.get("expected", ""),
                }
                for row in packet["input"]["records"]
            ],
            "pending": [],
            "excluded": [],
        }

    mocks["project-scope-identify"] = project_identify
    mocks["project-scope-generate"] = lambda packet: {
        "analyses": [
            {"scenario_id": template["id"], "analysis": "离线项目场景分析"}
            for template in packet["input"]["templates"]
        ],
        "supplements": [],
    }
    mocks["project-scope-compare"] = lambda packet: {
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


def test_code_retry_keeps_previous_case_scope_with_another_case_cached(tmp_path, monkeypatch):
    from scene_completion.application.node_recovery_service import rerun
    from scene_completion.infrastructure.storage import write_json

    service, rid, root = imported_project(tmp_path)
    first, _ = execute(root, ["UC-001", "UC-002"])
    prepare = "UC-001:ssd-prepare"
    other = "UC-002:ssd-prepare"
    before = deepcopy(first.scheduler.state["tasks"][other])
    original = read_json(root / "run" / first.scheduler.state["tasks"][prepare]["output_file"])
    write_json(
        root / "job.json",
        {"status": "waiting", "started_at": 1, "run_options": {"case_ids": ["UC-001"]}},
    )

    def resume(project_id, options):
        assert project_id == rid
        ex, manifest = execute(root, options["case_ids"])
        assert all(task.case == "UC-001" for task in ex.scheduler.tasks.values())
        assert ex.scheduler.state["tasks"][other] == before
        result = read_json(root / "run" / ex.scheduler.state["tasks"][prepare]["output_file"])
        assert result["payload"]["core_snapshot"] == original["payload"]["core_snapshot"]
        return manifest

    monkeypatch.setattr(service, "_start", resume)
    assert rerun(service, rid, {"task_key": prepare})["execution_complete"]
    service.pool.shutdown()
