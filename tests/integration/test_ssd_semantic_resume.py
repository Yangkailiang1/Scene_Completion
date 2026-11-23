"""Skipped semantic stages cannot masquerade as cached model analysis."""

import json
import shutil
from copy import deepcopy
from types import SimpleNamespace

import pytest

from scene_completion.application import ssd_revision_service as ssd_results
from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
from scene_completion.domain.ssd import validation as ssd_validation
from scene_completion.domain.ssd.construction import add_concern, add_scenario
from scene_completion.domain.ssd.construction import channel as empty_channel
from scene_completion.infrastructure import ssd_repository
from scene_completion.infrastructure.storage import read_json
from scene_completion.workflow import semantics, ssd_pipeline
from scene_completion.workflow.ssd.compare import alignment
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.resolve import classification
from scene_completion.workflow.ssd.resolve.entity_semantics import evidence_items
from scene_completion.workflow_core import Scheduler
from tests.support.paths import ROOT
from tests.support.ssd_results import bundle


def executor(root, semantic, *, mode="packets", client=None, mocks=None):
    return SimpleNamespace(
        root=root,
        scheduler=Scheduler(root, concurrency=1),
        mode=mode,
        client=client,
        mocks=mocks,
        registry_snapshot=default_registry(),
        artifact_identity={"mode": "mock" if mocks is not None else mode},
        semantic=semantic,
    )


def test_manual_independent_mount_persists_with_original_identity_and_checks_object(tmp_path):
    value = bundle()
    value["steps"][0]["entity_ids"] = ["positive-entity"]
    value["entities"][0]["attributes"] = [{"name": "quantity"}]
    value["channels"]["G"] = empty_channel()
    ssd_results.publish(tmp_path, value)
    current = ssd_results.editor(tmp_path, "case")
    edited = deepcopy(current["bundle"])
    gt = edited["channels"]["GT"]
    [pending_row] = gt["pending"]
    gt["pending"] = []
    concern = {
        **pending_row,
        "id": "manual-c",
        "step_id": "step",
        "target": "data",
        "entity_id": "positive-entity",
        "attribute": "quantity",
        "key": "api.data.range",
        "status": "active",
        "origin": "manual",
    }
    scene = {
        **concern,
        "id": pending_row["id"],
        "expected": "拒绝",
        "concern_ids": ["manual-c"],
    }
    gt["concerns"].append(concern)
    gt["scenarios"].append(scene)
    edited["review_notes"] = [
        {
            "id": "review-mount",
            "channel": "GT",
            "record_id": scene["id"],
            "decision": "mounted",
            "reason": "核对了实体属性",
        }
    ]
    submission = {"base_revision": current["revision"], "bundle": edited}
    scene["attribute"] = "unrelated"
    with pytest.raises(ValueError, match="对象与交互步骤"):
        ssd_results.save_revision(tmp_path, "case", submission)
    scene["attribute"] = "quantity"
    saved = ssd_results.save_revision(tmp_path, "case", submission)
    reloaded = ssd_results.editor(tmp_path, "case")
    assert saved["revision"] == reloaded["revision"]
    assert reloaded["bundle"]["channels"]["GT"]["scenarios"][-1] == scene
    assert reloaded["bundle"]["channels"]["GT"]["pending"] == []
    assert not reloaded["bundle"]["decisions"]
    with pytest.raises(ssd_results.RevisionConflict):
        ssd_results.save_revision(tmp_path, "case", submission)


def test_packet_cache_then_model_reruns_only_semantic_stages(tmp_path):
    initial = bundle()
    calls = {stage: 0 for stage in ("ssd-prepare", "ssd-resolve", "ssd-compare")}
    semantic_inputs = []

    def semantic(task, inputs, record):
        semantic_inputs.append((task, deepcopy(inputs)))
        if task == "ssd-resolve":
            return {"resolved_ids": [], "concerns": [], "scenarios": []}, {}
        return {
            "decisions": [
                {
                    "left_id": p["left"]["id"],
                    "right_id": p["right"]["id"],
                    "status": "partial",
                    "reason": "fixture independent comparison",
                }
                for p in inputs["pairs"]
            ]
        }, {}

    def run(client=None, mode="packets"):
        ex = executor(tmp_path / "run", semantic, client=client, mode=mode)

        def stage(name, function):
            def invoke(values, record):
                calls[name] += 1
                return function(values, record)

            return invoke

        prepare = ssd_pipeline._task(
            ex,
            "case",
            "ssd-prepare",
            [],
            stage("ssd-prepare", lambda d, r: deepcopy(initial)),
            "input-v1",
        )
        resolve = ssd_pipeline._task(
            ex,
            "case",
            "ssd-resolve",
            [prepare],
            stage("ssd-resolve", lambda d, r: ssd_pipeline._resolve(ex, d[prepare], r)),
        )
        compare = ssd_pipeline._task(
            ex,
            "case",
            "ssd-compare",
            [resolve],
            stage("ssd-compare", lambda d, r: ssd_pipeline._compare(ex, d[resolve], r)),
        )
        outcome = ex.scheduler.run()
        assert outcome["complete"]
        value = read_json(ex.root / ex.scheduler.state["tasks"][compare]["output_file"])["payload"]
        return ex, value

    offline, first = run()
    assert len(first["semantic_pending"]) == 3
    assert not first["decisions"]
    assert not semantic_inputs
    versions = {k: t.version for k, t in offline.scheduler.tasks.items()}
    before = dict(calls)
    again, _ = run()
    assert calls == before
    model, analyzed = run(object(), "external")
    assert calls == {"ssd-prepare": 1, "ssd-resolve": 2, "ssd-compare": 2}
    assert model.scheduler.tasks["case:ssd-prepare"].version == versions["case:ssd-prepare"]
    assert all(
        model.scheduler.tasks["case:" + name].version != versions["case:" + name]
        for name in ("ssd-resolve", "ssd-compare")
    )
    assert analyzed["semantic_pending"] == []
    assert len(analyzed["decisions"]) == 3
    assert {v["channel"] for task, v in semantic_inputs if task == "ssd-resolve"} == {"E", "GT"}
    for task, inputs in semantic_inputs:
        if task == "ssd-resolve":
            assert inputs["apis"] == initial["apis"] and inputs["entities"] == initial["entities"]
            assert [r["id"] for r in inputs["records"]] == [inputs["channel"] + "-pending"]
            assert not {"channels", "G", "E", "GT", "documents"}.intersection(inputs)
    before = dict(calls)
    run(object(), "external")
    assert calls == before


def test_semantic_inner_version_invalidates_compare_only(tmp_path, monkeypatch):
    ex = executor(tmp_path / "run", lambda *args: None, client=object(), mode="external")
    before = {
        stage: ssd_pipeline._semantic_cache_identity(ex, stage)
        for stage in ("ssd-prepare", "ssd-resolve", "ssd-compare")
    }
    original = semantics.code_version
    monkeypatch.setattr(
        semantics,
        "code_version",
        lambda task: (
            "updated-semantic-contract" if task == "ssd-semantic-compare" else original(task)
        ),
    )
    after = {stage: ssd_pipeline._semantic_cache_identity(ex, stage) for stage in before}
    assert after["ssd-prepare"] == before["ssd-prepare"] is None
    assert after["ssd-resolve"] == before["ssd-resolve"]
    assert after["ssd-compare"] != before["ssd-compare"]


def test_new_prepare_reuses_previous_machine_only_for_unchanged_pairs(tmp_path):
    calls = []

    def semantic(task, inputs, record):
        calls.extend((inputs["pair"], p["left"]["id"], p["right"]["id"]) for p in inputs["pairs"])
        return {
            "decisions": [
                {
                    "left_id": p["left"]["id"],
                    "right_id": p["right"]["id"],
                    "status": "partial",
                    "reason": "independent comparison",
                }
                for p in inputs["pairs"]
            ]
        }, {}

    ex = executor(tmp_path / "run", semantic, client=object(), mode="external")
    original = ssd_pipeline._compare(ex, bundle(), {})
    assert len(calls) == 3
    calls.clear()
    fresh = bundle()
    fresh["channels"]["G"]["scenarios"][0]["condition"] = "调用者身份凭证已撤销"
    added = deepcopy(fresh["channels"]["G"]["scenarios"][0])
    added.update(id="G-new", condition="调用者未提供凭证")
    fresh["channels"]["G"]["scenarios"].append(added)
    ssd_results.publish(tmp_path, fresh)
    assert not ssd_results.editor(tmp_path, "case", "original")["bundle"]["decisions"]
    assert ssd_repository.state(tmp_path, "case")["previous_baseline"] == original
    compared = ssd_pipeline._compare(ex, fresh, {})
    assert set(calls) == {
        ("G_E", "G-s", "E-s"),
        ("G_E", "G-new", "E-s"),
        ("GT_G", "GT-s", "G-s"),
        ("GT_G", "GT-s", "G-new"),
    }
    assert len(compared["decisions"]) == 5
    reused = next(d for d in compared["decisions"] if d["pair"] == "GT_E")
    assert reused == next(d for d in original["decisions"] if d["pair"] == "GT_E")
    calls.clear()
    ssd_results.publish(tmp_path, fresh)
    ssd_pipeline._compare(ex, fresh, {})
    assert calls == []


def test_previous_machine_decisions_require_same_semantic_identity(tmp_path):
    ex = executor(tmp_path / "run", lambda *args: None, client=object(), mode="external")
    previous = bundle()
    previous["semantic_comparison_identity"] = {"version": "old"}
    previous["decisions"] = [
        {
            "id": "old",
            "level": "scenario",
            "pair": "G_E",
            "left_id": "G-s",
            "right_id": "E-s",
            "status": "full",
            "reason": "old",
            "origin": "auto",
        }
    ]
    ssd_results.publish(tmp_path, previous)
    ssd_results.publish(tmp_path, bundle())
    current = ssd_pipeline._reuse_machine_decisions(ex, bundle(), {"version": "new"})
    assert current["decisions"] == []


def test_source_reference_repairs_reuse_decisions_but_other_fields_remain_strict(tmp_path):
    calls = []

    def semantic(task, inputs, record):
        calls.append(inputs)
        return {
            "decisions": [
                {
                    "left_id": p["left"]["id"],
                    "right_id": p["right"]["id"],
                    "status": "partial",
                    "reason": "independent comparison",
                }
                for p in inputs["pairs"]
            ]
        }, {}

    initial = bundle()
    initial["documents"] = [
        {"id": "doc", "name": "source", "role": "RR", "content": "旧出处\n精确出处"}
    ]
    for channel in initial["channels"].values():
        channel["scenarios"][0]["source_refs"] = [
            {
                "document_id": "doc",
                "start_line": 1,
                "end_line": 1,
                "quote": "旧出处",
                "kind": "origin",
            }
        ]
    ex = executor(tmp_path / "run", semantic, client=object(), mode="external")
    original = ssd_pipeline._compare(ex, initial, {})
    assert len(calls) == 3
    fresh = deepcopy(initial)
    for channel in fresh["channels"].values():
        channel["scenarios"][0]["source_refs"] = [
            {
                "document_id": "doc",
                "start_line": 2,
                "end_line": 2,
                "quote": "精确出处",
                "kind": "origin",
            }
        ]
    ssd_results.publish(tmp_path, fresh)
    calls.clear()
    result = ssd_pipeline._compare(ex, fresh, {})
    assert calls == []
    assert result["decisions"] == original["decisions"]
    assert result["channels"]["G"]["scenarios"][0]["source_refs"][0]["quote"] == "精确出处"
    for field, value in {
        "condition": "different failure",
        "expected": "different outcome",
        "step_id": "other",
        "target": "receiver",
        "field_id": "field",
        "entity_id": "entity",
        "key": "human.authorization",
        "status": "pending",
        "concern_ids": ["other-concern"],
    }.items():
        changed = deepcopy(fresh)
        changed["channels"]["G"]["scenarios"][0][field] = value
        reused = ssd_pipeline._reuse_machine_decisions(
            ex, changed, result["semantic_comparison_identity"]
        )
        assert {d["pair"] for d in reused["decisions"]} == {"GT_E"}, field


def test_resolve_uses_mock_capability_and_own_channel_only(tmp_path):
    inputs_seen = []

    def semantic(task, inputs, record):
        inputs_seen.append(inputs)
        return {"resolved_ids": [], "concerns": [], "scenarios": []}, {}

    ex = executor(tmp_path / "run", semantic, mocks={"ssd-resolve": {}})
    value = ssd_pipeline._resolve(ex, bundle(), {})
    assert [item["channel"] for item in inputs_seen] == ["E", "GT"]
    assert len(value["channels"]["E"]["pending"]) == 1
    assert all(item["apis"] and item["entities"] for item in inputs_seen)


def test_pending_pairs_recomputed_after_manual_decisions(tmp_path):
    value = bundle()
    ex = executor(tmp_path / "run", lambda *args: None)
    first = ssd_pipeline._compare(ex, value, {})
    assert len(first["semantic_pending"]) == 3
    pair = first["semantic_pending"][0]
    first["decisions"].append(
        {
            "id": "manual",
            "level": "scenario",
            "pair": pair["pair"],
            "left_id": pair["left_id"],
            "right_id": pair["right_id"],
            "status": "none",
            "reason": "人工确认",
            "origin": "manual",
        }
    )
    second = ssd_pipeline._compare(ex, first, {})
    assert len(second["semantic_pending"]) == 2
    assert pair not in second["semantic_pending"]
    ssd_validation.validate(second)


def test_human_revision_rechecks_only_changed_pairs_and_preserves_machine_baseline(tmp_path):
    calls = []

    def semantic(task, inputs, record):
        calls.extend(inputs["pairs"])
        return {
            "decisions": [
                {
                    "left_id": p["left"]["id"],
                    "right_id": p["right"]["id"],
                    "status": "partial",
                    "reason": "checked exact current content",
                }
                for p in inputs["pairs"]
            ]
        }, {}

    ex = executor(tmp_path / "run", semantic, client=object(), mode="external")
    machine = ssd_pipeline._compare(ex, bundle(), {})
    assert len(calls) == 3
    current = ssd_results.editor(tmp_path, "case")
    edited = deepcopy(current["bundle"])
    edited["channels"]["E"]["scenarios"][0]["condition"] = "人工修正后的条件"
    saved = ssd_results.save_revision(
        tmp_path, "case", {"base_revision": current["revision"], "bundle": edited}
    )
    assert len(saved["bundle"]["semantic_pending"]) == 2
    identity_before = ssd_pipeline._review_identity(ex, "case")
    calls.clear()
    rerun = ssd_pipeline._compare(ex, bundle(), {})
    assert len(calls) == 2
    assert all(
        any(
            r["id"] == "E-s" and r["condition"] == "人工修正后的条件"
            for r in (p["left"], p["right"])
        )
        for p in calls
    )
    effective = ssd_results.editor(tmp_path, "case")
    original = ssd_results.editor(tmp_path, "case", "original")
    assert effective["bundle"]["semantic_pending"] == []
    assert effective["revision"] == saved["revision"] + 1
    assert "自动复核人工修订" in effective["history"][-1]["reason"]
    assert original["bundle"] == machine == rerun
    assert original["bundle"]["channels"]["E"]["scenarios"][0]["condition"] == "无有效凭证"
    assert ssd_pipeline._review_identity(ex, "case") == identity_before
    calls.clear()
    ssd_pipeline._compare(ex, bundle(), {})
    assert not calls
    assert ssd_results.editor(tmp_path, "case")["revision"] == effective["revision"]


def test_concurrent_revision_wins_and_comparison_remains_retryable(tmp_path):
    import pytest

    from scene_completion.workflow_core import TaskBlocked

    conflicted = False

    def semantic(task, inputs, record):
        nonlocal conflicted
        if (
            any("人工" in p["left"]["condition"] + p["right"]["condition"] for p in inputs["pairs"])
            and not conflicted
        ):
            conflicted = True
            snapshot = ssd_results.editor(tmp_path, "case")
            edited = deepcopy(snapshot["bundle"])
            edited["review_notes"] = ["并发编辑必须保留"]
            ssd_results.save_revision(
                tmp_path, "case", {"base_revision": snapshot["revision"], "bundle": edited}
            )
        return {
            "decisions": [
                {
                    "left_id": p["left"]["id"],
                    "right_id": p["right"]["id"],
                    "status": "full",
                    "reason": "fixture",
                }
                for p in inputs["pairs"]
            ]
        }, {}

    ex = executor(tmp_path / "run", semantic, client=object(), mode="external")
    machine = ssd_pipeline._compare(ex, bundle(), {})
    snapshot = ssd_results.editor(tmp_path, "case")
    edited = deepcopy(snapshot["bundle"])
    edited["channels"]["E"]["scenarios"][0]["condition"] = "人工条件"
    ssd_results.save_revision(
        tmp_path, "case", {"base_revision": snapshot["revision"], "bundle": edited}
    )
    with pytest.raises(TaskBlocked):
        ssd_pipeline._compare(ex, bundle(), {})
    current = ssd_results.editor(tmp_path, "case")
    assert current["bundle"]["review_notes"] == ["并发编辑必须保留"]
    assert len(current["bundle"]["semantic_pending"]) == 2
    assert ssd_results.editor(tmp_path, "case", "original")["bundle"] == machine
    ssd_pipeline._compare(ex, bundle(), {})
    assert not ssd_results.editor(tmp_path, "case")["bundle"]["semantic_pending"]


@pytest.mark.parametrize("has_original", [True, False], ids=["original", "structured-only"])
def test_sc075_quotations_reach_comparison_after_prepare_upgrade(
    tmp_path, monkeypatch, has_original
):
    source = tmp_path / "input"
    shutil.copytree(ROOT / "datasets/mini-mall/examples/browse-product", source)
    required = "缺少必填请求头x-wisecloud-service-id"
    enum = "memoryType=INVALID不在枚举值[PROFILE,SEMANTIC]内"
    page = "page=abc类型非法（非整数）"
    size = "pageSize=xyz类型非法（非整数）"
    expected = "返回 HTTP 400"
    excerpt = "、".join((required, enum, page, size)) + "，" + expected
    foreign = "其他扩展中的 pageSize=900"
    original = source / "test_browse.md"
    if has_original:
        original.write_text("# 样例\n" + excerpt + "\n", encoding="utf8")
    else:
        original.unlink()

    def extension(ext_id, text, result, evidence):
        return {
            "id": ext_id,
            "condition": text,
            "expected_result": result,
            "evidence": evidence,
            "failure_step_id": "B2",
            "api_id": "BROWSE-GET",
        }

    recovered_path = source / "recovered_usecases.json"
    recovered = read_json(recovered_path)
    recovered[0]["extensions"] = [
        {
            **extension(
                "EXT-SC075", "memoryType=INVALID、page/pageSize传字符串", "拒绝请求", ["EV-310"]
            ),
            "scene_id": "SC-075",
        },
        extension("EXT-OTHER", "合法输入", "成功", [foreign]),
        extension("EXT-BAD", "非法输入", "拒绝", ["pageSize=990"]),
    ]
    recovered[0]["evidence_locations"] = [
        {"id": "EV-310", "location": "L2", "source_file": original.name, "quote": excerpt},
    ]
    recovered_path.write_text(json.dumps(recovered, ensure_ascii=False, indent=2), encoding="utf8")

    tree_path = source / "功能树.json"
    tree = read_json(tree_path)
    commands = tree["functions"][0]["srLayer"]["commands"]
    command = next(row for row in commands if row["apiId"] == "BROWSE-GET")
    command["attributes"].extend(
        {"name": name, "type": "string", "tags": [], "source": {}, "constraints": []}
        for name in ("memoryType", "x-wisecloud-service-id")
    )
    tree_path.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf8")

    completeness, bounds, data_type = "api.data.completeness", "api.data.range", "api.data.type"
    prepare_calls = []

    def prepare(_, __):
        prepare_calls.append(semantics.code_version("ssd-prepare"))
        value = build_cases(source, profile=COMMAND_OPERATION_PROFILE, generate=False)[0]
        value["coverage_policy"] = GRAIN_POLICY
        value["channels"]["E"] = empty_channel()
        step_id = value["command_bindings"]["BROWSE-GET"]["primary_step_id"]
        step = next(row for row in value["steps"] if row["id"] == step_id)
        fields = {field["name"]: field for field in step["data"]}
        generated = value["channels"]["G"]
        for name, key, condition in (
            ("x-wisecloud-service-id", completeness, required),
            ("memoryType", bounds, enum),
            ("page", data_type, page),
            ("pageSize", data_type, size),
        ):
            concern = add_concern(generated, value, "G", step, key, "data", field=fields[name])
            add_scenario(generated, concern, condition, expected, [])
        return value

    def semantic(task, inputs):
        if task == classification.CLASSIFY:

            def part(condition, key, expected_text=""):
                return {"condition": condition, "expected": expected_text, "keys": [key]}

            def fragments(index, *quotes):
                return {
                    **part("", data_type),
                    "condition_fragments": [
                        {"field": "evidence", "index": index, "quote": quote} for quote in quotes
                    ],
                }

            rows = []
            for record in inputs["records"]:
                if record["name"] == "EXT-SC075":
                    index = record["evidence"].index(excerpt)
                    parts = [
                        part(required, completeness, expected),
                        part(enum, bounds),
                        fragments(index, page, size),
                        part(enum.replace("INVALID", "invalid"), bounds),
                        fragments(index + len(record["evidence"]), page),
                    ]
                elif record["name"] == "EXT-BAD":
                    parts = [part(foreign, data_type), part("pageSize=991", data_type)]
                else:
                    parts = []
                rows.append(
                    {
                        "record_id": record["id"],
                        "kind": "exception" if parts else "normal",
                        "reason": "样例分类",
                        "parts": parts,
                    }
                )
            return {"records": rows}
        assert task == alignment.ALIGN
        return {
            "parts": [
                {
                    "part_id": row["id"],
                    "reason": "核对同一请求字段与失败条件",
                    "fallback": None,
                    "matches": [
                        {
                            "candidate_id": candidate["id"],
                            "status": "full"
                            if candidate["condition"] in row["condition"]
                            else "none",
                            "reason": "按失败条件逐字核对",
                        }
                        for candidate in row["candidates"]
                    ],
                }
                for row in inputs["parts"]
            ]
        }

    root = tmp_path / "run"
    cid = "UC-BROWSE-01"
    if not has_original:
        old_version = "v5-sr-input-field-identity"
        current_version = semantics.code_version
        assert current_version("ssd-prepare") != old_version

        def legacy_prepare(values, record):
            value = prepare(values, record)
            pending = next(
                row
                for row in value["channels"]["GT"]["pending"]
                if row["original"]["extension_id"] == "EXT-SC075"
            )
            # Before the upgrade only the extension-level reference carried the
            # original locator. The packet exposed the EV identifier alone.
            pending["original"]["source_refs"] = [
                {
                    **pending["original"]["source_refs"][0],
                    "origin": {"match": "pending"},
                    "declared_source": recovered[0]["evidence_locations"][0],
                }
            ]
            assert [item["text"] for item in evidence_items(pending["original"])] == ["EV-310"]
            return value

        def legacy_version(task):
            return old_version if task == "ssd-prepare" else current_version(task)

        with monkeypatch.context() as patch:
            patch.setattr(semantics, "code_version", legacy_version)
            previous = executor(root, lambda *_: None)
            old_prepare = ssd_pipeline._task(
                previous, cid, "ssd-prepare", [], legacy_prepare, "sc075"
            )
            assert previous.scheduler.run()["complete"]
            stale_version = previous.scheduler.tasks[old_prepare].version
            checkpoint = previous.scheduler.state["tasks"][old_prepare]["output_file"]
        prior = ssd_results.publish(tmp_path, read_json(root / checkpoint)["payload"])
        edited = deepcopy(prior["bundle"])
        edited["channels"]["G"]["scenarios"][0]["analysis"] = "人工审核说明"
        reviewed = ssd_results.save_revision(
            tmp_path, cid, {"base_revision": prior["revision"], "bundle": edited}
        )

    ex = executor(root, lambda *_: None)
    prepare_key = ssd_pipeline._task(ex, cid, "ssd-prepare", [], prepare, "sc075")

    def resolve(dependencies, _):
        value = deepcopy(dependencies[prepare_key])
        classification.classify(value, semantic)
        return value

    resolve_key = ssd_pipeline._task(ex, cid, "ssd-resolve", [prepare_key], resolve)

    def compare(dependencies, _):
        value = deepcopy(dependencies[resolve_key])
        alignment.align(value, semantic)
        return ssd_results.publish(tmp_path, value)["bundle"]

    ssd_pipeline._task(ex, cid, "ssd-compare", [resolve_key], compare)
    assert ex.scheduler.run()["complete"], ex.scheduler.state["tasks"]
    if not has_original:
        assert ex.scheduler.tasks[prepare_key].version != stale_version
        assert prepare_calls == [old_version, semantics.code_version("ssd-prepare")]

    view = ssd_results.editor(tmp_path, cid, compact=True)
    result = view["bundle"]
    if not has_original:
        saved = ssd_results.editor(tmp_path, cid, revision=reviewed["revision"])["bundle"]
        assert not saved["channels"]["GT"]["scenarios"]
        assert saved["channels"]["G"]["scenarios"][0]["analysis"] == "人工审核说明"
        assert result["channels"]["G"]["scenarios"][0]["analysis"] == "人工审核说明"
    audits = {row["source_id"]: row for row in result["source_classifications"]["GT"]}
    assert len(audits["EXT-SC075"]["pending_parts"]) == 2
    assert audits["EXT-BAD"]["kind"] == "pending"
    assert len(audits["EXT-BAD"]["pending_parts"]) == 2
    conditions = {row["condition"]: row for row in result["channels"]["GT"]["scenarios"]}
    assert set(conditions) == {required, enum, page + "；" + size}
    assert conditions[required]["expected"] == expected
    assert conditions[enum]["expected"] == ""
    assert len(result["channels"]["GT"]["pending"]) == 2
    matched = [
        row for row in result["decisions"] if row["level"] == "scenario" and row["status"] == "full"
    ]
    assert len(matched) == 4
    assert [quote["quote"] for quote in conditions[page + "；" + size]["verified_excerpts"]] == [
        page,
        size,
    ]
    visible_gt = {
        row["id"]
        for entry in view["comparison"]["scenarios"]
        if entry.get("generated_id")
        for row in entry["cells"]["GT"]
    }
    assert visible_gt == {row["id"] for row in conditions.values()}
    documents = {doc["id"]: doc for doc in result["documents"]}
    for row in conditions.values():
        refs = [ref for quote in row["verified_excerpts"] for ref in quote.get("source_refs", [])]
        assert refs and all(ref in row["source_refs"] for ref in refs)
        if has_original:
            assert any(
                documents[ref["document_id"]]["name"] == original.name and ref["start_line"] == 2
                for ref in refs
            )
        else:
            assert any(
                ref.get("json_pointer", "").endswith("/evidence_locations/0/quote")
                and ref["origin"]["match"] == "pending"
                for ref in refs
            )
