"""Minimal steps, source-channel routing and review version regressions."""

from copy import deepcopy

import pytest

from scene_completion.analysis.atomic_steps import apply_plan, compact, validate_plan
from scene_completion.analysis.exception_scopes import (
    canonical_dependencies,
    global_records,
    interaction_branches,
    inverse_dependencies,
    validate_scope,
)
from scene_completion.analysis.ssd_drawing import ordered_messages
from scene_completion.infrastructure.storage import fingerprint, write_json
from tests.test_workflow import R, exchange


def candidate():
    req = exchange()
    req.update(id="call", layer="SR", step_kind="interaction")
    req["sender"]["name"], req["receiver"]["name"] = "Admin", "Database"
    ret = deepcopy(req)
    ret.update(id="mixed", direction="return", parent_id="call", sequence=2)
    ret["sender"], ret["receiver"] = deepcopy(req["receiver"]), deepcopy(req["sender"])
    ret["operation"]["name"] = "Database检查名称唯一性，并向Admin返回结果"
    return {"interactions": [req, ret], "rr_sr_links": [], "pending": []}


def plan():
    common = {"layer": "SR", "validates": [], "source_refs": R}
    return {
        "steps": [
            {
                **common,
                "key": "call",
                "origin_ids": ["call"],
                "kind": "request",
                "sender": "Admin",
                "receiver": "Database",
                "operation": candidate()["interactions"][0]["operation"]["name"],
                "request_ref": None,
            },
            {
                **common,
                "key": "check",
                "origin_ids": ["mixed"],
                "kind": "action",
                "sender": "Database",
                "receiver": "Database",
                "operation": "检查名称唯一性",
                "request_ref": None,
            },
            {
                **common,
                "key": "return",
                "origin_ids": ["mixed"],
                "kind": "return",
                "sender": "Database",
                "receiver": "Admin",
                "operation": "返回结果",
                "request_ref": "call",
            },
        ],
        "pending": [],
    }


def test_atomic_plan_preserves_order_origin_data_and_return_identity():
    raw, p = candidate(), plan()
    validate_plan(p, {"candidate": compact(raw)})
    out = apply_plan(raw, p, "UC")
    rows = out["interactions"]
    assert [i["step_kind"] for i in rows] == ["interaction", "action", "interaction"]
    assert rows[1]["data"]["sequence"] == []
    assert rows[2]["parent_id"] == rows[0]["id"]
    assert rows[0]["id"] == "call"
    assert len(out["normalization"]["origins"][1]["step_ids"]) == 2
    assert [i["id"] for i in ordered_messages(out)[0]] == [i["id"] for i in rows]
    assert raw["interactions"][1]["operation"]["name"].endswith("返回结果")


@pytest.mark.parametrize("change", ["combined", "return_before_call", "forward_check", "omit"])
def test_atomic_plan_rejects_bundled_or_unordered_or_lost_steps(change):
    p = plan()
    if change == "combined":
        p["steps"][1]["operation"] = "检查名称后向Admin返回结果"
    if change == "return_before_call":
        p["steps"] = list(reversed(p["steps"]))
    if change == "forward_check":
        p["steps"][1]["validates"] = ["return"]
    if change == "omit":
        p["steps"] = p["steps"][:1]
    with pytest.raises(ValueError):
        validate_plan(p, {"candidate": compact(candidate())})


def unit(scope, trigger="同键不同内容", **kwargs):
    return {
        "source_id": "original",
        "trigger": trigger,
        "scope": scope,
        "global_kind": "idempotency" if scope == "global" else None,
        "entity_ids": ["Product"],
        "related_cases": ["UC"],
        "reason": "来源明确",
        **kwargs,
    }


def test_scope_split_keeps_shared_branch_but_does_not_leak_global_to_local():
    inp = {
        "source-records": [{"id": "original"}],
        "entity-index": {"entities": [{"id": "Product"}]},
        "case-catalogue": [{"id": "UC"}],
    }
    scopes = {"units": [unit("global"), unit("interaction", "缺少名称")]}
    validate_scope(scopes, inp)
    raw = {"branches": [{"id": "original", "description": "混合异常", "source_refs": R}]}
    local = interaction_branches(raw, scopes)["branches"]
    assert len(local) == 1 and local[0]["description"] == "缺少名称"
    assert local[0]["original_id"] == "original"
    glob = global_records(scopes, raw["branches"])
    assert len(glob) == 1 and glob[0]["description"] == "同键不同内容"
    with pytest.raises(ValueError, match="every exception"):
        validate_scope({"units": []}, inp)


def test_gt_dependency_identity_does_not_require_generation_answer():
    rec = {
        "id": "t",
        "source_refs": R,
        "scope_unit": unit("global", "未创建实例查询列表", global_kind="dependency_consistency"),
    }
    inv = inverse_dependencies([rec])[0]
    positive = {
        **inv,
        "id": "raw-id",
        "from_case_id": "RR-UC",
        "to_case_id": "SR-UC",
        "condition": "正常依赖要求",
    }
    out = canonical_dependencies(
        {"dependencies": [positive]}, [{"id": "UC", "rr_ids": ["RR-UC"], "sr_ids": ["SR-UC"]}]
    )
    assert inv["id"] == out["dependencies"][0]["id"]
    assert inv["condition"] == "未创建实例查询列表"
    assert out["dependencies"][0]["condition"] == "正常依赖要求"


def test_scope_review_dry_run_version_conflict_and_audit(tmp_path):
    from scene_completion.review.scope_reviews import reviewed, save, state, view

    root = tmp_path / "run"
    inputs = {"input": "independent"}
    output = {"units": [unit("interaction")]}
    write_json(
        root / "task.json", {"metadata": {"input_hash": fingerprint(inputs)}, "payload": output}
    )
    write_json(
        root / "workflow_tasks.json",
        {
            "tasks": {
                "UC:existing-scope": {
                    "stage": "exception-scope",
                    "status": "passed",
                    "output_file": "task.json",
                    "case": "UC",
                },
                "business-entities": {
                    "stage": "business-entities",
                    "status": "passed",
                    "output_file": "entities.json",
                },
                "use-case-align": {
                    "stage": "use-case-align",
                    "status": "passed",
                    "output_file": "cases.json",
                },
            }
        },
    )
    write_json(
        root / "entities.json", {"payload": {"entities": [{"id": "Product", "name": "商品"}]}}
    )
    write_json(root / "cases.json", {"payload": {"groups": [{"id": "UC"}]}})
    row = view(tmp_path)["records"][0]
    body = {
        "task_key": row["task_key"],
        "expected_version": row["expected_version"],
        "units": [unit("global")],
        "reviewer": "业务甲",
    }
    assert not save(tmp_path, {**body, "dry_run": True})["saved"]
    assert state(tmp_path)["revision"] == 0
    result = save(tmp_path, body)
    assert result["recompute_started"] is False
    assert reviewed(tmp_path, row["task_key"], inputs)["units"][0]["scope"] == "global"
    assert reviewed(tmp_path, row["task_key"], {"changed": True}) is None
    with pytest.raises(ValueError, match="版本"):
        save(tmp_path, body)
    assert len(state(tmp_path)["history"]) == 1


def test_global_reporting_is_not_blocked_by_test_alignment_and_gt_only_anchor_is_independent(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from scene_completion.analysis import test_alignment
    from scene_completion.workflow.global_pipeline import _schedule_global_analysis

    group = {
        "id": "UC",
        "rr_ids": ["RR-UC"],
        "sr_ids": ["SR-UC"],
        "status": "confirmed",
        "reason": "same",
        "source_refs": R,
    }

    class Pipeline:
        root = tmp_path
        session_id = "independent"
        pattern_settings = {}
        recommendation_history = []
        partitions = []

        def __init__(self):
            self.nodes = {}
            self.scheduler = SimpleNamespace(tasks={}, state={"tasks": {}})

        def add(self, key, stage, deps=(), **kwargs):
            node = SimpleNamespace(stage=stage, deps=deps, **kwargs)
            self.nodes[key] = node
            self.scheduler.tasks[key] = node

        def seed(self, key, value):
            path = key.replace(":", "-") + ".json"
            write_json(self.root / path, {"protocol": "scene-workflow-v5", "payload": value})
            self.scheduler.state["tasks"][key] = {"output_file": path}

    ex = Pipeline()
    values = {
        "use-case-align": {"groups": [group]},
        "business-entities": {"entities": [{"id": "Product", "name": "商品", "source_refs": R}]},
        "rr-use-cases": {"cases": []},
        "sr-use-cases": {"cases": []},
        "business-dependencies": {"dependencies": [], "pending": []},
        "business-crud-project": {"rows": []},
        "UC:existing-scope": {"units": []},
        "UC:existing-branches-source": {"branches": []},
        "test-inventory": {},
        "test-case-align": {},
    }
    for key, value in values.items():
        ex.seed(key, value)
    _schedule_global_analysis(ex, [], [], [], [{"test": "isolated"}])
    ex.partitions[0][1]()
    assert "UC:test-scope" not in ex.partitions[1][0]
    ex.partitions[1][1]()
    assert "global-scenario-compare" in ex.nodes
    assert "global-recommend" in ex.nodes
    assert all("test-scope" not in p for p in ex.nodes["global-scenario-compare"].deps)
    # Test independently exposes a dependency absent from both G and E.
    gt = unit("global", "缺少前置实体", global_kind="dependency_consistency")
    gt["source_id"] = "GT"
    ex.seed("UC:test-scope", {"units": [gt]})
    monkeypatch.setattr(test_alignment, "scoped_tests", lambda *a: ([], {}))
    monkeypatch.setattr(
        test_alignment,
        "as_records",
        lambda *a: [
            {
                "id": "GT",
                "scenario_type": "exception",
                "description": "缺少前置实体",
                "source_refs": R,
            }
        ],
    )
    ex.partitions[2][1]()
    g = [n for n in ex.nodes.values() if n.stage == "global-concerns"]
    assert len(g) == 1
    assert g[0].transform({}) == {"matches": [], "pending": []}
    assert "test-documents" not in g[0].static
    assert g[0].static["business-dependencies"]["dependencies"] == []
    truth = [n for n in ex.nodes.values() if n.stage == "global-test-concerns"][0]
    assert "UC:test-scope" in truth.deps
    assert "test-documents" in truth.static


def test_renaming_mixed_return_does_not_omit_its_actual_local_execution():
    raw = candidate()
    raw["interactions"][1]["operation"]["name"] = (
        "Database执行原子操作：检查唯一性，并向Admin返回结果"
    )
    p = plan()
    p["steps"] = [s for s in p["steps"] if s["kind"] != "action"]
    with pytest.raises(ValueError, match="explicit local execution"):
        validate_plan(p, {"candidate": compact(raw)})


def test_latest_native_mini_steps_pass_literal_audit_but_mixed_inputs_fall_back():
    import json
    from pathlib import Path

    from scene_completion.analysis.atomic_steps import literal_plan
    from scene_completion.inputs.behavior_imports import compile_product

    root = Path(__file__).resolve().parents[1] / "datasets/mini-mall/输入文件/行为模型"
    for p in root.glob("*/*/SysOperation.json"):
        value = json.loads(p.read_text())
        product = compile_product(value, "test-" + p.parent.name, p.name)
        raw = product["fused_template"]
        assert len(raw["interactions"]) == 11
        normalized = literal_plan(compact(raw))
        assert normalized is not None
        assert len(normalized["steps"]) == 11
        assert any(s["kind"] == "action" and s["layer"] == "RR" for s in normalized["steps"])
    assert literal_plan(compact(candidate())) is None


def test_business_check_uses_unique_positive_local_owner_not_upstream_or_return():
    from scene_completion.analysis.failure_units import local_rule_owner

    raw = candidate()["interactions"]
    local = deepcopy(raw[1])
    local.update(id="db-check", step_kind="action", direction="request")
    local["receiver"] = deepcopy(local["sender"])
    m = {"concern_key": "database.uniqueness", "field": None}
    inputs = {
        "normal-rules": {
            "rules": [
                {
                    "interaction_id": "db-check",
                    "owner_service": "Database",
                    "concern_key": "database.uniqueness",
                    "fields": ["name"],
                    "source_refs": R,
                }
            ]
        }
    }
    assert local_rule_owner(m, raw + [local], inputs)["id"] == "db-check"
    another = deepcopy(local)
    another["id"] = "another-check"
    inputs["normal-rules"]["rules"].append(
        {**inputs["normal-rules"]["rules"][0], "interaction_id": "another-check"}
    )
    assert local_rule_owner(m, raw + [local, another], inputs) is None
    assert local_rule_owner({"concern_key": "api.data.type"}, raw + [local], inputs) is None


def test_local_security_check_keeps_caller_boundary_without_crossing_layers():
    from scene_completion.analysis.failure_units import local_caller_request

    request = exchange()
    request.update(id="inbound", step_kind="interaction", layer="RR")
    local = deepcopy(request)
    local.update(id="check", step_kind="action")
    local["sender"] = deepcopy(local["receiver"])
    match = {"interaction_id": "check", "concern_key": "service_relation.authorization"}
    assert local_caller_request(match, [request, local])["id"] == "inbound"
    sr = deepcopy(request)
    sr.update(id="SR-call", layer="SR")
    assert local_caller_request(match, [request, local, sr])["id"] == "inbound"
    duplicate = deepcopy(request)
    duplicate["id"] = "another-inbound"
    assert local_caller_request(match, [request, local, duplicate]) is None


def test_failed_service_call_does_not_include_its_local_action_or_return():
    from scene_completion.analysis.failure_units import failed_requests

    call, response = candidate()["interactions"]
    local = deepcopy(call)
    local.update(id="db-local-check", step_kind="action")
    local["sender"] = deepcopy(local["receiver"])
    # An older self step may omit step_kind; its equal parties still exclude it.
    old_local = deepcopy(local)
    old_local.update(id="legacy-local-check")
    old_local.pop("step_kind")
    assert set(failed_requests("Database连接不可达", [call, local, old_local, response])) == {
        "call"
    }
    duplicate = deepcopy(call)
    duplicate["id"] = "another-real-call"
    assert len(failed_requests("Database不可用", [call, duplicate, local])) == 2


def test_explicit_api_response_fields_remain_on_the_response_of_that_call():
    from scene_completion.analysis.concern_alignment import response_targets

    raw = candidate()["interactions"]
    unrelated = deepcopy(raw[1])
    unrelated.update(id="RR-response", parent_id="another-public-api")
    assert response_targets(["call"], raw + [unrelated]) == ["mixed"]
    assert response_targets(["another-public-api"], raw + [unrelated]) == ["RR-response"]


def test_scene_bindings_follow_own_identified_E_location_and_mark_ambiguity():
    from scene_completion.analysis.exception_scopes import bindings_at_recognitions

    inputs = {
        "bindings": {
            "bindings": [
                {"branch_id": "b", "interaction_id": "call", "status": "confirmed", "basis": "raw"}
            ]
        },
        "identified-concerns": {
            "matches": [
                {"status": "applicable", "interaction_id": "mixed", "source_branch_ids": ["b"]}
            ]
        },
        "fused-ssd": candidate(),
    }
    assert bindings_at_recognitions(inputs)["bindings"][0]["interaction_id"] == "mixed"
    inputs["identified-concerns"]["matches"].append(
        {"status": "applicable", "interaction_id": "call", "source_branch_ids": ["b"]}
    )
    row = bindings_at_recognitions(inputs)["bindings"][0]
    assert row["status"] == "pending" and row["interaction_id"] is None
    assert inputs["bindings"]["bindings"][0]["interaction_id"] == "call"


def test_raw_observation_replay_recovers_observations_and_rejects_lossy_legacy_cache(tmp_path):
    from scene_completion.workflow.semantic_reuse import replay
    from tests.test_two_level_matching import memory_inputs, raw

    original = {"matches": [raw("api.data.type", "page", data_location="query")], "pending": []}
    write_json(
        tmp_path / "semantic_raw_responses/original.json",
        {"task": "test-concerns", "payload": original},
    )
    cached = {
        "payload": {"matches": [], "pending": [{"reason": "四要素位置或具体对象不唯一"}]},
        "proof": {
            "execution_model_evidence": {
                "raw_payload_file": "semantic_raw_responses/original.json",
                "raw_payload_hash": fingerprint(original),
            }
        },
    }
    result = replay(tmp_path, cached, "test-concerns", memory_inputs())
    assert len(result["matches"]) == 1
    assert result["matches"][0]["object"] == "page"
    with pytest.raises(ValueError, match="lossy"):
        replay(tmp_path, {"payload": cached["payload"]}, "test-concerns", memory_inputs())
    write_json(
        tmp_path / "semantic_raw_responses/original.json",
        {"task": "test-concerns", "payload": {"matches": []}},
    )
    with pytest.raises(ValueError, match="identity changed"):
        replay(tmp_path, cached, "test-concerns", memory_inputs())
