"""Freeze independently reviewed C across generator-only optimization rounds."""
from pathlib import Path
import shutil

from . import interaction_batches as batches
from .interaction_protocol import PROTOCOL
from .semantic_backend import collect_packets, read_json, write_json
from .sources import fingerprint
from .interaction_execution_identity import validate_result_execution, copy_execution_sidecars


def extraction_signature(packet):
    return fingerprint({"stage": packet["stage"], "input": {k: v for k, v in packet["input"].items() if k != "execution_versions"},
        "instructions": packet["instructions"], "output_contract": packet["output_contract"]})


def record_source_review(root, index):
    """Record actual completed independent source audit, never caller booleans."""
    from .interaction_audit import verify_checker_audit, checker_audit_proof_hash
    root = Path(root)
    audited = verify_checker_audit(root, index)
    frozen = read_json(root / 'existing_scenarios.json')
    folder = root / 'batches/interaction-checker'
    rows, status = collect_packets(folder, batches.checker_validator(index))
    if not status['complete'] or rows != frozen['scenarios'] or fingerprint(rows) != frozen['baseline_hash'] or frozen['source_hash'] != fingerprint(index):
        raise ValueError('cannot record source review for altered/incomplete C')
    evidence = []
    identities = []
    from .interaction_versions import packet_versions
    for batch in read_json(folder / 'manifest.json')['batches']:
        packet = read_json(folder / 'packets' / (batch['batch_id'] + '.json'))
        if packet['input'].get('execution_versions') != packet_versions('interaction-checker'):
            raise ValueError('C source review extraction dependencies are stale')
        result_path = folder / 'results' / (batch['batch_id'] + '.json')
        raw = read_json(result_path)
        identity = validate_result_execution(raw, result_path=result_path)
        identities.append(identity)
        proof = raw.get('execution_model_evidence', {})
        evidence.append({'batch_id': batch['batch_id'], 'evidence': proof})
    execution_models = sorted({identity['model'] for identity in identities})
    proof_kinds = sorted({identity['proof_kind'] for identity in identities})
    reviewer = ('ecnu-max independent source-only audit' if execution_models == ['ecnu-max'] else
        'independent source-only audit; execution models: ' + ', '.join(execution_models))
    review = {'passed': True, 'reviewer': reviewer, 'execution_models': execution_models,
        'execution_proof_kinds': proof_kinds,
        'baseline_hash': frozen['baseline_hash'], 'source_hash': fingerprint(index),
        'source_audit_hash': checker_audit_proof_hash(root), 'execution_evidence_hash': fingerprint(evidence),
        'unresolved_findings': [], 'reviewed_batches': len(audited),
        'note': 'Source baseline audit only; does not replace final gpt-6-luna/max effect review or formal acceptance.'}
    write_json(root / 'baseline_review.json', review)
    return review


def verify_baseline(directory, target, index):
    """Changes in original text, taxonomy or extraction rules invalidate reuse."""
    directory, target = Path(directory), Path(target)
    baseline = read_json(directory / "existing_scenarios.json")
    review = read_json(directory / "baseline_review.json")
    if (baseline.get("protocol") != PROTOCOL or baseline.get("complete") is not True or
            baseline.get("source_hash") != fingerprint(index) or baseline.get("baseline_hash") != fingerprint(baseline["scenarios"]) or
            review.get("passed") is not True or review.get("baseline_hash") != baseline["baseline_hash"] or
            review.get("source_hash") != baseline["source_hash"] or not review.get("reviewer") or review.get("unresolved_findings")):
        raise ValueError("frozen checker baseline must be independently reviewed and bound to unchanged original sources")
    source = directory / "batches" / "interaction-checker"
    old = read_json(source / "manifest.json")["batches"]
    new = read_json(target / "manifest.json")["batches"]
    if len(old) != len(new):
        raise ValueError("frozen checker assignment count changed")
    rows, status = collect_packets(source, batches.checker_validator(index))
    if not status["complete"] or rows != baseline["scenarios"]:
        raise ValueError("frozen checker source batches are incomplete or differ from C")
    from .interaction_audit import verify_checker_audit, checker_audit_proof_hash
    verify_checker_audit(directory, index)
    if review.get('source_audit_hash') != checker_audit_proof_hash(directory):
        raise ValueError('frozen baseline source audit differs from reviewed proof')
    identities = []
    for batch in old:
        result_path = source / 'results' / (batch['batch_id'] + '.json')
        raw = read_json(result_path)
        identities.append(validate_result_execution(raw, result_path=result_path))
    evidence_hash = fingerprint([{ "batch_id": b["batch_id"], "evidence": read_json(source / "results" / (b["batch_id"] + ".json")).get("execution_model_evidence", {})} for b in old])
    if review.get("execution_evidence_hash") != evidence_hash:
        raise ValueError("frozen baseline execution evidence differs from reviewed identity")
    if ('execution_models' in review and review['execution_models'] != sorted({v['model'] for v in identities})):
        raise ValueError('frozen baseline recorded execution models differ from original results')
    if ('execution_proof_kinds' in review and review['execution_proof_kinds'] != sorted({v['proof_kind'] for v in identities})):
        raise ValueError('frozen baseline recorded execution proof kinds differ from original results')
    for original, current in zip(old, new):
        packet = read_json(source / "packets" / (original["batch_id"] + ".json"))
        expected = read_json(target / "packets" / (current["batch_id"] + ".json"))
        result = read_json(source / "results" / (original["batch_id"] + ".json"))
        if extraction_signature(packet) != extraction_signature(expected):
            raise ValueError("checker source assignment, extraction rules or actual model changed")
        validate_result_execution(result, result_path=source / 'results' / (original['batch_id'] + '.json'))
        if result.get("baseline_execution"):
            raise ValueError("baseline must originate from direct independent extraction, not an imported baseline")
    return baseline, review, old, new


def checker_extraction_skill(text):
    """Only an explicit reporting-policy migration is extraction-neutral.

    Arbitrary Skill edits may change C despite identical Python validators.
    Historical packet text and execution proof are preserved unchanged.
    """
    old = 'RR、SR各自须≤5%且各自C非空，合计单独报告。'
    new = 'RR、SR分别如实报告，合计单独报告，空分母为null。当前只验流程，不设置漏报率通过阈值。'
    return text.replace(old, '<coverage-report-policy>').replace(new, '<coverage-report-policy>')


def import_baseline(filename, root, index, base, *, retain_source_packets=False):
    root, filename = Path(root), Path(filename).resolve()
    directory = filename.parent
    if filename.name != "existing_scenarios.json" or directory == root.resolve():
        raise ValueError("checker-input must refer to another round's reviewed existing_scenarios.json")
    target = root / "batches" / "interaction-checker"
    if retain_source_packets:
        # An independently reviewed baseline remains evidence of its original
        # Skill, never a new extraction using today's reporting instructions.
        # Actual extraction code, source assignments, taxonomy and explicit
        # extraction instructions must remain unchanged. Report-policy prose
        # in checker_skill may change without buying another extraction.
        from tempfile import TemporaryDirectory
        from .interaction_versions import packet_versions
        source = directory / 'batches/interaction-checker'
        source_manifest = read_json(source/'manifest.json')
        with TemporaryDirectory(prefix='scene-frozen-assignment-') as temporary:
            expected = batches.checker_packets(base, index, temporary)
            if len(expected['batches']) != len(source_manifest['batches']):
                raise ValueError('retained checker source assignment count changed')
            for old, new in zip(source_manifest['batches'], expected['batches']):
                original = read_json(source/'packets'/(old['batch_id']+'.json'))
                current = read_json(Path(temporary)/'packets'/(new['batch_id']+'.json'))
                old_core = {k: v for k, v in original['input'].items() if k != 'checker_skill'}
                new_core = {k: v for k, v in current['input'].items() if k != 'checker_skill'}
                if (old_core != new_core or original['instructions'] != current['instructions']
                        or checker_extraction_skill(original['input']['checker_skill']) != checker_extraction_skill(current['input']['checker_skill'])
                        or original['output_contract'] != current['output_contract']
                        or original['input'].get('execution_versions') != packet_versions('interaction-checker')):
                    raise ValueError('retained checker source, extraction rules or taxonomy changed')
        write_json(target/'manifest.json', source_manifest)
        for old in source_manifest['batches']:
            destination = target/'packets'/(old['batch_id']+'.json')
            write_json(destination, read_json(source/'packets'/destination.name))
    else:
        batches.checker_packets(base, index, target)
    baseline, review, old, new = verify_baseline(directory, target, index)
    snapshot = root / "checker_baseline_snapshot"
    for name in ("existing_scenarios.json", "baseline_review.json"):
        write_json(snapshot / name, read_json(directory / name))
    source = directory / "batches" / "interaction-checker"
    proof = snapshot / "batches" / "interaction-checker"
    write_json(proof / "manifest.json", read_json(source / "manifest.json"))
    for original, current in zip(old, new):
        for kind in ("packets", "results"):
            destination = proof / kind / (original["batch_id"] + ".json")
            destination.parent.mkdir(parents=True, exist_ok=True)
            original_path = source / kind / destination.name
            shutil.copyfile(original_path, destination)
            if kind == "results":
                copy_execution_sidecars(read_json(original_path), original_path, destination)
        result = read_json(source / "results" / (original["batch_id"] + ".json"))
        result["baseline_execution"] = {"batch_id": original["batch_id"], "input_hash": original["input_hash"], "model": result["model"], "baseline_hash": baseline["baseline_hash"]}
        result.update(batch_id=current["batch_id"], input_hash=current["input_hash"])
        write_json(target / "results" / (current["batch_id"] + ".json"), result)
    source_audit = directory / "batches/interaction-checker-audit"
    for destination_root in (snapshot / "batches/interaction-checker-audit", root / "batches/interaction-checker-audit"):
        for name in ("manifest.json",):
            write_json(destination_root / name, read_json(source_audit / name))
        for kind in ("packets", "results"):
            for path in (source_audit / kind).glob("*.json"):
                destination = destination_root / kind / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
                if kind == "results":
                    copy_execution_sidecars(read_json(path), path, destination)
    return {"baseline_hash": baseline["baseline_hash"], "source_hash": baseline["source_hash"], "reviewer": review["reviewer"], "snapshot": "checker_baseline_snapshot",
            'retained_source_packets': retain_source_packets}


def verify_import(root, index):
    root = Path(root)
    baseline, _, old, new = verify_baseline(root / "checker_baseline_snapshot", root / "batches" / "interaction-checker", index)
    for original, current in zip(old, new):
        source = read_json(root / "checker_baseline_snapshot/batches/interaction-checker/results" / (original["batch_id"] + ".json"))
        imported = read_json(root / "batches/interaction-checker/results" / (current["batch_id"] + ".json"))
        proof = imported.pop("baseline_execution", None)
        imported.update(batch_id=original["batch_id"], input_hash=original["input_hash"])
        if imported != source or proof != {"batch_id": original["batch_id"], "input_hash": original["input_hash"], "model": source["model"], "baseline_hash": baseline["baseline_hash"]}:
            raise ValueError("imported checker result differs from frozen direct execution proof")
    return baseline
