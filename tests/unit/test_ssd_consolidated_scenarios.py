from copy import deepcopy
from pathlib import Path

import pytest

from scene_completion.analysis.concerns.constraint_atoms import normalize_rules
from scene_completion.application import ssd_revision_service as revisions
from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.current_scope import case_report
from scene_completion.domain.ssd import concern_policy as policy
from scene_completion.domain.ssd.construction import channel, pending
from scene_completion.review.offline.business_report_export import export_html
from scene_completion.workflow.ssd.compare.alignment import align
from scene_completion.workflow.ssd.generate import fixed, scenarios
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.resolve import classification, entity_semantics, operations

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"


@pytest.fixture
def bundle():
    result = build_cases(BROWSE, profile="command-interaction-v3")[0]
    result["coverage_policy"] = GRAIN_POLICY
    result["gt_source_available"] = True
    result["channels"] = {name: channel() for name in ("E", "G", "GT")}
    commands = {command["id"]: command for command in result["commands"]}
    commands["BROWSE-GET"]["authentication"] = "required"
    return result


def _rows(bundle, channel, key):
    return [row for row in bundle["channels"][channel]["scenarios"] if row["key"] == key]


def _append_call(bundle, step_id, party, crud):
    template = bundle["steps"][0]
    row = {
        **deepcopy(template),
        "id": step_id,
        "order": len(bundle["steps"]) + 1,
        "direction": "request",
        "sender": template["receiver"],
        "receiver": party,
        "api_id": None,
        "data": [],
        "entity_ids": [],
        "operation": {"name": crud, "kinds": [crud], "kinds_source": "declared"},
    }
    bundle["steps"].append(row)
    return row


def _submit_evidence(bundle, side, condition, key, step, expected="按约定拒绝"):
    identity = f"{side}-{step}-{len(bundle['channels'][side]['pending'])}"
    source = {
        "id": identity,
        "failure_step_id": step,
        "condition": condition,
        "expected": expected,
        "concern_key": key,
        "source_refs": [
            {"document_id": bundle["documents"][0]["id"], "start_line": 1, "end_line": 1}
        ],
    }
    bundle["channels"][side]["pending"].append(
        pending(identity, condition, original=source, needs_semantic=True)
    )


def _run_evidence(bundle):
    keys = {
        row["id"]: row["original"]["concern_key"]
        for side in ("E", "GT")
        for row in bundle["channels"][side]["pending"]
    }

    def semantic(task, inputs):
        if task == "ssd-evidence-classify":
            return {
                "records": [
                    {
                        "record_id": row["id"],
                        "kind": "exception",
                        "reason": "按本条证据识别",
                        "parts": [
                            {
                                "condition": row["condition"],
                                "expected": row["expected"],
                                "keys": [keys[row["id"]]],
                            }
                        ],
                    }
                    for row in inputs["records"]
                ]
            }
        return {
            "parts": [
                {
                    "part_id": part["id"],
                    "reason": "依据本条失败及候选对象",
                    "fallback": None,
                    "matches": [
                        {
                            "candidate_id": candidate["id"],
                            "status": "full",
                            "reason": "同一对象的失败",
                        }
                        for candidate in part["candidates"]
                    ],
                }
                for part in inputs["parts"]
            ]
        }

    classification.classify(bundle, semantic)
    align(bundle, semantic)


def test_auth_and_database_evidence_fold_into_one_row_each(tmp_path, bundle):
    database = {
        "id": "db",
        "name": "CatalogDB",
        "type": "service",
        "external": True,
        "technology": "database",
    }
    _append_call(bundle, "DB-1", database, "read")
    _append_call(bundle, "DB-2", database, "read")
    operations.resolve(bundle, None)
    bundle["channels"]["G"] = fixed.generate_g(bundle)
    [auth] = _rows(bundle, "G", policy.AUTH)
    [db] = _rows(bundle, "G", policy.DATABASE)
    assert set(auth["failure_variants"]) == set(policy.AUTH_DETAILS)
    assert set(db["failure_variants"]) == set(policy.DB_DETAILS)
    assert db["related_call_step_ids"] == ["DB-1", "DB-2"]
    _submit_evidence(bundle, "E", "Token 已过期", policy.AUTH, "B1")
    for condition in (
        "Authorization 缺失",
        "凭证为空",
        "凭证格式错误",
        "Token 无效",
        "Token 已过期",
    ):
        _submit_evidence(bundle, "GT", condition, policy.AUTH, "B1")
    for condition in (
        "SQL 内容被错误处理",
        "HTML 内容被错误处理",
        "宽字符处理异常",
        "emoji 处理异常",
    ):
        _submit_evidence(bundle, "GT", condition, policy.DATABASE, "DB-2")
    _submit_evidence(bundle, "GT", "SQL 字段被入口拒绝", policy.DATABASE, "B1")
    _run_evidence(bundle)
    assert {r["failure_subtype"] for r in _rows(bundle, "GT", policy.AUTH)} == set(
        policy.AUTH_DETAILS
    )
    assert {r["failure_subtype"] for r in _rows(bundle, "GT", policy.DATABASE)} == set(
        policy.DB_DETAILS
    )
    assert all(r["failure_step_id"] == "DB-2" for r in _rows(bundle, "GT", policy.DATABASE))
    assert len(bundle["channels"]["GT"]["pending"]) == 1
    report = case_report(bundle)
    rows = {
        r["generated_id"]: r for r in report["comparison"]["scenarios"] if r.get("generated_id")
    }
    assert len(rows[auth["id"]]["cells"]["GT"]) == 5
    assert len(rows[db["id"]]["cells"]["GT"]) == 4
    decisions = [
        row for row in bundle["decisions"] if row["pair"] == "GT_G" and row["level"] == "scenario"
    ]
    assert {row["right_id"] for row in decisions} == {auth["id"], db["id"]}
    assert all(row["source_refs"] for row in rows[db["id"]]["cells"]["GT"])

    project = tmp_path / "project"
    revisions.publish(project, bundle)
    html = export_html(project)
    assert html.count(auth["id"]) > 0 and "失败类型明细" in html and "Token 已过期" in html


def test_optional_auth_and_one_concurrency_at_each_actual_operation(bundle):
    next(row for row in bundle["commands"] if row["id"] == "BROWSE-GET")["authentication"] = (
        "optional"
    )
    service = {"id": "outside", "name": "外部服务", "type": "service", "external": True}
    for i, crud in enumerate(("read", "create", "update", "delete", "delete"), 1):
        _append_call(bundle, f"S{i}", service, crud)
    operations.resolve(bundle, None)
    bundle["channels"]["G"] = fixed.generate_g(bundle)
    [auth] = _rows(bundle, "G", policy.AUTH)
    assert "missing_credential" not in auth["failure_variants"]
    for crud, step in (("create", "S2"), ("update", "S3"), ("delete", "S4")):
        key = f"service.crud.{crud}.concurrency_consistency"
        [scene] = _rows(bundle, "G", key)
        assert (scene["variant_id"], scene["step_id"]) == ("concurrent_conflict", step)
        batch = next(
            inputs
            for inputs in scenarios.batches(bundle)
            if scene["id"] in {r["id"] for r in inputs["templates"]}
        )
        invalid = {
            "analyses": [{"scenario_id": r["id"], "analysis": "说明"} for r in batch["templates"]],
            "supplements": [
                {
                    "concern_id": scene["concern_ids"][0],
                    "condition": "关联资源被并发删除",
                    "expected": "按约定",
                    "analysis": "说明",
                }
            ],
        }
        with pytest.raises(ValueError, match="只填写固定场景"):
            scenarios.validate_result(invalid, batch)
    assert not _rows(bundle, "G", "service.query_retrieval.idempotency")


def test_input_body_size_and_scope_rules(bundle):
    request = bundle["steps"][0]
    command = next(row for row in bundle["commands"] if row["id"] == "BROWSE-GET")
    command["quote"] = "请求体不能为空"
    field = next(row for row in request["data"] if row["name"] == "keyword")
    field["atoms"].extend(
        normalize_rules(
            [{"rule": "文件大小不超过 2.5 MiB"}, {"rule": "非空"}],
            field["name"],
            [],
            entity_only=True,
        )["items"]
    )
    bundle["channels"]["G"] = fixed.generate_g(bundle)
    [body] = [
        row
        for row in _rows(bundle, "G", policy.COMPLETENESS)
        if row.get("variant_id") == "empty_body"
    ]
    assert body["command_id"] == "BROWSE-GET"
    assert any(
        row["condition"] == "keyword缺失或为空" for row in _rows(bundle, "G", policy.COMPLETENESS)
    )
    assert any(
        row["condition"] == "keyword大小 > 2.5 MiB" for row in _rows(bundle, "G", "api.data.size")
    )
    assert set(entity_semantics.definitions(bundle)) == policy.ACTIVE_CHECKS
    _submit_evidence(bundle, "GT", "请求体为空", policy.COMPLETENESS, "B1")
    _submit_evidence(bundle, "GT", "返回版本不符", policy.FIELD, "B6")
    _run_evidence(bundle)
    [gt] = _rows(bundle, "GT", policy.COMPLETENESS)
    assert any(
        r["pair"] == "GT_G" and r["left_id"] == gt["id"] and r["right_id"] == body["id"]
        for r in bundle["decisions"]
    )
    assert any(row["kind"] == "out_of_scope" for row in bundle["source_classifications"]["GT"])


def test_upgrade_keeps_old_auth_revision_and_holds_ambiguous_edits(tmp_path, bundle):
    project = tmp_path / "project"
    legacy = deepcopy(bundle)
    del legacy["scenario_policy"]
    legacy["channels"]["G"] = fixed.generate_g(legacy)
    before = revisions.publish(project, legacy)
    manually_edited = deepcopy(before["bundle"])
    old_rows = _rows(manually_edited, "G", policy.AUTH)
    assert len(old_rows) == 5
    old_rows[0]["analysis"] = "仅适用这一种认证失败的人工说明"
    revisions.save_revision(
        project,
        bundle["case"]["id"],
        {"base_revision": before["revision"], "bundle": manually_edited, "reason": "人工校对"},
    )
    bundle["channels"]["G"] = fixed.generate_g(bundle)
    after = revisions.publish(project, bundle)
    assert len(_rows(after["bundle"], "G", policy.AUTH)) == 1
    assert any(
        issue.get("previous_record", {}).get("analysis") == old_rows[0]["analysis"]
        for issue in after["bundle"]["revision_issues"]
    )
    frozen = revisions.editor(project, bundle["case"]["id"], before["revision"])
    assert len(_rows(frozen["bundle"], "G", policy.AUTH)) == 5


def test_explicit_field_uniqueness_and_creation_target_share_one_scenario(bundle):
    from scene_completion.domain.ssd.validation import validate
    from scene_completion.workflow.ssd.resolve import path_roles

    step = bundle["steps"][0]
    command = next(row for row in bundle["commands"] if row["id"] == "BROWSE-GET")
    command.update(path="/categories/{categoryId}", method="POST")
    step["operation"].update(
        http_method="POST", http_path=command["path"], kinds_source="manual", kinds=["create"]
    )
    operations.resolve(bundle, None)
    path_roles.resolve(
        bundle,
        lambda _task, _inputs: {
            "parameters": [
                {
                    "command_id": command["id"],
                    "name": "categoryId",
                    "role": "target",
                    "reason": "这一条操作创建分类",
                }
            ]
        },
    )
    field = next(row for row in step["data"] if row["name"] == "categoryId")
    field["atoms"].extend(
        [
            {
                "concern_key": policy.FIELD,
                "operation": "semantic",
                "failure_condition": "categoryId 已存在",
                "applicable_operations": ["create"],
                "source_refs": [],
            },
            {
                "concern_key": policy.FIELD,
                "operation": "semantic",
                "failure_condition": "同一租户中分类重名",
                "applicable_operations": ["create"],
                "source_refs": [],
            },
        ]
    )
    entity_semantics.infer(bundle, None)
    rows = [
        row
        for row in validate(bundle)["channels"]["G"]["scenarios"]
        if row.get("resource_failure") == "already_exists"
        and row.get("command_id") == command["id"]
    ]
    [target] = rows
    assert target["key"] == policy.FIELD and target["status"] == "active"
    assert any(row["condition"] == "同一租户中分类重名" for row in _rows(bundle, "G", policy.FIELD))
    _submit_evidence(
        bundle, "GT", "categoryId 已存在", "service.crud.create.resource_existence", "B1"
    )
    _run_evidence(bundle)
    [truth] = _rows(bundle, "GT", policy.FIELD)
    assert any(
        d["pair"] == "GT_G" and d["left_id"] == truth["id"] and d["right_id"] == target["id"]
        for d in bundle["decisions"]
    )
