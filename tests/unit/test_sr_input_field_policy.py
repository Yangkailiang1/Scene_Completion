import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from scene_completion.application import ssd_revision_service
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
from scene_completion.domain.ssd.construction import channel, ident, pending
from scene_completion.domain.ssd.interface_fields import INPUT_FIELD_POLICY, candidates
from scene_completion.workflow.ssd.compare import alignment
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.input_conversion.core_input import convert, validate_core
from scene_completion.workflow.ssd.resolve import classification
from tests.support.ssd_results import sample

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"


def load(path):
    return json.loads(path.read_text(encoding="utf8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf8")


def test_sr_fields_without_location_round_trip_and_merge_per_command(tmp_path):
    source = tmp_path / "input"
    shutil.copytree(BROWSE, source)
    tree_file = source / "功能树.json"
    tree = load(tree_file)
    commands = tree["functions"][0]["srLayer"]["commands"]
    by_command = {row["apiId"]: row for row in commands}
    attributes = by_command["BROWSE-GET"]["attributes"]
    page = next(row for row in attributes if row["name"] == "pageSize")
    attributes.append({**deepcopy(page), "location": "response", "direction": "return"})
    # The same field name in a different SR command is a different obligation.
    by_command["CATALOG-SEARCH"]["attributes"].append(deepcopy(page))
    for command in commands:
        for row in command["attributes"]:
            row.setdefault("source", {}).update(section="方法/路径")
    write(tree_file, tree)

    bundle = build_cases(source, profile=COMMAND_OPERATION_PROFILE)[0]
    assert bundle["interface_field_policy"] == INPUT_FIELD_POLICY
    fields = [
        field for step in bundle["steps"] for field in step["data"] if field["name"] == "pageSize"
    ]
    assert {f["command_id"] for f in fields} == {"BROWSE-GET", "CATALOG-SEARCH"}
    assert len(set(f["id"] for f in fields)) == len(fields) == 2
    assert all("location" not in f and "direction" not in f for f in fields)
    assert all(len(f["atoms"]) == len(fields[0]["atoms"]) for f in fields)
    assert len(fields[0]["source_refs"]) >= 2
    assert not any("唯一定位 SR 字段" in p["reason"] for p in bundle["pending"] if p.get("reason"))

    evidence = {"parameter": {"name": "pageSize", "location": "header", "direction": "response"}}
    assert len(candidates(bundle, None, evidence)) == 2
    assert [f["command_id"] for _, f in candidates(bundle, "B2", evidence)] == ["BROWSE-GET"]
    assert [
        f["command_id"]
        for _, f in candidates(bundle, None, {**evidence, "api_id": "CATALOG-SEARCH"})
    ] == ["CATALOG-SEARCH"]

    output = tmp_path / "core"
    assert convert(source, output, profile=COMMAND_OPERATION_PROFILE)["output"]
    main_path = next(output.glob("cases/*/main-success.json"))
    main = load(main_path)
    assert main["interface_field_policy"] == INPUT_FIELD_POLICY
    assert all(
        set(r) == {"step_id", "field_id", "command_id", "name"} for r in main["data_obligations"]
    )
    source_map = load(main_path.with_name("source-map.json"))
    assert source_map["interface_fields"][fields[0]["id"]]["constraints"]
    assert validate_core(output)["valid"]
    existing_path = main_path.with_name("existing-exceptions.json")
    existing = load(existing_path)
    existing["exceptions"].append(
        {
            "id": "e-confirmed-page-size",
            "step_id": "B2",
            "target": "receiver",
            "concern_key": "api.data.range",
            "parameter": {"command_id": "BROWSE-GET", "name": "pageSize"},
            "condition": "pageSize > 100",
            "expected": "拒绝",
            "status": "active",
            "anchor": None,
        }
    )
    write(existing_path, existing)
    assert validate_core(output)["valid"]
    existing["exceptions"][-1]["parameter"]["command_id"] = "CATALOG-SEARCH"
    write(existing_path, existing)
    assert not validate_core(output)["valid"]
    existing["exceptions"].pop()
    write(existing_path, existing)

    # A legacy export could omit a field when its transport location was unknown.
    main.pop("interface_field_policy")
    main["data_obligations"] = main["data_obligations"][:-1]
    for row in main["data_obligations"]:
        row["location"] = "query"
        row["field_id"] = ident(
            "command-field", main["case"]["id"], row["command_id"], "query", row["name"]
        )
    write(main_path, main)
    assert validate_core(output)["valid"]


def test_response_failure_is_audited_but_input_rejection_is_still_matched():
    bundle = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE)[0]
    bundle["channels"].update(E=channel(), GT=channel())

    for record_id, condition in (
        ("output", "响应字段 pageSize 格式错误"),
        ("input", "请求参数 pageSize > 100"),
    ):
        bundle["channels"]["GT"]["pending"].append(
            pending(
                record_id,
                condition,
                needs_semantic=True,
                original={
                    "id": record_id,
                    "condition": condition,
                    "expected": "返回错误",
                    "failure_step_id": "B2",
                    "source_refs": [],
                    "parameter": {
                        "name": "pageSize",
                        "location": "response",
                        "direction": "response",
                    },
                },
            )
        )

    def semantic(task, packet):
        if task == classification.CLASSIFY:
            assert [r["id"] for r in packet["records"]] == ["input"]
            return {
                "records": [
                    {
                        "record_id": "input",
                        "kind": "exception",
                        "reason": "输入超过上界",
                        "parts": [
                            {
                                "condition": packet["records"][0]["condition"],
                                "expected": "返回错误",
                                "keys": ["api.data.range"],
                            }
                        ],
                    }
                ]
            }
        assert task == alignment.ALIGN
        assert all("location" not in field for field in packet["interface_fields"])
        return {
            "parts": [
                {
                    "part_id": part["id"],
                    "reason": "分页上界",
                    "fallback": None,
                    "matches": [
                        {"candidate_id": candidate["id"], "reason": "同一阈值", "status": "full"}
                        for candidate in part["candidates"]
                    ],
                }
                for part in packet["parts"]
            ]
        }

    classification.classify(bundle, semantic)
    alignment.align(bundle, semantic)
    audit = {row["record_id"]: row for row in bundle["source_classifications"]["GT"]}
    assert audit["output"]["kind"] == "out_of_scope"
    assert audit["input"]["kind"] == "exception"
    assert bundle["channels"]["GT"]["scenarios"][0]["failure_step_id"] == "B2"
    assert not bundle["channels"]["GT"]["pending"]


@pytest.mark.parametrize("ambiguous", [False, True])
def test_field_policy_upgrade_preserves_review_decisions_or_reports_conflicts(tmp_path, ambiguous):
    original = sample()
    step = original["steps"][0]
    legacy = {"id": "old-field", "command_id": "api", "name": "name", "location": "body"}
    step["data"] = [legacy]
    if ambiguous:
        step["data"].append({**legacy, "id": "other-field", "location": "query"})
    for data in original["channels"].values():
        for row in data["concerns"] + data["scenarios"]:
            row.update(field_id="old-field", target="data", key="api.data.format")
    first = ssd_revision_service.publish(tmp_path, original)
    edited = deepcopy(original)
    edited["channels"]["E"]["scenarios"][0]["analysis"] = "人工修订"
    judgment = {
        "id": "review",
        "level": "scenario",
        "pair": "G_E",
        "left_id": "G-s",
        "right_id": "E-s",
        "status": "full",
        "reason": "人工确认",
        "origin": "manual",
    }
    edited["decisions"] = [judgment]
    ssd_revision_service.save_revision(
        tmp_path, "case", {"base_revision": first["revision"], "bundle": edited}
    )

    next_version = deepcopy(original)
    next_version["interface_field_policy"] = INPUT_FIELD_POLICY
    next_version["steps"][0]["data"] = [{"id": "new-field", "command_id": "api", "name": "name"}]
    for data in next_version["channels"].values():
        for row in data["concerns"] + data["scenarios"]:
            row.update(id="new-" + row["id"], field_id="new-field")
            if "concern_ids" in row:
                row["concern_ids"] = ["new-" + ident for ident in row["concern_ids"]]
    current = ssd_revision_service.publish(tmp_path, next_version)["bundle"]
    assert ssd_revision_service.editor(tmp_path, "case", 2)["bundle"]["decisions"] == [judgment]
    if ambiguous:
        assert not current["decisions"]
        assert any(
            issue.get("previous_decision") == judgment for issue in current["revision_issues"]
        )
    else:
        assert current["channels"]["E"]["scenarios"][0]["analysis"] == "人工修订"
        assert current["decisions"] == [{**judgment, "left_id": "new-G-s", "right_id": "new-E-s"}]
        assert not current["revision_issues"]
