import copy

import pytest

from scene_completion.checker_taxonomy import apply_taxonomy_audit, taxonomy_packets, taxonomy_validator
from scene_completion.semantic_backend import read_json, write_json
from scene_completion.sources import fingerprint
from scene_completion.taxonomy_audit import audited_taxonomy_validator, verify_taxonomy
from tests.test_generator_model import fixture


def audit_fixture(tmp_path):
    _, _, index, _, _, _ = fixture(tmp_path)
    checker = {"complete": True, "source_hash": fingerprint(index), "scenario_count": 1,
        "scenarios": [{"scenario_id": "C1", "use_case_id": "UC-001", "name": "cancel",
            "scenario_type": "requirement_exception", "trigger": "cancel payment", "scenario_steps": ["stop"],
            "expected_result": "stop", "concern_keys": [],
            "source_refs": [{"document": "req.md", "line_start": 4, "line_end": 4}]}]}
    directory = tmp_path / "checker-taxonomy"
    manifest = taxonomy_packets(checker, index, directory)
    packet = read_json(directory / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    result = {"batch_id": packet["batch_id"], "input_hash": packet["input_hash"], "items": [{
        "scenario_id": "C1", "concern_keys": ["service.workflow.interruption"], "reason": "Cancel stops workflow",
        "source_refs": checker["scenarios"][0]["source_refs"]}]}
    return checker, index, directory, packet, result


def test_taxonomy_audit_keeps_behavior_and_denominator_frozen(tmp_path):
    checker, index, directory, packet, result = audit_fixture(tmp_path)
    assert "concern_keys" not in packet["input"]["scenarios"][0]
    assert "design.md" not in str(packet)
    assert not apply_taxonomy_audit(checker, index, directory)["complete"]
    class Client:
        def model(self, _): return "ecnu-max"
        def agent(self, _): return {"verdicts": [{"scenario_id": "C1", "trigger_quote": "cancel payment",
            "assessments": [{"key": "service.workflow.interruption", "supported": True,
                             "reason": "Cancel stops business workflow"}],
            "reason": "Source explicitly describes cancellation", "source_refs": result["items"][0]["source_refs"]}]}
    result = verify_taxonomy(packet, result, Client(), index)
    write_json(directory / "results" / (packet["batch_id"] + ".json"), result)
    audited = apply_taxonomy_audit(checker, index, directory)
    assert audited["complete"] and audited["scenario_count"] == checker["scenario_count"]
    assert audited["scenarios"][0]["concern_keys"] == ["service.workflow.interruption"]
    for key, value in checker["scenarios"][0].items():
        if key != "concern_keys": assert audited["scenarios"][0][key] == value
    assert audited["taxonomy_audit"]["changes"][0]["old_keys"] == []
    changed = copy.deepcopy(checker)
    changed["scenarios"][0]["trigger"] = "different trigger"
    with pytest.raises(ValueError, match="stale"):
        apply_taxonomy_audit(changed, index, directory)


@pytest.mark.parametrize("defect", ["omission", "unknown_id", "unknown_key", "bad_citation"])
def test_taxonomy_audit_rejects_incomplete_or_unbound_decisions(tmp_path, defect):
    _, index, _, packet, result = audit_fixture(tmp_path)
    if defect == "omission": result["items"] = []
    if defect == "unknown_id": result["items"][0]["scenario_id"] = "new-scene"
    if defect == "unknown_key": result["items"][0]["concern_keys"] = ["invented.key"]
    if defect == "bad_citation": result["items"][0]["source_refs"][0]["line_end"] = 999
    with pytest.raises(ValueError): taxonomy_validator(index)(packet, result)


def test_classification_proof_rejects_omitted_proposed_keys_and_stale_quotes(tmp_path):
    _, index, _, packet, result = audit_fixture(tmp_path)
    with pytest.raises(ValueError, match="independent"):
        audited_taxonomy_validator(index)(packet, result)
    class Client:
        def model(self, _): return "ecnu-max"
        def agent(self, _): return {"verdicts": [{"scenario_id": "C1", "trigger_quote": "cancel payment",
            "assessments": [{"key": "service.workflow.interruption", "supported": False,
                             "reason": "Reject this proposed classification"}],
            "reason": "Taxonomy gap preserved", "source_refs": result["items"][0]["source_refs"]}]}
    verified = verify_taxonomy(packet, result, Client(), index)
    assert verified["items"][0]["concern_keys"] == []
    assert verified["classification_verification"]["proposed_items"][0]["concern_keys"] == ["service.workflow.interruption"]
    assert audited_taxonomy_validator(index)(packet, verified)
    verified["classification_verification"]["verdicts"][0]["trigger_quote"] = "another condition"
    with pytest.raises(ValueError, match="quote"):
        audited_taxonomy_validator(index)(packet, verified)


def test_classification_can_cite_explicitly_supplied_requirement_context(tmp_path):
    _, index, _, packet, result = audit_fixture(tmp_path)
    result["items"][0]["source_refs"] = [{"document": "req.md", "line_start": 1, "line_end": 1}]
    assert taxonomy_validator(index)(packet, result)[0]["source_refs"][0]["line_start"] == 1
    packet["input"]["requirement_context"] = []
    with pytest.raises(ValueError, match="outside"):
        taxonomy_validator(index)(packet, result)


def test_generator_classification_reads_own_sources_and_preserves_all_candidates(tmp_path):
    _, index, _, _, _, _ = fixture(tmp_path)
    branch = {"scenario_id": "GEN-1", "use_case_id": "UC-001", "name": "cancel",
        "scenario_type": "requirement_exception", "generation_status": "explicit", "trigger": "cancel payment",
        "scenario_steps": ["stop"], "expected_result": "stop", "concern_keys": ["common.timeout"],
        "source_refs": [{"document": "req.md", "line_start": 4, "line_end": 4}]}
    derived = {**copy.deepcopy(branch), "scenario_id": "GEN-2", "scenario_type": "concern_derived_exception",
               "generation_status": "constraint_instantiation"}
    generic = {**copy.deepcopy(derived), "scenario_id": "GEN-3", "generation_status": "unreviewed_candidate"}
    generator = {"role": "generator", "complete": True, "scenario_count": 3, "llm_review_used": False,
                 "scenarios": [branch, derived, generic]}
    directory = tmp_path / "generator-taxonomy"
    manifest = taxonomy_packets(generator, index, directory, "generator")
    packet = read_json(directory / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    assert packet["stage"] == "generator-taxonomy"
    assert "design.md" in str(packet) and "checker_scenarios" not in str(packet)
    assert {s["scenario_id"] for s in packet["input"]["scenarios"]} == {"GEN-1", "GEN-2"}
    assert all("concern_keys" not in s for s in packet["input"]["scenarios"])
    result = {"batch_id": packet["batch_id"], "input_hash": packet["input_hash"], "items": [
        {"scenario_id": s["scenario_id"], "concern_keys": ["service.workflow.interruption"],
         "reason": "Source cancellation", "source_refs": s["source_refs"]} for s in (branch, derived)]}
    class Client:
        def model(self, _): return "ecnu-max"
        def agent(self, request):
            assert request["stage"] == "generator-taxonomy-verification"
            return {"verdicts": [{"scenario_id": s["scenario_id"], "trigger_quote": s["trigger"],
                "assessments": [{"key": "service.workflow.interruption", "supported": True, "reason": "Source cancellation"}],
                "reason": "Source cancellation", "source_refs": s["source_refs"]} for s in (branch, derived)]}
    result = verify_taxonomy(packet, result, Client(), index)
    write_json(directory / "results" / (packet["batch_id"] + ".json"), result)
    audited = apply_taxonomy_audit(generator, index, directory, "generator")
    assert audited["complete"] and audited["scenario_count"] == 3 and not audited["llm_review_used"]
    assert audited["scenarios"][2] == generic
    for old, new in zip(generator["scenarios"][:2], audited["scenarios"][:2]):
        assert new["concern_keys"] == ["service.workflow.interruption"]
        assert all(new[k] == v for k, v in old.items() if k != "concern_keys")
