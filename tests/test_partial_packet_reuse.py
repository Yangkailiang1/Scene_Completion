"""Offline tests for exact, individually validated packet reuse."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from scene_completion.case_dag import CallGate, TaskRejected
from scene_completion.concern_gap_dag import Packets
from scene_completion.partial_packet_reuse import semantic_packet
from scene_completion.partial_packet_reuse import reuse_from
from scene_completion.semantic_backend import prepare_packets, read_json, write_json


def _prepare(folder: Path, payloads):
    return prepare_packets(folder, "gap-recheck-fixture", payloads, ["instruction"], {"items": []})


def _result(folder: Path, batch, *, items=None):
    raw = {"batch_id": batch["batch_id"], "input_hash": batch["input_hash"],
        "model": "fixture-model", "execution_model_evidence": {"requested_model": "fixture-model"},
        "items": [] if items is None else items}
    write_json(folder / "results" / f"{batch['batch_id']}.json", raw)
    return raw


def test_valid_inverse_check_rejection_is_preserved_instead_of_rerolled(tmp_path):
    source, destination = tmp_path / 'source', tmp_path / 'destination'
    stage = 'gap-reverse-check-T'
    old = prepare_packets(source, stage, [{'value': 1, 'execution_versions': {'v': 1}}],
        ['check'], {'items': []})
    raw = _result(source, old['batches'][0], items=[{'passed': False, 'reason': 'real source defect'}])
    prepare_packets(destination, stage, [{'value': 1, 'execution_versions': {'v': 2}}],
        ['check'], {'items': []})
    outcome = reuse_from(source, destination, lambda p, r: r['items'], lambda r: None)
    assert outcome['reused_batch_ids'] == [old['batches'][0]['batch_id']]
    copied = read_json(destination / 'results' / (old['batches'][0]['batch_id'] + '.json'))
    assert copied == raw and copied['items'][0]['passed'] is False


def test_reuses_unchanged_packet_and_leaves_only_changed_packet_pending(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    old_manifest = _prepare(source, [
        {"value": "unchanged", "execution_versions": {"validator": "old"}},
        {"value": "old-value", "execution_versions": {"validator": "old"}},
    ])
    original = _result(source, old_manifest["batches"][0], items=[{"id": "kept"}])
    _result(source, old_manifest["batches"][1], items=[{"id": "changed"}])
    original_bytes = (source / "results" / f"{old_manifest['batches'][0]['batch_id']}.json").read_bytes()

    new_manifest = _prepare(destination, [
        {"value": "unchanged", "execution_versions": {"validator": "new"}},
        {"value": "new-value", "execution_versions": {"validator": "new"}},
    ])
    outcome = reuse_from(source, destination, lambda _p, result: result["items"], lambda _raw: None)

    reused_id = old_manifest["batches"][0]["batch_id"]
    remaining_id = new_manifest["batches"][1]["batch_id"]
    assert outcome["reused_batch_ids"] == [reused_id]
    assert outcome["pending_batch_ids"] == [remaining_id]
    assert (destination / "results" / f"{remaining_id}.json").exists() is False
    assert (destination / "results" / f"{reused_id}.json").read_bytes() == original_bytes
    assert read_json(destination / "results" / f"{reused_id}.json") == original
    assert read_json(destination / "manifest.json")["batches"][0] == old_manifest["batches"][0]
    assert outcome["proofs"][0]["model"] == "fixture-model"


def test_does_not_reuse_source_with_any_rejected_review(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    payload = {"value": 1, "execution_versions": {"validator": "old"}}
    old_manifest = _prepare(source, [payload])
    _result(source, old_manifest["batches"][0], items=[{"value": "good"}])
    _prepare(destination, [{"value": 1, "execution_versions": {"validator": "new"}}])

    outcome = reuse_from(source, destination,
        lambda _p, _r: {"reviews": [{"passed": True}, {"passed": False}]}, lambda _raw: None)

    assert outcome["reused_batch_ids"] == []
    assert len(outcome["pending_batch_ids"]) == 1
    assert "explicit rejected" in outcome["rejected"][0]["reason"]


def test_tampered_source_packet_hash_is_not_reused(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    old_manifest = _prepare(source, [{"value": 1, "execution_versions": {"validator": "old"}}])
    batch = old_manifest["batches"][0]
    _result(source, batch)
    source_result_path = source / "results" / f"{batch['batch_id']}.json"
    original_result_bytes = source_result_path.read_bytes()
    packet_path = source / "packets" / f"{batch['batch_id']}.json"
    packet = read_json(packet_path)
    packet["input"]["value"] = "tampered"
    write_json(packet_path, packet)
    _prepare(destination, [{"value": 1, "execution_versions": {"validator": "new"}}])

    outcome = reuse_from(source, destination, lambda _p, result: result["items"], lambda _raw: None)

    assert outcome["reused_batch_ids"] == []
    assert len(outcome["pending_batch_ids"]) == 1
    assert hashlib.sha256(source_result_path.read_bytes()).digest() == hashlib.sha256(original_result_bytes).digest()
    assert read_json(destination / "manifest.json")["batches"][0] != batch


def test_partial_success_keeps_original_identity_across_execution_metadata_change(tmp_path):
    calls = []
    class Client:
        config = {"thinking": False, "model_preflight": "off"}
        def model(self, kind): return "fixture"
        def agent(self, packet):
            number = packet["input"]["number"]
            calls.append(number)
            return {"items": [number] if number == 1 or calls.count(2) > 1 else "bad",
                "execution_model_evidence": {"requested_model": "fixture", "thinking": False, "reasoning_effort": None}}
    packets = Packets(tmp_path, SimpleNamespace(agent_mode="external", reuse_run=None), Client(), CallGate(1))
    def check(packet, raw):
        if not isinstance(raw["items"], list): raise ValueError("wrong shape")
        return raw["items"]
    def prepare(version, prose):
        return lambda folder: prepare_packets(folder, "gap-fixture",
            [{"number": n, "execution_versions": version,
              "skill": "---\nname: scene-concern-gap\n---\n\n生成原子异常\n\n批量无法完成时" + prose}
             for n in (1, 2)], ["unchanged actual generation instruction"], {"items": []})
    folder = packets.prepare(tmp_path, "G", prepare(1, "自动接手一次"), check)
    with pytest.raises(TaskRejected): packets.execute(folder, check)
    original = read_json(folder / "manifest.json")["batches"][0]
    raw = (folder / "results" / (original["batch_id"] + ".json")).read_bytes()
    folder = packets.prepare(tmp_path, "G", prepare(2, "主控持续处理"), check)
    assert packets.execute(folder, check)["values"] == [1, 2]
    assert calls == [1, 2, 2]
    assert read_json(folder / "manifest.json")["batches"][0] == original
    assert (folder / "results" / (original["batch_id"] + ".json")).read_bytes() == raw


@pytest.mark.parametrize("field", ["instructions", "source", "output_contract"])
def test_semantic_input_or_contract_changes_cannot_reuse_partial_packets(field):
    old = {"stage": "gap-generation", "input": {"source": "original", "execution_versions": 1},
        "instructions": ["preserve semantics"], "output_contract": {"items": []}}
    import copy
    new = copy.deepcopy(old)
    if field == "source": new["input"][field] = "different source"
    else: new[field] = ["different meaning"]
    assert semantic_packet(new) != semantic_packet(old)
