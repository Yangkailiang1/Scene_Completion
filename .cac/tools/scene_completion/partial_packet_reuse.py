"""Offline reuse of individually unchanged, previously validated semantic packets.

The source execution remains immutable: its packet, result, model identity and
execution proof are copied byte-for-byte. Only the destination manifest is
updated, and only after the source packet/result pass current integrity,
execution-identity and semantic validation.
"""
from __future__ import annotations

import copy
import shutil
from pathlib import Path

from .interaction_execution_identity import copy_execution_sidecars, validate_result_execution
from .response_contract import contract_view
from .semantic_backend import read_json, write_json
from .sources import fingerprint


EXECUTION_PARAGRAPHS = ("批量运行默认按用例的依赖通过后立即推进", "批量无法完成时",
    "批量语义模型从运行配置", "运行前先执行可用模型检查及配置")


def semantic_packet(packet: dict) -> dict:
    """Normalize only execution identity/version fields before exact comparison."""
    value = copy.deepcopy(packet)
    value.pop("batch_id", None)
    value.pop("input_hash", None)
    if isinstance(value.get("input"), dict):
        if value.get('stage')=='gap-generation':
            from .generation_compaction import decode, INSTRUCTION
            if value['input'].get('generation_compaction'):
                value['input']=decode(value['input'])
            value['instructions']=[line for line in value.get('instructions',[]) if line!=INSTRUCTION]
        for field in ("execution_versions", "test_parser_version"):
            value["input"].pop(field, None)
        for field in ("skill", "generator_skill"):
            text = value["input"].get(field)
            if isinstance(text, str) and "name: scene-concern-gap\n" in text:
                value["input"][field] = "\n\n".join(paragraph for paragraph in text.split("\n\n")
                    if not paragraph.startswith(EXECUTION_PARAGRAPHS))
    return value


def _contains_explicit_rejection(value) -> bool:
    """Fail closed when a validator result contains a rejected review/status."""
    if isinstance(value, dict):
        for key in ("passed", "valid"):
            if key in value:
                verdict = value[key]
                if isinstance(verdict, bool):
                    if not verdict:
                        return True
                elif isinstance(verdict, str):
                    if verdict.strip().casefold() not in {"true", "yes", "valid", "passed", "pass"}:
                        return True
                else:
                    return True
        status = value.get("status")
        if isinstance(status, str) and status.strip().casefold() in {"invalid", "rejected", "failed", "fail"}:
            return True
        return any(_contains_explicit_rejection(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_explicit_rejection(child) for child in value)
    return False


def _check_packet(packet: dict, batch: dict, expected_stage: str) -> None:
    if not isinstance(packet, dict) or packet.get("stage") != expected_stage:
        raise ValueError("source packet stage differs from destination stage")
    bid, input_hash = batch.get("batch_id"), batch.get("input_hash")
    if (not isinstance(bid, str) or packet.get("batch_id") != bid
            or not isinstance(input_hash, str) or packet.get("input_hash") != input_hash):
        raise ValueError("source packet identity differs from its manifest entry")
    computed = fingerprint({key: value for key, value in packet.items() if key not in {"batch_id", "input_hash"}})
    if computed != input_hash:
        raise ValueError("source packet hash does not match its manifest")


def _copy_exact(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != source.read_bytes():
            raise ValueError(f"destination already contains conflicting artifact: {destination.name}")
        return
    shutil.copyfile(source, destination)


def reuse_from(source_folder, destination_folder, validator, cache_identity):
    """Reuse unique, semantically identical source batches that still validate.

    ``cache_identity`` is the caller's configured execution-identity check and
    must raise ``ValueError`` when the saved execution is not acceptable.
    The return value identifies reused original batch IDs and destination
    batches that remain to be executed.
    """
    source = Path(source_folder).resolve()
    destination = Path(destination_folder).resolve()
    if source == destination:
        raise ValueError("source and destination packet folders must be distinct")
    source_manifest_path, destination_manifest_path = source / "manifest.json", destination / "manifest.json"
    if not source_manifest_path.is_file() or not destination_manifest_path.is_file():
        raise ValueError("source and destination manifests are required")
    source_manifest, destination_manifest = read_json(source_manifest_path), read_json(destination_manifest_path)
    if source_manifest.get("stage") != destination_manifest.get("stage"):
        raise ValueError("source and destination packet stages differ")

    source_rows = source_manifest.get("batches")
    destination_rows = destination_manifest.get("batches")
    if not isinstance(source_rows, list) or not isinstance(destination_rows, list):
        raise ValueError("manifest batch lists are invalid")
    if len({row.get("batch_id") for row in source_rows if isinstance(row, dict)}) != len(source_rows):
        raise ValueError("source manifest batch IDs are missing or duplicated")
    if len({row.get("batch_id") for row in destination_rows if isinstance(row, dict)}) != len(destination_rows):
        raise ValueError("destination manifest batch IDs are missing or duplicated")
    if source_manifest.get("input_hash") != fingerprint(source_rows):
        raise ValueError("source manifest batch-list hash is invalid")
    if destination_manifest.get("input_hash") != fingerprint(destination_rows):
        raise ValueError("destination manifest batch-list hash is invalid")

    source_packets = []
    for row in source_rows:
        if not isinstance(row, dict) or not isinstance(row.get("batch_id"), str):
            continue
        packet_path = source / "packets" / f"{row['batch_id']}.json"
        if not packet_path.is_file():
            continue
        packet = read_json(packet_path)
        # Even malformed/untrusted packet contents are never used as a match.
        try:
            _check_packet(packet, row, source_manifest["stage"])
        except (ValueError, KeyError, TypeError):
            continue
        source_packets.append((row, packet))

    reused, proofs, rejected = [], [], []
    used_source_ids = set()
    updated_rows = list(destination_rows)
    for position, target_row in enumerate(destination_rows):
        if not isinstance(target_row, dict) or not isinstance(target_row.get("batch_id"), str):
            rejected.append({"batch_id": None, "reason": "invalid destination manifest entry"})
            continue
        target_id = target_row["batch_id"]
        target_packet_path = destination / "packets" / f"{target_id}.json"
        if not target_packet_path.is_file():
            rejected.append({"batch_id": target_id, "reason": "destination packet is missing"})
            continue
        target_packet = read_json(target_packet_path)
        try:
            _check_packet(target_packet, target_row, destination_manifest["stage"])
        except (ValueError, KeyError, TypeError) as exc:
            rejected.append({"batch_id": target_id, "reason": str(exc)})
            continue

        matches = [(row, packet) for row, packet in source_packets
            if semantic_packet(packet) == semantic_packet(target_packet)]
        if len(matches) != 1:
            if len(matches) > 1:
                rejected.append({"batch_id": target_id, "reason": "source semantic packet match is ambiguous"})
            continue
        source_row, source_packet = matches[0]
        source_id = source_row["batch_id"]
        if source_id in used_source_ids:
            rejected.append({"batch_id": target_id, "source_batch_id": source_id,
                "reason": "source execution has already been assigned to another destination packet"})
            continue
        src_packet = source / "packets" / f"{source_id}.json"
        src_result = source / "results" / f"{source_id}.json"
        if not src_result.is_file():
            continue
        try:
            raw = read_json(src_result)
            if (not isinstance(raw, dict) or raw.get("batch_id") != source_id
                    or raw.get("input_hash") != source_row.get("input_hash")):
                raise ValueError("source result identity differs from its packet")
            validate_result_execution(raw, result_path=src_result)
            cache_identity(raw)
            normalized = validator(source_packet, contract_view(source_packet, raw))
            if _contains_explicit_rejection(normalized):
                raise ValueError("current validator returned an explicit rejected/invalid item")
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            rejected.append({"batch_id": target_id, "source_batch_id": source_id,
                "reason": f"source result failed revalidation: {type(exc).__name__}: {exc}"})
            continue

        dst_packet = destination / "packets" / f"{source_id}.json"
        dst_result = destination / "results" / f"{source_id}.json"
        try:
            _copy_exact(src_packet, dst_packet)
            _copy_exact(src_result, dst_result)
            copy_execution_sidecars(raw, src_result, dst_result)
            # Verify copied native proofs against the destination's portable sidecars too.
            validate_result_execution(raw, result_path=dst_result)
        except (ValueError, OSError) as exc:
            rejected.append({"batch_id": target_id, "source_batch_id": source_id,
                "reason": f"copy or copied proof verification failed: {type(exc).__name__}: {exc}"})
            continue

        # Keep the original manifest row and source packet/result bytes. No
        # model labels, execution evidence, or hashes are rewritten.
        updated_rows[position] = copy.deepcopy(source_row)
        reused.append(source_id)
        used_source_ids.add(source_id)
        proofs.append({"destination_batch_id": target_id, "reused_batch_id": source_id,
            "input_hash": source_row["input_hash"], "model": raw.get("model"),
            "result_hash": fingerprint(raw)})

    if updated_rows != destination_rows:
        destination_manifest["batches"] = updated_rows
        destination_manifest["input_hash"] = fingerprint(updated_rows)
        write_json(destination_manifest_path, destination_manifest)

    pending = [row["batch_id"] for row in updated_rows
        if not (destination / "results" / f"{row['batch_id']}.json").is_file()]
    return {"reused_batch_ids": reused, "proofs": proofs,
        "pending_batch_ids": pending, "rejected": rejected}


def reuse(folder, previous, validator, cache_identity):
    """Compatibility adapter for an in-place packet-folder regeneration.

    ``prepare_packets`` keeps prior packet/result files in the same folder and
    replaces only its manifest. This adapter preserves that established DAG
    call shape while applying the same exact-hash, execution and validator
    checks as :func:`reuse_from`.
    """
    root = Path(folder).resolve()
    current = read_json(root / "manifest.json")
    if not isinstance(previous, dict):
        return []
    prior_rows = previous.get("batches", []) if isinstance(previous, dict) else []
    if not isinstance(prior_rows, list) or current.get("stage") != previous.get("stage"):
        return []
    if current.get("input_hash") != fingerprint(current.get("batches", [])):
        raise ValueError("partial reuse current manifest batch-list hash is invalid")
    if previous.get("input_hash") != fingerprint(prior_rows):
        raise ValueError("partial reuse previous manifest batch-list hash is invalid")

    sources = []
    for row in prior_rows:
        if not isinstance(row, dict) or not isinstance(row.get("batch_id"), str):
            continue
        packet_path = root / "packets" / f"{row['batch_id']}.json"
        if not packet_path.is_file():
            continue
        packet = read_json(packet_path)
        try:
            _check_packet(packet, row, current["stage"])
        except (ValueError, KeyError, TypeError):
            continue
        sources.append((row, packet))

    reused_rows, proofs, used = list(current["batches"]), [], set()
    for index, row in enumerate(current["batches"]):
        packet_path = root / "packets" / f"{row['batch_id']}.json"
        packet = read_json(packet_path)
        try:
            _check_packet(packet, row, current["stage"])
        except (ValueError, KeyError, TypeError):
            continue
        matches = [(old, original) for old, original in sources
            if semantic_packet(original) == semantic_packet(packet)]
        if len(matches) != 1:
            continue
        old, original = matches[0]
        if old["batch_id"] == row["batch_id"] or old["batch_id"] in used:
            continue
        result_path = root / "results" / f"{old['batch_id']}.json"
        if not result_path.is_file():
            continue
        try:
            raw = read_json(result_path)
            if raw.get("batch_id") != old["batch_id"] or raw.get("input_hash") != old["input_hash"]:
                raise ValueError("prior result identity differs from its manifest entry")
            validate_result_execution(raw, result_path=result_path)
            cache_identity(raw)
            checked = validator(original, contract_view(original, raw))
            if _contains_explicit_rejection(checked):
                raise ValueError("current validator returned an explicit rejected/invalid item")
        except (ValueError, KeyError, TypeError, RuntimeError):
            continue
        reused_rows[index] = old
        used.add(old["batch_id"])
        proofs.append({"original_batch_id": old["batch_id"], "original_input_hash": old["input_hash"],
            "current_expected_hash": row["input_hash"], "result_hash": fingerprint(raw),
            "semantic_input_hash": fingerprint(semantic_packet(packet))})

    if proofs:
        current["batches"] = reused_rows
        current["input_hash"] = fingerprint(reused_rows)
        write_json(root / "manifest.json", current)
        history = root / "compatible_packet_reuse.json"
        records = read_json(history) if history.exists() else []
        write_json(history, records + [proof for proof in proofs if proof not in records])
    return proofs
