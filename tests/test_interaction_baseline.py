"""C stays fixed without masking source or extraction changes."""
import copy

import pytest

from scene_completion import interaction_batches as batches
from scene_completion.interaction_baseline import import_baseline, verify_import
from scene_completion.interaction_protocol import PROTOCOL
from scene_completion.semantic_backend import read_json, write_json, collect_packets
from scene_completion.sources import index_sources, fingerprint
from tests.test_interaction_protocol import scene


def original(tmp_path):
    paths = []
    for layer in ("RR", "SR"):
        path = tmp_path / (layer + ".md")
        path.write_text("# " + layer + "\n## UC-1\n异常条件\n", encoding="utf-8")
        paths.append(str(path))
    index = index_sources(paths)
    for document, layer in zip(index["documents"], ("RR", "SR")):
        document["requirement_layer"] = layer
    base = {"use_cases": [{"use_case_id": "UC-1", "use_case_name": "查询"}]}
    root = tmp_path / "original"
    folder = root / "batches/interaction-checker"
    manifest = batches.checker_packets(base, index, folder)
    for batch in manifest["batches"]:
        packet = read_json(folder / "packets" / (batch["batch_id"] + ".json"))
        layer = packet["input"]["requirement_layer"]
        value = {**scene("C", layer), "layer_use_case_id": "UC-1", "source_refs": [{"document": layer + ".md", "line_start": 3, "line_end": 3}]}
        value.update(extraction_basis="explicit_named", failure_source_refs=value["source_refs"], contract_source_refs=[])
        write_json(folder / "results" / (batch["batch_id"] + ".json"), {**batch, "model": "ecnu-max", "execution_model_evidence": {"requested_model": "ecnu-max", "provider_model": None}, "covered_section_ids": [s["chapter_id"] for s in packet["input"]["sections"]], "scenarios": [value]})
    rows, status = collect_packets(folder, batches.checker_validator(index))
    assert status["complete"]
    # Mocked semantic audit evidence exercises provenance and import guards;
    # these fixtures do not assert real ECNU semantic correctness.
    from scene_completion.interaction_audit import checker_audit_packets, checker_audit_proof_hash
    audit_folder = root / 'batches/interaction-checker-audit'
    audit_manifest = checker_audit_packets(folder, index, audit_folder)
    for batch in audit_manifest['batches']:
        packet = read_json(audit_folder / 'packets' / (batch['batch_id'] + '.json'))
        reviews = [{'scenario_id': s['scenario_id'], 'source_supported': True, 'atomic': True,
            'operation_binding_supported': True, 'citation_accurate': True, 'evidence_quote': '异常条件',
            'source_refs': s['failure_source_refs'], 'issues': []} for s in packet['input']['scenarios']]
        write_json(audit_folder / 'results' / (batch['batch_id'] + '.json'), {**batch, 'model': 'ecnu-max',
            'execution_model_evidence': {'requested_model': 'ecnu-max'},
            'covered_section_ids': [s['chapter_id'] for s in packet['input']['sections']], 'reviews': reviews, 'omitted_conditions': []})
    baseline = {"protocol": PROTOCOL, "complete": True, "source_hash": fingerprint(index), "scenarios": rows, "baseline_hash": fingerprint(rows)}
    write_json(root / "existing_scenarios.json", baseline)
    evidence_hash = fingerprint([{ "batch_id": b["batch_id"], "evidence": read_json(folder / "results" / (b["batch_id"] + ".json"))["execution_model_evidence"]} for b in manifest["batches"]])
    write_json(root / "baseline_review.json", {"passed": True, "reviewer": "fixture source review", "source_hash": baseline["source_hash"], "baseline_hash": baseline["baseline_hash"], "execution_evidence_hash": evidence_hash, 'source_audit_hash': checker_audit_proof_hash(root), "unresolved_findings": []})
    return root, index, base, baseline


def test_fixed_baseline_import_is_offline_and_auditable(tmp_path):
    root, index, base, baseline = original(tmp_path)
    target = tmp_path / "next_round"
    result = import_baseline(root / "existing_scenarios.json", target, index, base)
    assert result["baseline_hash"] == baseline["baseline_hash"]
    assert verify_import(target, index) == baseline
    # Source round can be absent; all direct-execution evidence is copied locally.
    saved = next((target / "batches/interaction-checker/results").glob("*.json"))
    value = read_json(saved)
    value["scenarios"][0]["trigger_condition"] = "伪造条件"
    write_json(saved, value)
    with pytest.raises(ValueError, match="differs"):
        verify_import(target, index)


def test_baseline_review_is_recorded_from_complete_current_source_proof(tmp_path):
    from scene_completion.interaction_baseline import record_source_review
    root, index, _, fixed = original(tmp_path)
    review = record_source_review(root, index)
    assert review['passed'] and review['baseline_hash'] == fixed['baseline_hash']
    assert review['reviewed_batches'] == 2
    assert read_json(root / 'baseline_review.json') == review
    fixed['scenarios'][0]['trigger_condition'] = 'altered condition'
    write_json(root / 'existing_scenarios.json', fixed)
    with pytest.raises(ValueError, match='altered/incomplete'):
        record_source_review(root, index)


def test_checker_code_version_change_blocks_reuse(tmp_path, monkeypatch):
    root, index, base, _ = original(tmp_path)
    monkeypatch.setattr(batches, "checker_extraction_version", lambda: "changed-identification-rules")
    with pytest.raises(ValueError, match="extraction rules"):
        import_baseline(root / "existing_scenarios.json", tmp_path / "next", index, base)


@pytest.mark.parametrize("change", ["source", "rules", "review", "incomplete", "model"])
def test_baseline_invalidations_are_explicit(tmp_path, change):
    root, index, base, baseline = original(tmp_path)
    if change == "source":
        index = copy.deepcopy(index)
        index["documents"][0]["text"] += "\n改变的原文"
    elif change == "review":
        review = read_json(root / "baseline_review.json")
        review["passed"] = False
        write_json(root / "baseline_review.json", review)
    else:
        folder = root / "batches/interaction-checker"
        bid = read_json(folder / "manifest.json")["batches"][0]["batch_id"]
        path = folder / "results" / (bid + ".json")
        if change == "incomplete":
            path.unlink()
        elif change == "model":
            value = read_json(path)
            value["model"] = "other-model"
            write_json(path, value)
        else:
            path = folder / "packets" / (bid + ".json")
            value = read_json(path)
            value["instructions"] += ["不同抽取规则"]
            write_json(path, value)
    with pytest.raises(ValueError):
        import_baseline(root / "existing_scenarios.json", tmp_path / "next", index, base)
