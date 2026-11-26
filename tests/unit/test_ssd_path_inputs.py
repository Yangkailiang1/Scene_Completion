from copy import deepcopy
from pathlib import Path

import pytest

from scene_completion.analysis.concerns.constraint_atoms import normalize_rules
from scene_completion.application import ssd_revision_service as revisions
from scene_completion.domain import business_report
from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.current_scope import (
    COMMAND_OPERATION_PROFILE,
    case_report,
    current_registry,
)
from scene_completion.domain.ssd import concern_policy as policy
from scene_completion.domain.ssd import matching
from scene_completion.domain.ssd.construction import channel, pending
from scene_completion.domain.ssd.validation import validate
from scene_completion.review.offline import adoption
from scene_completion.workflow.ssd.compare import alignment
from scene_completion.workflow.ssd.generate.fixed import generate_g
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.resolve import classification

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"
COMMAND = "BROWSE-GET"
ROUTE = "/stores/{storeId}/products/{productId}?filter={ignored}"


@pytest.fixture
def bundle():
    result = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE)[0]
    result.update(coverage_policy=GRAIN_POLICY, gt_source_available=True)
    result["channels"] = {name: channel() for name in ("E", "G", "GT")}
    return result


def _command(bundle, command=COMMAND):
    return next(row for row in bundle["commands"] if row["id"] == command)


def _evidence(bundle, eid, condition, *, evidence=(), step=None, api=None):
    refs = [{"document_id": bundle["documents"][0]["id"], "start_line": 1, "end_line": 1}]
    source = {
        "id": eid,
        "extension_id": eid,
        "condition": condition,
        "expected": "拒绝请求",
        "source_refs": refs,
        "raw": {"evidence": evidence},
        **({"failure_step_id": step} if step else {}),
        **({"api_id": api} if api else {}),
    }
    bundle["channels"]["GT"]["pending"].append(
        pending(eid, condition, refs, original=source, needs_semantic=True)
    )


def _result(part, predicate):
    return {
        "part_id": part["id"],
        "reason": "按实际测试字段和条件比对",
        "fallback": None,
        "matches": [
            {
                "candidate_id": row["id"],
                "status": "full" if predicate(row) else "none",
                "reason": "测试证据是否验证此参数和失败类型",
            }
            for row in part["candidates"]
        ],
    }


@pytest.mark.parametrize("mode", ["one", "all", "none", "specific", "special"])
def test_path_focus_matches_before_each_scenario(bundle, mode, tmp_path):
    _command(bundle)["path"] = ROUTE
    request = bundle["steps"][0]
    sample = next(field for field in request["data"] if field["name"] == "keyword")
    field = {
        **sample,
        "id": "path-storeId",
        "name": "storeId",
        "wire_name": "storeId",
        "atoms": normalize_rules(["必填"], "storeId", sample["source_refs"])["items"],
    }
    request["data"].append(field)
    bundle["channels"]["G"] = generate_g(bundle)
    path_scenes = [row for row in bundle["channels"]["G"]["scenarios"] if row.get("path_input")]
    parent_ids = {parent for row in path_scenes for parent in row["concern_ids"]}
    path_groups = [row for row in bundle["channels"]["G"]["concerns"] if row["id"] in parent_ids]
    assert len(path_groups) == 2
    assert all(row["input_group"] for row in path_groups)
    assert len(path_scenes) == 4
    assert {row["path_input"]["parameter"] for row in path_scenes} == {"storeId", "productId"}
    assert all(row["step_id"] == "B1" for row in path_scenes)
    assert len({matching.binding(row) for row in path_scenes}) == 4
    assert (
        len(
            [
                row
                for row in bundle["channels"]["G"]["scenarios"]
                if row["key"] == policy.COMPLETENESS and row.get("field_id") == field["id"]
            ]
        )
        == 1
    )
    label = {
        "specific": "路径参数 {productId} 为空",
        "special": "路径参数含特殊字符串",
    }.get(mode, "路径参数为空／特殊字符串")
    evidence = {
        "all": "逐个验证每个路径参数为空和含特殊字符时均拒绝",
        "one": "测试步骤设置 productId 为空，接口拒绝请求",
        "specific": "测试步骤设置 productId 为空，接口拒绝请求",
        "special": "测试步骤的 productId 含非法字符，接口拒绝请求",
    }.get(mode, "未展开测试字段或处理方式")
    _evidence(bundle, "GT-path", label, evidence=[evidence], api=COMMAND)
    expected_candidates = {"specific": 1, "special": 2}.get(mode, 4)

    def semantic(task, inputs):
        assert task == alignment.ALIGN
        [part] = inputs["parts"]
        assert len(part["candidates"]) == expected_candidates
        assert len([d for d in bundle["decisions"] if d["level"] == "concern"]) == {
            "specific": 1,
            "special": 1,
        }.get(mode, 2)
        return {
            "parts": [
                _result(
                    part,
                    lambda row: (
                        mode == "all"
                        or mode != "none"
                        and row["key"]
                        == (policy.PATH_CHARACTERS if mode == "special" else policy.COMPLETENESS)
                        and row["path_input"]["parameter"] == "productId"
                    ),
                )
            ]
        }

    classification.classify(bundle, semantic)
    alignment.align(bundle, semantic)
    result = validate(bundle)
    assert not result["channels"]["GT"]["pending"]
    [gt] = result["channels"]["GT"]["scenarios"]
    assert gt["extension_id"] == "GT-path" and gt["condition"] == label
    assert len([d for d in result["decisions"] if d["level"] == "scenario"]) == expected_candidates
    compare = case_report(result)["comparison"]
    focus_rows = [
        r for r in compare["concerns"] if r["generated_id"] in {p["id"] for p in path_groups}
    ]
    assert sum(bool(r["cells"]["GT"]) for r in focus_rows) == {
        "specific": 1,
        "special": 1,
    }.get(mode, 2)
    g_ids = {p["id"] for p in path_scenes}
    scenario_rows = [r for r in compare["scenarios"] if r.get("generated_id") in g_ids]
    count = {"one": 1, "all": 4, "none": 0, "specific": 1, "special": 1}[mode]
    assert sum(bool(r["cells"]["GT"]) for r in scenario_rows) == count
    grouped, _ = business_report.classify(result, matching)
    assert len([r for r in grouped["covered"] if r["id"] in g_ids]) == count
    assert len(grouped["gt_only"]) == int(mode == "none")
    if mode == "one":
        revisions.publish(tmp_path, result)
        report = adoption.parse(adoption.export_html(tmp_path, {"scopes": ["interaction"]}))
        assert report["report"]["counts"]["covered"]["total"] == 1


def test_path_without_unique_interface_stays_pending(bundle):
    assert not any(row.get("path_input") for row in generate_g(bundle)["scenarios"])
    _command(bundle)["path"] = ROUTE
    _command(bundle, "CATALOG-SEARCH")["path"] = "/catalog/{catalogId}"
    bundle["channels"]["G"] = generate_g(bundle)
    _evidence(bundle, "GT-ambiguous", "路径参数为空或含特殊字符")
    _evidence(bundle, "GT-none", "路径参数为空", api="UNKNOWN")

    def semantic(*_):
        pytest.fail("接口未能定位时不把场景交给模型猜测")

    classification.classify(bundle, semantic)
    alignment.align(bundle, semantic)
    assert not bundle["decisions"]
    assert all("唯一确认" in row["reason"] for row in bundle["channels"]["GT"]["pending"])
    assert len(bundle["channels"]["GT"]["pending"]) == 2


def test_character_field_matches_at_request_and_database_processing_is_out_of_scope(bundle):
    request = bundle["steps"][0]
    field = next(row for row in request["data"] if row["name"] == "keyword")
    field.update(name="name", wire_name="name", atoms=[])
    field["atoms"].extend(
        normalize_rules(
            [{"rule": "符合正则 ^[A-Za-z0-9_]+$"}, {"rule": "邮箱格式"}],
            field["name"],
            field["source_refs"],
            character_rules=True,
        )["items"]
    )
    database = next(row for row in bundle["steps"] if row["id"] == "B3")
    database["receiver"] = {**database["receiver"], "technology": "database", "external": True}
    bundle["channels"]["G"] = generate_g(bundle)
    [g] = [r for r in bundle["channels"]["G"]["scenarios"] if r.get("input_character_rule")]
    assert g["key"] == policy.FIELD and g["step_id"] == "B1"
    assert any(r["key"] == "api.data.format" for r in bundle["channels"]["G"]["scenarios"])
    assert any(
        r["key"] == "service.base.availability" for r in bundle["channels"]["G"]["scenarios"]
    )
    assert not any(r["key"] == policy.DATABASE for r in bundle["channels"]["G"]["scenarios"])
    _evidence(bundle, "GT-field", "name 含非法特殊字符", step="B3")
    _evidence(bundle, "GT-db", "数据库处理特殊字符异常", step="B3")

    def semantic(task, inputs):
        if task == alignment.ALIGN:
            [part] = inputs["parts"]
            assert {r["id"] for r in part["candidates"]} == {g["id"]}
            return {"parts": [_result(part, lambda row: True)]}
        [source] = inputs["records"]
        return {
            "records": [
                {
                    "record_id": source["id"],
                    "kind": "exception",
                    "reason": "输入违反允许字符规则",
                    "parts": [
                        {
                            "condition": source["condition"],
                            "expected": source["expected"],
                            "keys": [policy.FIELD],
                        }
                    ],
                }
            ]
        }

    classification.classify(bundle, semantic)
    alignment.align(bundle, semantic)
    [gt] = bundle["channels"]["GT"]["scenarios"]
    assert gt["step_id"] == "B1" and gt["failure_step_id"] == "B3"
    assert any(r["kind"] == "out_of_scope" for r in bundle["source_classifications"]["GT"])


def test_upgrade_freezes_retired_database_judgment(tmp_path, bundle):
    database = bundle["steps"][2]
    database["receiver"] = {**database["receiver"], "technology": "database", "external": True}
    legacy = deepcopy(bundle)
    legacy["scenario_policy"] = policy.LEGACY_VERSION
    legacy["registry"] = current_registry(default_registry(), consolidated=True, path_policy=False)
    legacy["channels"]["G"] = generate_g(legacy)
    [generated] = [
        row for row in legacy["channels"]["G"]["scenarios"] if row["key"] == policy.DATABASE
    ]
    existing = {
        **generated,
        "id": "GT-database-chars",
        "concern_ids": ["GT-database-check"],
    }
    concern = next(
        row for row in legacy["channels"]["G"]["concerns"] if row["key"] == policy.DATABASE
    )
    legacy["channels"]["GT"]["concerns"].append({**concern, "id": "GT-database-check"})
    legacy["channels"]["GT"]["scenarios"].append(existing)
    old = revisions.publish(tmp_path, legacy)
    edited = deepcopy(old["bundle"])
    edited["decisions"].append(
        {
            "id": "manual-db",
            "level": "scenario",
            "pair": "GT_G",
            "left_id": existing["id"],
            "right_id": generated["id"],
            "status": "full",
            "origin": "manual",
            "reason": "人工核对数据库异常",
        }
    )
    saved = revisions.save_revision(
        tmp_path,
        bundle["case"]["id"],
        {"base_revision": old["revision"], "bundle": edited, "reason": "历史判定"},
    )
    bundle["channels"]["G"] = generate_g(bundle)
    upgraded = revisions.publish(tmp_path, bundle)
    assert not upgraded["bundle"]["decisions"]
    assert any(
        issue.get("previous_decision", {}).get("id") == "manual-db"
        for issue in upgraded["bundle"]["revision_issues"]
    )
    frozen = revisions.editor(tmp_path, bundle["case"]["id"], saved["revision"])
    assert frozen["bundle"]["decisions"][0]["id"] == "manual-db"
