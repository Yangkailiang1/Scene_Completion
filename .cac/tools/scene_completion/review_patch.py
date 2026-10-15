"""Merge source-bound review retries without rerunning accepted reviews."""
from __future__ import annotations

from copy import deepcopy

from .directed_patch import _resolve_path, _verify_file_hash
from .interaction_execution_identity import validate_result_execution
from .response_contract import contract_view
from .semantic_backend import read_json
from .sources import fingerprint


def _packet_content_hash(packet):
    return fingerprint({key: value for key, value in packet.items()
        if key not in {"batch_id", "input_hash"}})


def _unit_ids(input_data, label):
    units = input_data.get("units")
    if not isinstance(units, list):
        raise ValueError(f"{label} input units must be a list")
    ids = [row.get("unit_id") if isinstance(row, dict) else None for row in units]
    if (any(not isinstance(value, str) or not value for value in ids)
            or len(ids) != len(set(ids))):
        raise ValueError(f"{label} input units need unique unit IDs")
    return ids


def _validated_reviews(packet, raw, validator, label):
    candidate = contract_view(packet, raw)
    rows = validator(packet, deepcopy(candidate))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{label} validator must return a list of review objects")
    ids = [row.get("unit_id") for row in rows]
    expected = _unit_ids(packet.get("input", {}), label)
    if (any(not isinstance(value, str) or not value for value in ids)
            or len(ids) != len(set(ids)) or set(ids) != set(expected)):
        raise ValueError(f"{label} validator reviews must cover its packet units exactly once")
    if any(type(row.get("passed")) is not bool for row in rows):
        raise ValueError(f"{label} validator reviews need explicit passed booleans")
    return rows


def _verify_narrowed_source_context(prior_input, current_input, rejected_ids):
    prior_ids = _unit_ids(prior_input, "prior")
    prior_units = {row["unit_id"]: row for row in prior_input["units"]}
    if not set(rejected_ids) <= set(prior_ids):
        raise ValueError("rejected_unit_ids include a unit absent from the original packet")
    expected_units = [prior_units[unit_id] for unit_id in prior_ids if unit_id in set(rejected_ids)]
    if current_input.get("units") != expected_units:
        raise ValueError("review patch units must be exactly the rejected original units in original order")

    prior_scenarios = prior_input.get("original_scenarios")
    current_scenarios = current_input.get("original_scenarios")
    if not isinstance(prior_scenarios, list) or not isinstance(current_scenarios, list):
        raise ValueError("review patch requires original_scenarios lists")
    source_ids = {prior_units[unit_id].get("source_scenario_id") for unit_id in rejected_ids}
    if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
        raise ValueError("rejected units must identify their original source scenarios")
    expected_scenarios = [row for row in prior_scenarios
        if isinstance(row, dict) and row.get("scenario_id") in source_ids]
    if current_scenarios != expected_scenarios or {
            row.get("scenario_id") for row in expected_scenarios} != source_ids:
        raise ValueError("review patch original_scenarios must be the exact rejected-source subset")

    prior_evidence = prior_input.get("original_evidence")
    current_evidence = current_input.get("original_evidence")
    if not isinstance(prior_evidence, list) or not isinstance(current_evidence, list):
        raise ValueError("review patch requires original_evidence lists")
    expected_evidence = [row for row in prior_evidence
        if isinstance(row, dict) and row.get("scenario_id") in source_ids]
    if current_evidence != expected_evidence:
        raise ValueError("review patch original_evidence must be the exact rejected-source subset")


def apply_review_patch(packet, raw, base_validator):
    """Return the original full review list with only failed units re-reviewed.

    The prior packet/result and its execution proof are immutable inputs. The
    supplied patch packet must contain exactly the rejected units and matching
    original-source context. New review verdicts are returned as validated;
    this helper never flips a verdict or marks a review passed.
    """
    if not callable(base_validator):
        raise TypeError("base_validator must be callable")
    if not isinstance(packet, dict) or not isinstance(packet.get("input"), dict):
        raise ValueError("review patch packet must contain an input object")
    current_input = packet["input"]
    directive = current_input.get("review_patch")
    if not isinstance(directive, dict):
        raise ValueError("review packet is missing review_patch instructions")
    if packet.get("input_hash") != _packet_content_hash(packet):
        raise ValueError("review patch packet input_hash does not verify its contents")

    rejected_ids = directive.get("rejected_unit_ids")
    if (not isinstance(rejected_ids, list) or not rejected_ids
            or any(not isinstance(value, str) or not value for value in rejected_ids)
            or len(rejected_ids) != len(set(rejected_ids))):
        raise ValueError("rejected_unit_ids must be a nonempty unique list")
    execution = directive.get("prior_execution")
    required = {"result_path", "result_hash", "packet_path", "packet_hash"}
    if not isinstance(execution, dict) or not required <= set(execution):
        raise ValueError("review_patch.prior_execution must bind the original result and packet")

    result_path = _resolve_path(execution["result_path"], "prior result")
    packet_path = _resolve_path(execution["packet_path"], "prior packet")
    prior_raw, prior_packet = read_json(result_path), read_json(packet_path)
    _verify_file_hash(result_path, execution["result_hash"], "prior result", prior_raw)
    _verify_file_hash(packet_path, execution["packet_hash"], "prior packet", prior_packet)
    if not isinstance(prior_packet, dict) or not isinstance(prior_packet.get("input"), dict):
        raise ValueError("preserved source packet has no input object")
    if prior_packet.get("stage") != packet.get("stage"):
        raise ValueError("review patch stage differs from the preserved source stage")
    if prior_packet.get("input_hash") != _packet_content_hash(prior_packet):
        raise ValueError("preserved source packet input_hash does not verify its original contents")
    if (prior_raw.get("input_hash") != prior_packet.get("input_hash")
            or prior_raw.get("batch_id") != prior_packet.get("batch_id")):
        raise ValueError("preserved source result is not bound to the original packet")
    validate_result_execution(prior_raw, result_path=result_path)

    prior_reviews = _validated_reviews(prior_packet, prior_raw, base_validator, "prior")
    prior_by_id = {row["unit_id"]: row for row in prior_reviews}
    if not set(rejected_ids) <= set(prior_by_id):
        raise ValueError("rejected_unit_ids include a unit absent from the validated original reviews")
    if any(prior_by_id[unit_id]["passed"] is not False for unit_id in rejected_ids):
        raise ValueError("review patch cannot re-review a unit that previously passed")
    _verify_narrowed_source_context(prior_packet["input"], current_input, rejected_ids)

    if not isinstance(raw, dict):
        raise ValueError("review patch response must be an object")
    if (("batch_id" in raw or "input_hash" in raw)
            and (raw.get("batch_id") != packet.get("batch_id")
                or raw.get("input_hash") != packet.get("input_hash"))):
        raise ValueError("review patch response is bound to a different repair packet")

    patch_validator_packet = deepcopy(packet)
    patch_validator_packet["input"].pop("review_patch", None)
    patch_reviews = _validated_reviews(patch_validator_packet, raw, base_validator, "repair")
    patch_ids = [row["unit_id"] for row in patch_reviews]
    if len(patch_ids) != len(rejected_ids) or set(patch_ids) != set(rejected_ids):
        raise ValueError("repair reviews must contain exactly the requested rejected unit IDs")

    replacements = {row["unit_id"]: row for row in patch_reviews}
    return [deepcopy(replacements.get(row["unit_id"], row)) for row in prior_reviews]
