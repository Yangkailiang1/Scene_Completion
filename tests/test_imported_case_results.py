import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scene_completion.analysis.imported_case_results import VERSION
from scene_completion.analysis.interaction_enrichment import (
    contract_fields,
    parameters_for,
    requirement_sources,
)
from scene_completion.analysis.standalone_case import finalize, input_phase
from scene_completion.api.application import create_app
from scene_completion.cli.main import main
from scene_completion.inputs.colleague_formats import parameter

MINI = Path(__file__).resolve().parents[1] / "datasets/mini-mall/输入文件"


def test_contract_fields_use_actual_call_and_success_variant():
    def field(name, location, dtype):
        return parameter(name, location, [], dtype=dtype)

    def message(ident, direction, name, *, layer="SR", parent=None, step_kind="interaction"):
        return {
            "id": ident,
            "case_id": "case",
            "direction": direction,
            "layer": layer,
            "step_kind": step_kind,
            "parent_id": parent,
            "api_id": "SR::A",
            "operation": {"name": name},
            "receiver": {"name": "Service"},
            "data": {"sequence": []},
        }

    request = message("sr", "request", "GET /things")
    returns = [
        message("ok", "return", "HTTP 200", parent="sr"),
        message("accepted", "return", "HTTP 202", parent="sr"),
        message("bad", "return", "HTTP 400", parent="sr"),
        message("unknown", "return", "返回", parent="sr"),
        message("unbound", "return", "HTTP 200", parent="elsewhere"),
    ]
    rr = message("rr", "request", "GET /things", layer="RR")
    action = message("local", "request", "GET /things", step_kind="action")
    repeated = message("another-call", "request", "GET /things")
    request["data"]["sequence"] = [field("id", "body", "integer")]
    api = {
        "id": "SR::A",
        "name": "A",
        "source_layer": "SR",
        "address": "/things",
        "method": "GET",
        "bound_interaction_ids": [row["id"] for row in [request, *returns, rr, action]],
        "parameters": [
            field("id", "query", "string"),
            field("id", "body", None),
            field("legacy", "response", "string"),
        ],
        "responses": [
            {
                "kind": "success",
                "status_code": "200",
                "parameters": [field("items[].id", "response", "integer")],
            },
            {
                "kind": "success",
                "status_code": "202",
                "parameters": [field("job", "response", "string")],
            },
            {
                "kind": "error",
                "status_code": "400",
                "parameters": [field("error", "response", "string")],
            },
        ],
    }
    inputs = {
        "sr-ssd": {"interactions": [request, *returns, action, repeated]},
        "rr-ssd": {"interactions": [rr]},
        "api-parameters": {"apis": [api]},
    }
    assert {
        (p["location"], p["name"], p["data_type"]) for p in parameters_for(request, inputs)
    } == {
        ("body", "id", "integer"),
        ("query", "id", "string"),
    }
    assert [p["name"] for p in parameters_for(returns[0], inputs)] == ["items[].id"]
    assert [p["name"] for p in requirement_sources(returns[1], inputs)] == ["job"]
    assert api["responses"][2]["parameters"][0]["name"] == "error"
    assert contract_fields(returns[3], inputs)[1]
    for i in (rr, action, repeated, *returns[2:]):
        assert parameters_for(i, inputs) == []


@pytest.fixture(scope="module")
def mini_bundle():
    if not MINI.is_dir():
        pytest.skip("开发样例不随Windows程序包分发")
    model, existing, truth = (
        input_phase(MINI, "创建商品", role) for role in ("model", "existing", "test")
    )
    request = next(i for i in model["interactions"] if i["operation"]["name"].startswith("S1."))
    database = next(i for i in model["interactions"] if i["operation"]["name"].startswith("S4."))
    header = next(p for p in request["data"]["sequence"] if p["name"] == "x-service-id")
    branch = next(r for r in existing["records"] if "EX_DUPLICATE_NAME" in r["id"])
    test = next(r for r in truth["records"] if r["id"].endswith("-DUPLICATE_NAME"))

    def records(prefix, iid, key, target, location, obj, trigger, refs, pattern):
        concern = {
            "interaction_id": iid["id"],
            "target": target,
            "object": obj,
            "concern_key": key,
            "basis": trigger,
            "concrete_rule": trigger,
            "source_refs": refs,
        }
        if location:
            concern["data_location"] = location
        scenario = {
            "id": prefix,
            "case_id": iid["case_id"],
            "interaction_id": iid["id"],
            "layer": iid["layer"],
            "object": obj,
            "operation": iid["operation"]["name"],
            "cause": trigger,
            "conditions": [trigger],
            "concern_key": key,
            "field": obj if location else None,
            "rule_id": None,
            "source_status": "explicit",
            "derivation": trigger,
            "source_refs": refs,
            "steps": {"normal_context": [], "trigger": trigger, "documented_follow_up": []},
            "pattern_id": pattern,
            "confidence": {"score": 1, "basis": "明示规则", "calibrated_probability": False},
        }
        if location:
            scenario["data_location"] = location
        return concern, scenario

    duplicates = []
    for name, refs in (
        ("g-name", database["source_refs"]),
        ("e-name", branch["source_refs"]),
        ("gt-name", test["source_refs"]),
    ):
        duplicates.append(
            records(
                name,
                database,
                "database.uniqueness",
                "receiver",
                None,
                database["receiver"]["name"],
                "当前商家已有同名商品",
                refs,
                "rule.database.uniqueness",
            )
        )
    header_concern, header_scene = records(
        "g-header",
        request,
        "api.data.completeness",
        "data",
        "header",
        header["name"],
        "x-service-id 未提供",
        header["source_refs"],
        "data.required",
    )
    bundle = {
        key: model[key]
        for key in (
            "case",
            "ssd",
            "api_map",
            "api_parameters",
            "registry",
            "recommendation_settings",
        )
    }
    bundle.update(
        version=VERSION,
        scope="all",
        history=[],
        pending=model["pending"] + truth["pending"],
        sources=model["sources"] + existing["sources"] + truth["sources"],
        channels={
            key: {
                "status": "ready",
                "concerns": [m],
                "scenarios": [s],
                "source_refs": m["source_refs"],
                "pending": [],
            }
            for key, (m, s) in zip(("G", "E", "GT"), duplicates, strict=True)
        },
        decisions={
            name: [
                {
                    "left_id": left,
                    "right_id": right,
                    "status": "full",
                    "reason": "同一S4同商家名称重复",
                }
            ]
            for name, left, right in (
                ("G_E", "g-name", "e-name"),
                ("GT_G", "gt-name", "g-name"),
                ("GT_E", "gt-name", "e-name"),
            )
        },
    )
    bundle["channels"]["G"]["concerns"].append(header_concern)
    bundle["channels"]["G"]["scenarios"].append(header_scene)
    return bundle


def test_import_cli_reuses_case_views_without_workflow(tmp_path, mini_bundle, capsys):
    artifact = tmp_path / "out" / "case-analysis.json"
    summary = finalize(mini_bundle, artifact.parent)
    assert (artifact.parent / "case-analysis.md").is_file()
    assert json.loads(artifact.read_text())["recommendation_ids"] == ["g-header"]
    with TestClient(create_app(tmp_path / "projects")) as client:
        created = client.post(
            "/api/projects",
            json={
                "name": "mini",
                "sources": {
                    "RR": [{"name": "需求.md", "content": "# 需求"}],
                    "SR": [{"name": "设计.md", "content": "# 设计"}],
                },
            },
        )
        assert created.status_code == 200, created.text
        project_id = created.json()["id"]
        base = "/api/projects/" + project_id
        project = tmp_path / "projects" / project_id

        class CliClient:
            def call(self, path, body, method):
                response = client.request(method, "/api/" + path, json=body)
                assert response.status_code == 200, response.text
                return response.json()

        args = ["import-case-result", "--project", project_id, "--file", str(artifact)]
        main([*args, "--dry-run"], CliClient())
        assert json.loads(capsys.readouterr().out)["dry_run"]
        assert not (project / "imported-case-results").exists()
        main(args, CliClient())
        imported = json.loads(capsys.readouterr().out)
        main(args, CliClient())
        assert imported == json.loads(capsys.readouterr().out)
        version = imported["id"]
        assert version == summary["id"]
        assert not (project / "run" / "workflow_tasks.json").exists()
        index = client.get(base + "/results").json()
        assert not index["cases"]
        assert index["case_result_imports"][0]["id"] == version
        query = {"import_id": version}
        selected = client.get(base + "/results", params=query)
        assert selected.status_code == 200
        assert selected.json()["cases"][0]["id"] == mini_bundle["case"]["id"]
        cid = mini_bundle["case"]["id"]
        response = client.get(f"{base}/results/{cid}", params=query)
        assert response.status_code == 200, response.text
        detail = response.json()
        assert len(detail["interactions"]) == 11
        assert any(
            row["status"] == "triple"
            for step in detail["interactions"]
            for row in step["alignment_rows"]
        )
        assert detail["recommendations"]["Q"][0]["id"] == "g-header"
        response = client.get(f"{base}/results/{cid}/metrics", params=query)
        assert response.status_code == 200, response.text
        metrics = response.json()["metrics"]
        assert metrics["generation_validity"]["value"] == 50
        assert metrics["missing_exception_miss_rate"]["status"] == "不适用"
        assert metrics["recommendation_false_positive"]["value"] == 100
        assert summary["metrics"]["generation_validity"]["value"] == 50
        assert client.get(f"{base}/results/{cid}/scenarios/GT/gt-name", params=query).json()[
            "source_refs"
        ]
        invalid = deepcopy(mini_bundle)
        invalid["decisions"]["GT_G"][0]["right_id"] = "g-header"
        bad = client.post(base + "/case-result-imports", json={"bundle": invalid})
        assert bad.status_code == 400 and "同一交互" in bad.text
        invalid = json.loads(artifact.read_text())
        invalid["metrics"]["generation_validity"]["value"] = 99
        bad = client.post(base + "/case-result-imports", json={"bundle": invalid})
        assert bad.status_code == 400 and "计算的结果不一致" in bad.text
        incomplete = deepcopy(mini_bundle)
        incomplete["channels"]["GT"].update(
            status="missing", source_refs=[], concerns=[], scenarios=[]
        )
        incomplete["decisions"].update(GT_G=[], GT_E=[])
        saved = client.post(base + "/case-result-imports", json={"bundle": incomplete}).json()
        assert saved["id"] != version
        fresh = client.get(
            f"{base}/results/{cid}/metrics", params={"import_id": saved["id"]}
        ).json()
        assert fresh["cases"][0]["status"] == "未评测" and not fresh["metrics"]
        assert client.get(f"{base}/results/{cid}/metrics", params=query).json()["complete"]
