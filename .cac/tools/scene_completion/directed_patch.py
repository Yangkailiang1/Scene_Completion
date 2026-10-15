"""Apply an audited generation-only patch without rewriting successful items."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .interaction_execution_identity import validate_result_execution
from .response_contract import ENVELOPE_METADATA, contract_view
from .semantic_backend import read_json
from .sources import fingerprint


_FORBIDDEN_INPUT_KEYS = {
    "checker", "checkers", "checker_scenarios", "test", "tests",
    "checker_evidence", "checker_results", "test_evidence", "test_results",
    "test_scenarios", "test_conditions", "collection_e", "collection_t",
    "evidence_e", "evidence_t", "external_findings",
}


def validate_generation_progress(before, after, rejected_ids):
    """A directed source repair must actually replace every rejected cause."""
    if (not isinstance(rejected_ids, list) or not rejected_ids
            or any(not isinstance(value, str) or not value for value in rejected_ids)
            or len(set(rejected_ids)) != len(rejected_ids)):
        raise ValueError('source repair requires unique rejected source scenario IDs')
    rejected = set(rejected_ids)
    if before is not None and not rejected <= {row['scenario_id'] for row in before}:
        raise ValueError('source repair refers to an unknown original scenario')
    if rejected & {row['scenario_id'] for row in after}:
        raise ValueError('source repair left a rejected source condition unchanged')


def _resolve_path(value, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"directed patch {label} path is missing")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"directed patch {label} file does not exist")
    return path


def _verify_file_hash(path: Path, expected, label: str, parsed=None) -> None:
    if not isinstance(expected, str) or not expected.strip():
        raise ValueError(f"directed patch {label} hash is missing")
    raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    semantic_hash = fingerprint(parsed) if parsed is not None else None
    if expected not in {raw_hash, semantic_hash}:
        raise ValueError(f"directed patch {label} hash differs from the preserved artifact")


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).casefold()
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _base_validator(index_or_validator, base_validator):
    if base_validator is not None:
        if not callable(base_validator):
            raise TypeError("base_validator must be callable")
        return base_validator
    if callable(index_or_validator):
        return index_or_validator
    if index_or_validator is None:
        raise ValueError("supply a source index or the original generation validator")
    from .concern_gap_batches import generation_validator
    return generation_validator(index_or_validator)


def _validated_scenarios(packet, result, validator):
    value = contract_view(packet, result)
    normalized = validator(packet, copy.deepcopy(value))
    if not isinstance(normalized, list):
        raise ValueError("original generation validator did not return a scenario list")
    items = value.get("items")
    if not isinstance(items, list):
        raise ValueError("generation result items must be a list")
    raw_rows = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("mount_id"), str):
            raise ValueError("generation result contains an invalid mount item")
        scenarios = item.get("scenarios")
        if not isinstance(scenarios, list):
            raise ValueError("generation mount scenarios must be a list")
        for offset, scenario in enumerate(scenarios):
            if not isinstance(scenario, dict):
                raise ValueError("generation scenario must be an object")
            raw_rows.append((item["mount_id"], offset, scenario))
    if len(raw_rows) != len(normalized):
        raise ValueError("validator scenario order/count differs from original raw generation items")
    by_id = {}
    for (mount_id, offset, scenario), checked in zip(raw_rows, normalized):
        scenario_id = checked.get("scenario_id") if isinstance(checked, dict) else None
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ValueError("generation validator omitted a stable scenario_id")
        if scenario_id in by_id:
            raise ValueError("original generation result contains duplicate scenario IDs")
        by_id[scenario_id] = {"mount_id": mount_id, "offset": offset,
            "raw_scenario": copy.deepcopy(scenario), "validated": checked}
    return value, normalized, by_id


def apply_generation_patch(packet, raw, index_or_validator=None, *, base_validator=None):
    """Merge a response containing only directed replacements into prior G output.

    The original execution and packet proofs are verified before they are read.
    This function returns the immutable original packet and an in-memory merged
    result; it writes no acceptance labels and does not alter either saved source.
    ``index_or_validator`` may be the source index used to build the repository's
    generation validator, or a callable validator for offline fixtures.
    """
    if not isinstance(packet, dict) or packet.get("stage") != "gap-generation":
        raise ValueError("directed patch applies only to gap-generation packets")
    current_hash = fingerprint({key: value for key, value in packet.items()
        if key not in {"batch_id", "input_hash"}})
    if packet.get("input_hash") != current_hash:
        raise ValueError("directed patch packet input_hash does not verify its contents")
    data = packet.get("input")
    directive = data.get("directed_patch") if isinstance(data, dict) else None
    if not isinstance(directive, dict):
        raise ValueError("generation packet is missing directed_patch instructions")
    execution = directive.get("prior_execution")
    if not isinstance(execution, dict):
        raise ValueError("directed_patch.prior_execution must bind the original result and packet")
    required = {"result_path", "result_hash", "packet_path", "packet_hash"}
    if not required <= set(execution):
        raise ValueError("prior_execution is missing standard result/packet path or hash fields")

    rejected_ids = directive.get("rejected_scenario_ids")
    if (not isinstance(rejected_ids, list) or not rejected_ids
            or any(not isinstance(value, str) or not value.strip() for value in rejected_ids)
            or len(rejected_ids) != len(set(rejected_ids))):
        raise ValueError("rejected_scenario_ids must be a nonempty unique list of source G IDs")

    if _FORBIDDEN_INPUT_KEYS & set(_walk_keys(data)):
        raise ValueError("directed generation patch input must not include checker or E/T evidence")

    result_path = _resolve_path(execution["result_path"], "prior result")
    packet_path = _resolve_path(execution["packet_path"], "prior packet")
    prior_raw, prior_packet = read_json(result_path), read_json(packet_path)
    _verify_file_hash(result_path, execution["result_hash"], "prior result", prior_raw)
    _verify_file_hash(packet_path, execution["packet_hash"], "prior packet", prior_packet)
    if not isinstance(prior_packet, dict) or prior_packet.get("stage") != "gap-generation":
        raise ValueError("preserved source packet is not a gap-generation packet")
    prior_input_hash = prior_packet.get("input_hash")
    prior_batch_id = prior_packet.get("batch_id")
    packet_hash = fingerprint({key: value for key, value in prior_packet.items()
        if key not in {"batch_id", "input_hash"}})
    if not isinstance(prior_input_hash, str) or prior_input_hash != packet_hash:
        raise ValueError("preserved source packet input_hash does not verify its original contents")
    if (prior_raw.get("input_hash") != prior_input_hash
            or prior_raw.get("batch_id") != prior_batch_id):
        raise ValueError("preserved source result is not bound to the original packet")
    if not isinstance(prior_packet.get("input"), dict):
        raise ValueError("preserved source packet has no generation input")
    validate_result_execution(prior_raw, result_path=result_path)

    validator = _base_validator(index_or_validator, base_validator)
    original_input, original_scenarios, source_by_id = _validated_scenarios(prior_packet, prior_raw, validator)
    if not set(rejected_ids) <= set(source_by_id):
        raise ValueError("rejected_scenario_ids include IDs absent from the validated original G output")

    if not isinstance(raw, dict):
        raise ValueError("directed patch response must be an object")
    raw = contract_view(packet, raw)
    if set(raw) - (ENVELOPE_METADATA | {"replacements"}):
        raise ValueError("directed patch response may contain replacements and transport metadata only")
    if raw.get("stage", packet["stage"]) != packet["stage"]:
        raise ValueError("directed patch response stage differs from the repair packet")
    replacements = raw.get("replacements")
    if not isinstance(replacements, list):
        raise ValueError("directed patch response must contain a replacements list")
    replacement_ids = [row.get("source_scenario_id") if isinstance(row, dict) else None
        for row in replacements]
    if (len(replacement_ids) != len(rejected_ids)
            or any(not isinstance(value, str) for value in replacement_ids)
            or len(replacement_ids) != len(set(replacement_ids))
            or set(replacement_ids) != set(rejected_ids)):
        raise ValueError("each rejected source G ID must be replaced exactly once; no other ID is allowed")

    # New repair attempts retain their own identity check when the transport
    # attached one. The returned merged result below keeps the original proof.
    if "batch_id" in raw or "input_hash" in raw:
        if (raw.get("batch_id") != packet.get("batch_id")
                or raw.get("input_hash") != packet.get("input_hash")):
            raise ValueError("directed patch response is bound to a different repair packet")
    if "execution_model_evidence" in raw or "model" in raw:
        validate_result_execution(raw)

    merged_raw = copy.deepcopy(prior_raw)
    merged_items = copy.deepcopy(original_input["items"])
    mount_for_rejected = {source_id: source_by_id[source_id]["mount_id"] for source_id in rejected_ids}
    replacement_scenarios = {}
    for row in replacements:
        if not isinstance(row, dict) or set(row) != {"source_scenario_id", "scenarios"}:
            raise ValueError("replacement rows must contain only source_scenario_id and scenarios")
        source_id, scenarios = row["source_scenario_id"], row["scenarios"]
        if not isinstance(scenarios, list) or not scenarios or any(not isinstance(scene, dict) for scene in scenarios):
            raise ValueError("each rejected source scenario needs one or more complete replacement scenarios")
        replacement_scenarios[source_id] = copy.deepcopy(scenarios)

    by_mount = {item["mount_id"]: item for item in merged_items}
    if len(by_mount) != len(merged_items):
        raise ValueError("original generation result contains duplicate mount IDs")
    offsets = {source_id: source_by_id[source_id]["offset"] for source_id in rejected_ids}
    by_mount_offsets = {}
    for source_id in rejected_ids:
        by_mount_offsets.setdefault(mount_for_rejected[source_id], []).append(source_id)
    for mount_id, source_ids in by_mount_offsets.items():
        item = by_mount.get(mount_id)
        if item is None:
            raise ValueError("rejected scenario points to a mount absent from original raw.items")
        scenarios = item.get("scenarios")
        if not isinstance(scenarios, list):
            raise ValueError("original mount scenarios must be a list")
        # Use original offsets in descending order. Expanding a later rejected
        # scenario cannot shift any earlier source scenario's original index.
        for source_id in sorted(source_ids, key=lambda value: offsets[value], reverse=True):
            offset = offsets[source_id]
            if offset >= len(scenarios):
                raise ValueError("rejected scenario no longer resolves to its original raw scenario")
            # Replace precisely one source scenario. Every neighboring raw
            # object is carried over byte-for-byte at the JSON-value level.
            scenarios = scenarios[:offset] + replacement_scenarios[source_id] + scenarios[offset + 1:]
        item["scenarios"] = scenarios

    merged_raw["items"] = merged_items
    # Run the unmodified original generation validator over the complete merged
    # result. It assigns authoritative scenario IDs and rejects collateral damage.
    _, merged_scenarios, merged_by_id = _validated_scenarios(prior_packet, merged_raw, validator)
    untouched_ids = set(source_by_id) - set(rejected_ids)
    if not untouched_ids <= set(merged_by_id):
        raise ValueError("directed patch removed an untouched successful source scenario")
    for scenario_id in untouched_ids:
        original = source_by_id[scenario_id]
        current = merged_by_id[scenario_id]
        if (current["mount_id"] != original["mount_id"]
                or current["raw_scenario"] != original["raw_scenario"]):
            raise ValueError("directed patch altered an untouched successful raw scenario")
    if len(merged_scenarios) < len(untouched_ids) + len(rejected_ids):
        raise ValueError("directed patch unexpectedly deleted source scenarios")
    return prior_packet, merged_raw
