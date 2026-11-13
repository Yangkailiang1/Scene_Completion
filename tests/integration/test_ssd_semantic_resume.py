"""Skipped semantic stages cannot masquerade as cached model analysis."""

from copy import deepcopy
from types import SimpleNamespace

from scene_completion.application import ssd_revision_service as ssd_results
from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.ssd import validation as ssd_validation
from scene_completion.infrastructure import ssd_repository
from scene_completion.infrastructure.storage import read_json
from scene_completion.workflow import ssd_pipeline
from scene_completion.workflow_core import Scheduler


def bundle():
    value = {
        "version": "ssd-case-v1",
        "case": {"id": "case", "name": "case"},
        "steps": [
            {
                "id": "step",
                "order": 1,
                "kind": "interaction",
                "direction": "request",
                "layer": "SR",
                "sender": {"id": "a", "name": "a", "type": "human"},
                "receiver": {"id": "b", "name": "b", "type": "service"},
                "operation": {"name": "call", "kinds": []},
                "data": [],
                "api_id": None,
                "entity_ids": [],
                "source_refs": [],
            }
        ],
        "channels": {},
        "documents": [],
        "decisions": [],
        "pending": [],
        "apis": [{"id": "positive-api", "fields": []}],
        "entities": [{"id": "positive-entity", "attributes": []}],
    }
    for channel, condition in (("G", "身份认证不满足"), ("E", "无有效凭证"), ("GT", "凭证已过期")):
        concern = {
            "id": channel + "-c",
            "step_id": "step",
            "target": "sender",
            "key": "human.authentication",
            "label": "身份认证",
            "condition": condition,
            "field_id": None,
            "status": "active",
            "source_refs": [],
        }
        scenario = {
            "id": channel + "-s",
            "step_id": "step",
            "target": "sender",
            "key": "human.authentication",
            "field_id": None,
            "concern_ids": [channel + "-c"],
            "condition": condition,
            "expected": "",
            "status": "active",
            "source_refs": [],
        }
        value["channels"][channel] = {"concerns": [concern], "scenarios": [scenario], "pending": []}
        if channel != "G":
            value["channels"][channel]["pending"] = [
                {
                    "id": channel + "-pending",
                    "condition": channel + "-private-source",
                    "status": "pending",
                    "needs_semantic": True,
                    "source_refs": [],
                }
            ]
    return value


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
    from scene_completion.workflow import semantics

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
