"""Recover a proven but unpromoted source-G correction from cached executions.

This module is deliberately read-only. It treats supervisor journals as the
source of the obligation, and only returns candidates whose generator,
normalizer, and matching reverse review all pass their current validators.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from .interaction_execution_identity import validate_result_execution
from .semantic_backend import read_json
from .sources import fingerprint


_REVIEW_DEFECTS = ("source_supported", "atomic", "mapping_correct")


def _numbered(paths):
    def number(path):
        match = re.search(r"-(\d+)$", path.stem)
        return int(match.group(1)) if match else -1
    return sorted(paths, key=lambda path: (number(path), path.name), reverse=True)


def _manifest(root):
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = read_json(manifest_path)
    batches = manifest.get("batches")
    if not isinstance(batches, list) or manifest.get("input_hash") != fingerprint(batches):
        raise ValueError(f"cached stage manifest is malformed or changed: {root}")
    return manifest


def _validated_cache(folder, validator, cache_identity):
    """Collect one complete cache and independently verify execution proofs."""
    manifest = _manifest(folder)
    if manifest is None:
        return None
    values, proofs = [], []
    from .response_contract import contract_view
    for batch in manifest["batches"]:
        result_path = folder / "results" / f"{batch['batch_id']}.json"
        packet_path = folder / "packets" / f"{batch['batch_id']}.json"
        if not result_path.is_file() or not packet_path.is_file():
            raise ValueError(f"cached candidate stage is incomplete: {folder}: {batch['batch_id']}")
        raw, packet = read_json(result_path), read_json(packet_path)
        validate_result_execution(raw, result_path=result_path)
        if cache_identity is not None:
            cache_identity(raw)
        if (raw.get("batch_id") != batch["batch_id"]
                or raw.get("input_hash") != batch["input_hash"]
                or packet.get("batch_id") != batch["batch_id"]
                or packet.get("input_hash") != batch["input_hash"]
                or fingerprint({key: value for key, value in packet.items()
                    if key not in {"batch_id", "input_hash"}}) != batch["input_hash"]):
            raise ValueError(f"cached candidate packet/result binding changed: {result_path}")
        values.extend(validator(packet, contract_view(packet, raw)))
        proofs.append({"batch_id": raw["batch_id"], "input_hash": raw["input_hash"],
            "result_path": str(result_path.resolve()), "result_hash": fingerprint(raw),
            "model": raw.get("model")})
    return {"values": values, "folder": str(folder.resolve()), "executions": proofs}


def _source_failure(findings):
    selected = []
    for row in findings:
        if not isinstance(row, dict):
            continue
        if row.get("passed") is False and (
                any(row.get(field) is False for field in _REVIEW_DEFECTS)
                or row.get("defect_origin") == "generated_identification"):
            source_id = row.get("source_scenario_id")
            if isinstance(source_id, str) and source_id:
                selected.append(row)
    ids = [row["source_scenario_id"] for row in selected]
    if not ids or len(ids) != len(set(ids)):
        return [], []
    return ids, selected


def _review_packets_bind_to_candidate(folder, candidate_units, candidate_scenarios, changed_source_ids):
    """Require each review packet to be the exact candidate, with no extra units."""
    manifest = _manifest(folder)
    if manifest is None:
        return False
    expected_units = {row.get("unit_id"): row for row in candidate_units}
    expected_sources = {row.get("scenario_id"): row for row in candidate_scenarios}
    if None in expected_units or None in expected_sources:
        raise ValueError("candidate review inputs lack stable IDs")
    packets = []
    for batch in manifest["batches"]:
        packet_path = folder / "packets" / f"{batch['batch_id']}.json"
        if not packet_path.is_file():
            raise ValueError(f"candidate review packet is missing: {packet_path}")
        packet = read_json(packet_path)
        data = packet.get("input", {})
        units = data.get("units")
        scenarios = data.get("original_scenarios")
        if not isinstance(units, list) or not isinstance(scenarios, list):
            continue
        packets.append((units, scenarios))
    if not any({row.get("scenario_id") for row in scenarios} & set(changed_source_ids)
            for _, scenarios in packets):
        return False
    seen_units = set()
    seen_sources = set()
    for units, scenarios in packets:
        unit_ids = [row.get("unit_id") for row in units]
        source_ids = [row.get("scenario_id") for row in scenarios]
        if (any(unit_id not in expected_units for unit_id in unit_ids)
                or any(source_id not in expected_sources for source_id in source_ids)
                or any(expected_units[unit_id] != row for unit_id, row in zip(unit_ids, units))
                or any(expected_sources[source_id] != row for source_id, row in zip(source_ids, scenarios))):
            raise ValueError("review cache partially overlaps or changes the source-repair candidate")
        seen_units.update(unit_ids)
        seen_sources.update(source_ids)
    return seen_units == set(expected_units) and seen_sources == set(expected_sources)


def find_pending_source_correction(root, currentG, validators, cache_identity, *, case_prefix=None):
    """Find the latest fully proven source correction that has not been promoted.

    ``validators`` is a mapping containing ``G-generate``, ``normalize-G`` and
    ``reverse-G`` callables. Missing artifacts return ``None`` when no source
    obligation can be established; a malformed or unverifiable artifact for an
    established obligation raises ``ValueError`` so callers cannot erase it.
    """
    root = Path(root).resolve()
    validators = validators or {}
    required = ("G-generate", "normalize-G", "reverse-G")
    if any(not callable(validators.get(key)) for key in required):
        raise ValueError("source correction recovery requires all three current validators")
    if isinstance(currentG, dict):
        currentG = currentG.get("values")
    if not isinstance(currentG, list):
        raise ValueError("current G must be a scenario list or a values output")
    current_by_id = {row.get("scenario_id"): row for row in currentG if isinstance(row, dict)}
    if len(current_by_id) != len(currentG) or None in current_by_id:
        raise ValueError("current G must contain unique stable scenario IDs")

    journals = _numbered((root / "repair_rounds").glob("reverse-G-supervisor-*.json"))
    if not journals:
        return None
    # Later review-code repairs may have no source IDs at all. Walk newest to
    # oldest and select the newest source obligation whose original IDs remain
    # in the live G. Once selected, a bad/missing proof is an error; do not hide
    # it by falling back to an older candidate.
    journal_path = journal = None
    rejected_ids, findings = [], []
    for candidate_path in journals:
        candidate_journal = read_json(candidate_path)
        candidate_ids, candidate_findings = _source_failure(
            candidate_journal.get("failure", {}).get("findings", []))
        remaining = [source_id for source_id in candidate_ids if source_id in current_by_id]
        if remaining:
            journal_path, journal = candidate_path, candidate_journal
            rejected_ids = remaining
            findings = [row for row in candidate_findings
                if row.get("source_scenario_id") in set(remaining)]
            break
    if journal is None:
        return None

    supervisor_round = int(re.search(r"-(\d+)$", journal_path.stem).group(1))
    generation_folder = root / "batches" / f"G-generate-supervisor-repair-{supervisor_round}"
    if not generation_folder.is_dir():
        raise ValueError("source repair obligation remains, but its generator cache is missing")
    generation = _validated_cache(generation_folder, validators["G-generate"], cache_identity)
    candidate_scenarios = generation["values"]
    from .directed_patch import validate_generation_progress
    # The journal preserves the normalized original target; its IDs still bind
    # the rejected source scenes even though generation has a separate schema.
    prior_ids = {value for row in journal.get("old_output", {}).get("values", [])
        for value in (row.get("source_scenario_id"), row.get("scenario_id")) if value}
    if not set(rejected_ids) <= prior_ids:
        raise ValueError("journal old output does not contain all rejected source IDs")
    validate_generation_progress([{"scenario_id": value} for value in prior_ids if value],
        candidate_scenarios, rejected_ids)
    if set(rejected_ids) & {row.get("scenario_id") for row in candidate_scenarios}:
        raise ValueError("cached generator did not change every rejected source scenario")
    changed_source_ids = {row.get("scenario_id") for row in candidate_scenarios} - set(current_by_id)
    rejected_mounts = {current_by_id[source_id].get("mount_id") for source_id in rejected_ids}
    candidate_mounts = {row.get("mount_id") for row in candidate_scenarios
        if row.get("scenario_id") in changed_source_ids}
    if None in rejected_mounts or not rejected_mounts <= candidate_mounts:
        raise ValueError("corrected candidate does not replace every rejected source mount")

    normalization_folders = _numbered((root / "batches").glob("normalize-G-after-source-repair-*"))
    if not normalization_folders:
        raise ValueError("source correction generator is valid, but normalized candidate cache is missing")
    normalization = None
    normalization_folder = None
    for folder in normalization_folders:
        manifest = _manifest(folder)
        if manifest is None:
            continue
        # Bind the full scenario set from packet inputs before trusting a
        # validator result. A matching stage is unique by exact source payload.
        packet_scenarios = []
        for batch in manifest["batches"]:
            packet_path = folder / "packets" / f"{batch['batch_id']}.json"
            if not packet_path.is_file():
                raise ValueError(f"candidate normalization packet is missing: {packet_path}")
            packet = read_json(packet_path)
            packet_scenarios.extend(row.get("scenario_id") for row in
                packet.get("input", {}).get("scenarios", []))
        if len(packet_scenarios) == len(candidate_scenarios) and set(packet_scenarios) == {
                row.get("scenario_id") for row in candidate_scenarios}:
            normalization = _validated_cache(folder, validators["normalize-G"], cache_identity)
            if normalization is None:
                continue
            normalization_folder = folder
            break
    if normalization is None:
        raise ValueError("no complete normalization cache is bound to the corrected G candidate")
    normalized_units = normalization["values"]
    if {row.get("source_scenario_id") for row in normalized_units} != {
            row.get("scenario_id") for row in candidate_scenarios}:
        raise ValueError("normalized candidate does not preserve the corrected G source set")

    # Only a review of these exact normalized units and corrected original
    # scenarios can discharge the old source defect. A generic passing review
    # from the task record is never used as evidence here.
    review_folders = _numbered((root / "batches").glob("reverse-G-recheck-*"))
    review_folders += [folder for folder in _numbered((root / "batches").glob("reverse-G-supervisor-repair-*"))
        if folder not in review_folders]
    review_output = None
    for folder in review_folders:
        if not _review_packets_bind_to_candidate(folder, normalized_units, candidate_scenarios, changed_source_ids):
            continue
        review_output = _validated_cache(folder, validators["reverse-G"], cache_identity)
        if review_output is not None:
            break
    if review_output is None:
        raise ValueError("corrected G candidate has no complete review cache bound to its normalization")
    reviewed = review_output["values"]
    if {row.get("unit_id") for row in reviewed} != {row.get("unit_id") for row in normalized_units}:
        raise ValueError("candidate review output does not cover corrected normalized units")

    prefix = case_prefix or root.name
    replacements = {f"{prefix}:G-generate": generation,
        f"{prefix}:normalize-G": normalization}
    source_repair = {"generation_task": f"{prefix}:G-generate",
        "prior_output_hash": fingerprint(journal.get("old_output")),
        "corrected_output_hash": fingerprint(generation),
        "rejected_source_ids": rejected_ids}
    pending_findings = [deepcopy(row) for row in reviewed if row.get("passed") is False]
    return {"candidate_replacements": replacements,
        "candidate_source_repair": source_repair,
        "failure": {"findings": pending_findings, "output": review_output,
            "candidate_replacements": replacements,
            "candidate_source_repair": source_repair,
            "source_obligation_findings": findings,
            "recovered_from_journal": str(journal_path.resolve()),
            "normalization_folder": str(normalization_folder.resolve())}}
