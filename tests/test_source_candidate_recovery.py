from __future__ import annotations

import json

import pytest

from scene_completion.semantic_backend import prepare_packets, read_json, write_json
from scene_completion.sources import fingerprint
from scene_completion.source_candidate_recovery import find_pending_source_correction


def _execution_result(packet, semantics):
    return {**semantics, "batch_id": packet["batch_id"], "input_hash": packet["input_hash"],
        "model": "ecnu-max", "execution_model_evidence": {"requested_model": "ecnu-max",
            "provider": "fixture"}}


def _cache(folder, stage, inputs, contract, semantics, validator):
    manifest = prepare_packets(folder, stage, inputs, [], contract)
    for row, value in zip(manifest["batches"], semantics):
        packet = read_json(folder / "packets" / f"{row['batch_id']}.json")
        write_json(folder / "results" / f"{row['batch_id']}.json", _execution_result(packet, value))
    return validator


def _scene(sid, trigger, mount_id=None):
    return {"scenario_id": sid, "trigger_condition": trigger,
        "failure_mechanism": "mechanism: " + trigger, "operation": "create",
        "mount_id": mount_id or sid}


def _review_validator(packet, result):
    units = packet["input"]["units"]
    by_id = {row["unit_id"]: row for row in result["reviews"]}
    if set(by_id) != {row["unit_id"] for row in units}:
        raise ValueError("review coverage differs")
    return [{**row, "passed": all(row[key] for key in
        ("source_supported", "atomic", "mapping_correct", "cause_correct"))}
        for row in result["reviews"]]


def _fixture(tmp_path, *, corrected_review=True):
    root = tmp_path / "case-123"
    old = [_scene("OLD1", "bad one", "M1"), _scene("OLD2", "bad two", "M2"),
        _scene("KEEP", "kept", "MK")]
    fixed = [_scene("NEW1", "fixed one", "M1"), _scene("NEW2", "fixed two", "M2"), old[2]]
    old_units = [{"unit_id": "U-OLD1", "source_scenario_id": "OLD1"},
        {"unit_id": "U-OLD2", "source_scenario_id": "OLD2"},
        {"unit_id": "U-KEEP", "source_scenario_id": "KEEP"}]
    candidate_units = [{"unit_id": "U-NEW1", "source_scenario_id": "NEW1"},
        {"unit_id": "U-NEW2", "source_scenario_id": "NEW2"},
        {"unit_id": "U-KEEP", "source_scenario_id": "KEEP"}]

    generation_validator = lambda packet, raw: raw["scenarios"]
    normalize_validator = lambda packet, raw: raw["units"]
    _cache(root / "batches" / "G-generate-supervisor-repair-4", "gap-generation",
        [{"mounts": ["m1", "m2"]}], {"scenarios": []}, [{"scenarios": fixed}], generation_validator)
    _cache(root / "batches" / "normalize-G-after-source-repair-2", "gap-normalize-G",
        [{"scenarios": fixed}], {"units": []}, [{"units": candidate_units}], normalize_validator)

    review_units = candidate_units if corrected_review else old_units
    review_scenes = fixed if corrected_review else old
    review_rows = [{"unit_id": unit["unit_id"], "source_supported": True,
        "atomic": True, "mapping_correct": True, "cause_correct": True}
        for unit in review_units]
    _cache(root / "batches" / "reverse-G-recheck-2", "gap-reverse-check-G",
        [{"units": review_units, "original_scenarios": review_scenes}], {"reviews": []},
        [{"reviews": review_rows}], _review_validator)

    journal = {"failure": {"findings": [
        {"unit_id": "U-OLD1", "source_scenario_id": "OLD1", "source_supported": True,
            "atomic": False, "mapping_correct": False, "passed": False},
        {"unit_id": "U-OLD2", "source_scenario_id": "OLD2", "source_supported": True,
            "atomic": False, "mapping_correct": False, "passed": False}]},
        "old_output": {"values": old_units}}
    (root / "repair_rounds").mkdir(parents=True)
    (root / "repair_rounds" / "reverse-G-supervisor-4.json").write_text(
        json.dumps(journal), encoding="utf-8")
    validators = {"G-generate": generation_validator,
        "normalize-G": normalize_validator, "reverse-G": _review_validator}
    return root, old, validators


def _recover(root, current, validators):
    return find_pending_source_correction(root, current, validators, lambda raw: None)


def test_recovers_valid_source_fix_and_exact_candidate_review(tmp_path):
    root, old, validators = _fixture(tmp_path)
    recovered = _recover(root, old, validators)

    assert recovered["candidate_source_repair"]["rejected_source_ids"] == ["OLD1", "OLD2"]
    assert recovered["failure"]["findings"] == []
    assert {key.rsplit(":", 1)[-1] for key in recovered["candidate_replacements"]} == {
        "G-generate", "normalize-G"}
    assert recovered["failure"]["output"]["values"]


def test_current_g_without_rejected_ids_has_no_pending_obligation(tmp_path):
    root, old, validators = _fixture(tmp_path)
    assert _recover(root, [_scene("NEW1", "fixed one"), _scene("NEW2", "fixed two")], validators) is None


def test_newer_code_only_journal_does_not_hide_source_obligation(tmp_path):
    root, old, validators = _fixture(tmp_path)
    later = {"failure": {"findings": [{"unit_id": "U-NEW1", "cause_correct": False,
        "passed": False}]}, "old_output": {"values": []}}
    (root / "repair_rounds" / "reverse-G-supervisor-5.json").write_text(
        json.dumps(later), encoding="utf-8")

    recovered = _recover(root, old, validators)
    assert recovered["failure"]["source_obligation_findings"]
    assert recovered["candidate_source_repair"]["rejected_source_ids"] == ["OLD1", "OLD2"]


def test_unrelated_passing_review_cannot_discharge_source_obligation(tmp_path):
    root, old, validators = _fixture(tmp_path, corrected_review=False)
    with pytest.raises(ValueError, match="no complete review cache"):
        _recover(root, old, validators)


def test_candidate_with_unchanged_rejected_source_is_rejected(tmp_path):
    root, old, validators = _fixture(tmp_path)
    folder = root / "batches" / "G-generate-supervisor-repair-4"
    batch = read_json(folder / "manifest.json")["batches"][0]
    packet = read_json(folder / "packets" / f"{batch['batch_id']}.json")
    result_path = folder / "results" / f"{batch['batch_id']}.json"
    result = read_json(result_path)
    result["scenarios"][0] = old[0]
    write_json(result_path, result)
    with pytest.raises(ValueError):
        _recover(root, old, validators)


def test_tampered_execution_identity_fails_closed(tmp_path):
    root, old, validators = _fixture(tmp_path)
    folder = root / "batches" / "G-generate-supervisor-repair-4"
    batch = read_json(folder / "manifest.json")["batches"][0]
    path = folder / "results" / f"{batch['batch_id']}.json"
    raw = read_json(path)
    raw["execution_model_evidence"]["requested_model"] = "other-model"
    write_json(path, raw)
    with pytest.raises(ValueError):
        _recover(root, old, validators)
