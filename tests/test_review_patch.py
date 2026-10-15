"""Offline tests for source-bound review retries."""
from __future__ import annotations

import copy

import pytest

from scene_completion.review_patch import apply_review_patch
from scene_completion.semantic_backend import prepare_packets, read_json, write_json
from scene_completion.sources import fingerprint


def _unit(unit_id, source_id):
    return {"unit_id": unit_id, "source_scenario_id": source_id,
        "concern_key": "specific-cause", "mapping_status": "mapped"}


def _scene(sid, quote):
    return {"scenario_id": sid, "trigger_condition": quote,
        "failure_mechanism": f"mechanism: {quote}", "operation": "create"}


def _base_validator(packet, raw):
    units = {row["unit_id"]: row for row in packet["input"]["units"]}
    rows = raw.get("reviews")
    if not isinstance(rows, list) or len(rows) != len(units):
        raise ValueError("wrong review count")
    ids = [row.get("unit_id") for row in rows]
    if len(set(ids)) != len(ids) or set(ids) != set(units):
        raise ValueError("wrong review IDs")
    scenes = {row["scenario_id"]: row for row in packet["input"]["original_scenarios"]}
    result = []
    for row in rows:
        unit = units[row["unit_id"]]
        source = scenes[unit["source_scenario_id"]]
        quote = row.get("evidence_quote")
        if not quote or quote not in source["trigger_condition"] and quote not in source["failure_mechanism"]:
            raise ValueError("review must quote original source")
        normalized = copy.deepcopy(row)
        normalized["passed"] = all(row[key] for key in
            ("source_supported", "atomic", "mapping_correct", "cause_correct"))
        result.append(normalized)
    return result


def _review(unit_id, quote, *, good):
    return {"unit_id": unit_id, "source_supported": good, "atomic": good,
        "mapping_correct": good, "cause_correct": good, "evidence_quote": quote,
        "reason": "checked against the source"}


def _source(tmp_path):
    source = tmp_path / "source"
    input_data = {"units": [_unit("U1", "S1"), _unit("U2", "S2"), _unit("U3", "S3")],
        "original_scenarios": [_scene("S1", "trigger one"), _scene("S2", "trigger two"),
            _scene("S3", "trigger three")],
        "original_evidence": [{"scenario_id": sid, "source_ref": f"ref-{sid}", "text": f"source {sid}"}
            for sid in ("S1", "S2", "S3")]}
    manifest = prepare_packets(source, "gap-reverse-check-G", [input_data], [],
        {"reviews": []})
    batch = manifest["batches"][0]
    packet_path = source / "packets" / f"{batch['batch_id']}.json"
    packet = read_json(packet_path)
    prior = {"batch_id": batch["batch_id"], "input_hash": batch["input_hash"],
        "model": "ecnu-max", "execution_model_evidence": {"requested_model": "ecnu-max",
            "provider": "fixture"},
        "reviews": [_review("U1", "trigger one", good=True),
            _review("U2", "trigger two", good=False), _review("U3", "trigger three", good=True)]}
    result_path = source / "results" / f"{batch['batch_id']}.json"
    write_json(result_path, prior)
    return source, packet_path, result_path, packet, prior


def _repair_packet(tmp_path, source, packet_path, result_path, prior_packet, prior_raw,
        rejected_ids=("U2",)):
    prior_input = prior_packet["input"]
    units = {row["unit_id"]: row for row in prior_input["units"]}
    source_ids = {units[unit_id]["source_scenario_id"] for unit_id in rejected_ids
        if unit_id in units}
    repair_input = copy.deepcopy(prior_input)
    prior_order = [row["unit_id"] for row in prior_input["units"]]
    repair_input["units"] = [units[unit_id] for unit_id in prior_order
        if unit_id in rejected_ids]
    repair_input["original_scenarios"] = [row for row in prior_input["original_scenarios"]
        if row["scenario_id"] in source_ids]
    repair_input["original_evidence"] = [row for row in prior_input["original_evidence"]
        if row["scenario_id"] in source_ids]
    repair_input["review_patch"] = {"rejected_unit_ids": list(rejected_ids),
        "prior_execution": {"result_path": str(result_path),
            "result_hash": fingerprint(prior_raw), "packet_path": str(packet_path),
            "packet_hash": fingerprint(prior_packet)}}
    manifest = prepare_packets(tmp_path / "repair", "gap-reverse-check-G",
        [repair_input], [], {"reviews": []})
    batch = manifest["batches"][0]
    packet = read_json(tmp_path / "repair" / "packets" / f"{batch['batch_id']}.json")
    return packet, batch


def _response(batch, rows):
    return {"batch_id": batch["batch_id"], "input_hash": batch["input_hash"],
        "model": "ecnu-max", "execution_model_evidence": {"requested_model": "ecnu-max",
            "provider": "fixture"}, "reviews": rows}


def test_rechecks_only_failed_reviews_and_merges_in_prior_order_without_mutation(tmp_path):
    source, packet_path, result_path, prior_packet, prior_raw = _source(tmp_path)
    packet, batch = _repair_packet(tmp_path, source, packet_path, result_path,
        prior_packet, prior_raw)
    raw = _response(batch, [_review("U2", "trigger two", good=False)])
    raw_before = copy.deepcopy(raw)
    original_bytes = result_path.read_bytes()

    merged = apply_review_patch(packet, raw, _base_validator)

    assert [row["unit_id"] for row in merged] == ["U1", "U2", "U3"]
    assert [row["passed"] for row in merged] == [True, False, True]
    assert merged[1]["reason"] == "checked against the source"
    assert raw == raw_before
    assert result_path.read_bytes() == original_bytes
    assert "passed" not in prior_raw["reviews"][1]


def test_failed_retry_is_preserved_and_a_retry_can_remain_failed(tmp_path):
    source, packet_path, result_path, prior_packet, prior_raw = _source(tmp_path)
    packet, batch = _repair_packet(tmp_path, source, packet_path, result_path,
        prior_packet, prior_raw)
    merged = apply_review_patch(packet,
        _response(batch, [_review("U2", "trigger two", good=False)]), _base_validator)
    assert merged[1]["passed"] is False
    assert all(row["unit_id"] != "U2" or row["passed"] is False for row in merged)


@pytest.mark.parametrize("rejected_ids", [("U1",), ("U2", "U2"), ("not-a-unit",)])
def test_rejects_passed_duplicate_or_unknown_review_targets(tmp_path, rejected_ids):
    source, packet_path, result_path, prior_packet, prior_raw = _source(tmp_path)
    packet, batch = _repair_packet(tmp_path, source, packet_path, result_path,
        prior_packet, prior_raw, rejected_ids)
    unit_id = rejected_ids[0]
    source_id = {row["unit_id"]: row["source_scenario_id"]
        for row in prior_packet["input"]["units"]}.get(unit_id, "S1")
    quote = next(row["trigger_condition"] for row in prior_packet["input"]["original_scenarios"]
        if row["scenario_id"] == source_id)
    response = _response(batch, [_review(unit_id, quote, good=False)])
    with pytest.raises(ValueError):
        apply_review_patch(packet, response, _base_validator)


def test_requires_exact_current_ids_and_rejects_duplicates(tmp_path):
    source, packet_path, result_path, prior_packet, prior_raw = _source(tmp_path)
    packet, batch = _repair_packet(tmp_path, source, packet_path, result_path,
        prior_packet, prior_raw)
    with pytest.raises(ValueError, match="wrong review count"):
        apply_review_patch(packet, _response(batch, []), _base_validator)
    with pytest.raises(ValueError, match="wrong review count"):
        apply_review_patch(packet, _response(batch, [
            _review("U2", "trigger two", good=False),
            _review("U2", "trigger two", good=False)]), _base_validator)


@pytest.mark.parametrize("artifact", ["packet", "result"])
def test_rejects_tampered_prior_artifacts(tmp_path, artifact):
    source, packet_path, result_path, prior_packet, prior_raw = _source(tmp_path)
    packet, batch = _repair_packet(tmp_path, source, packet_path, result_path,
        prior_packet, prior_raw)
    target = packet_path if artifact == "packet" else result_path
    changed = read_json(target)
    changed["tampered"] = True
    write_json(target, changed)
    with pytest.raises(ValueError, match="prior .* hash"):
        apply_review_patch(packet,
            _response(batch, [_review("U2", "trigger two", good=False)]), _base_validator)


def test_rejects_invalid_original_execution_identity_and_current_packet_hash(tmp_path):
    source, packet_path, result_path, prior_packet, prior_raw = _source(tmp_path)
    prior_raw["execution_model_evidence"]["requested_model"] = "different-model"
    write_json(result_path, prior_raw)
    packet, batch = _repair_packet(tmp_path, source, packet_path, result_path,
        prior_packet, prior_raw)
    response = _response(batch, [_review("U2", "trigger two", good=False)])
    with pytest.raises(ValueError, match="request evidence"):
        apply_review_patch(packet, response, _base_validator)

    source, packet_path, result_path, prior_packet, prior_raw = _source(tmp_path / "other")
    packet, batch = _repair_packet(tmp_path / "other", source, packet_path, result_path,
        prior_packet, prior_raw)
    packet["input"]["review_patch"]["rejected_unit_ids"] = ["U1"]
    with pytest.raises(ValueError, match="input_hash"):
        apply_review_patch(packet, _response(batch, [_review("U2", "trigger two", good=False)]),
            _base_validator)


def test_rejects_response_for_another_current_batch(tmp_path):
    source, packet_path, result_path, prior_packet, prior_raw = _source(tmp_path)
    packet, batch = _repair_packet(tmp_path, source, packet_path, result_path,
        prior_packet, prior_raw)
    response = _response(batch, [_review("U2", "trigger two", good=False)])
    response["batch_id"] = "other-batch"
    with pytest.raises(ValueError, match="different repair packet"):
        apply_review_patch(packet, response, _base_validator)


def test_rejects_broadened_original_scenarios_or_evidence_in_repair_packet(tmp_path):
    source, packet_path, result_path, prior_packet, prior_raw = _source(tmp_path)
    packet, batch = _repair_packet(tmp_path, source, packet_path, result_path,
        prior_packet, prior_raw)
    packet["input"]["original_scenarios"].append(prior_packet["input"]["original_scenarios"][0])
    packet["input_hash"] = fingerprint({key: value for key, value in packet.items()
        if key not in {"batch_id", "input_hash"}})
    with pytest.raises(ValueError, match="original_scenarios"):
        apply_review_patch(packet, _response(batch,
            [_review("U2", "trigger two", good=False)]), _base_validator)
