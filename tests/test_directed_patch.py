"""Offline tests for source-bound directed G-generation patching."""
from __future__ import annotations

import copy

import pytest

from scene_completion.directed_patch import apply_generation_patch
from scene_completion.semantic_backend import prepare_packets, read_json, write_json
from scene_completion.sources import fingerprint


def _scene(name, trigger):
    return {"name": name, "exception_object": "商品草稿", "operation": "写入商品草稿",
        "failure_mechanism": "字段不合法", "trigger_condition": trigger,
        "necessary_conditions": [], "pending_details": [], "source_refs": []}


def _validator(packet, result):
    mounts = {mount["mount_id"] for mount in packet["input"]["mounts"]}
    items = result.get("items")
    if not isinstance(items, list) or {item.get("mount_id") for item in items} != mounts:
        raise ValueError("each generation mount must occur exactly once")
    output = []
    for item in items:
        if not isinstance(item.get("scenarios"), list) or not item["scenarios"]:
            raise ValueError("each mount must retain at least one scenario")
        for scenario in item["scenarios"]:
            if not all(scenario.get(field) for field in
                    ("name", "exception_object", "operation", "failure_mechanism", "trigger_condition")):
                raise ValueError("replacement lacks a complete generation identification")
            output.append({"scenario_id": f"G::{item['mount_id']}::{scenario['name']}::{scenario['trigger_condition']}",
                "mount_id": item['mount_id']})
    return output


def _source(tmp_path):
    source = tmp_path / "source"
    source_input = {"protocol": "fixture", "mounts": [{"mount_id": "M-1", "exchange_id": "X-1"}, {"mount_id": "M-2", "exchange_id": "X-1"}],
        "exchanges": [{"exchange_id": "X-1"}], "nodes": [{"node_id": "N-1"}]}
    manifest = prepare_packets(source, "gap-generation", [source_input], [], {"items": []})
    batch = manifest["batches"][0]
    packet_path = source / "packets" / f"{batch['batch_id']}.json"
    result = {"batch_id": batch["batch_id"], "input_hash": batch["input_hash"], "model": "fixture-model",
        "execution_model_evidence": {"requested_model": "fixture-model", "thinking": False},
        "items": [{"mount_id": "M-1", "scenarios": [_scene("rejected", "原触发"), _scene("keep-1", "保持原样")]},
            {"mount_id": "M-2", "scenarios": [_scene("keep-2", "另一个挂载保持原样")] }]}
    result_path = source / "results" / f"{batch['batch_id']}.json"
    write_json(result_path, result)
    return source, packet_path, result_path, read_json(packet_path), result


def _patch_packet(tmp_path, source, packet_path, result_path, prior_packet, prior_result,
        rejected_ids=None, **extra_input):
    patch_dir = tmp_path / "patch"
    patch_input = copy.deepcopy(prior_packet["input"])
    patch_input.update(extra_input)
    patch_input["directed_patch"] = {
        "prior_execution": {"result_path": str(result_path), "result_hash": fingerprint(prior_result),
            "packet_path": str(packet_path), "packet_hash": fingerprint(prior_packet)},
        "rejected_scenario_ids": rejected_ids or ["G::M-1::rejected::原触发"],
    }
    patch_manifest = prepare_packets(patch_dir, "gap-generation", [patch_input], [], {"replacements": []})
    patch_batch = patch_manifest["batches"][0]
    patch_packet = read_json(patch_dir / "packets" / f"{patch_batch['batch_id']}.json")
    return patch_packet, patch_batch


def _patch_raw(batch, replacements):
    return {"batch_id": batch["batch_id"], "input_hash": batch["input_hash"],
        "model": "fixture-model", "execution_model_evidence": {"requested_model": "fixture-model", "thinking": False},
        "replacements": replacements}


def test_patch_replaces_only_rejected_raw_scenario_and_preserves_original_proof(tmp_path):
    source, packet_path, result_path, prior_packet, prior_result = _source(tmp_path)
    original_bytes = result_path.read_bytes()
    patch_packet, batch = _patch_packet(tmp_path, source, packet_path, result_path, prior_packet, prior_result)
    response = _patch_raw(batch, [{"source_scenario_id": "G::M-1::rejected::原触发",
        "scenarios": [_scene("repaired", "修复后的具体触发")]}])

    returned_packet, merged = apply_generation_patch(patch_packet, response, base_validator=_validator)

    assert returned_packet == prior_packet
    assert merged["execution_model_evidence"] == prior_result["execution_model_evidence"]
    assert merged["model"] == prior_result["model"]
    assert merged["items"][0]["scenarios"] == [_scene("repaired", "修复后的具体触发"), prior_result["items"][0]["scenarios"][1]]
    assert merged["items"][1] == prior_result["items"][1]
    assert result_path.read_bytes() == original_bytes
    assert "passed" not in merged and "valid" not in merged


@pytest.mark.parametrize("replacements", [
    [{"source_scenario_id": "G::M-1::rejected::原触发", "scenarios": [_scene("a", "x")]},
     {"source_scenario_id": "G::M-1::rejected::原触发", "scenarios": [_scene("b", "y")]}],
    [{"source_scenario_id": "not-a-source-G-id", "scenarios": [_scene("a", "x")]}],
])
def test_patch_requires_every_rejected_id_exactly_once_and_no_other_ids(tmp_path, replacements):
    source, packet_path, result_path, prior_packet, prior_result = _source(tmp_path)
    patch_packet, batch = _patch_packet(tmp_path, source, packet_path, result_path, prior_packet, prior_result)
    with pytest.raises(ValueError, match="exactly once"):
        apply_generation_patch(patch_packet, _patch_raw(batch, replacements), _validator)


def test_patch_rejects_tampered_prior_packet_hash(tmp_path):
    source, packet_path, result_path, prior_packet, prior_result = _source(tmp_path)
    packet = read_json(packet_path)
    packet["input"]["mounts"][0]["mount_id"] = "TAMPERED"
    write_json(packet_path, packet)
    patch_packet, batch = _patch_packet(tmp_path, source, packet_path, result_path, prior_packet, prior_result)
    response = _patch_raw(batch, [{"source_scenario_id": "G::M-1::rejected::原触发",
        "scenarios": [_scene("repaired", "触发")]}])
    with pytest.raises(ValueError, match="prior packet hash"):
        apply_generation_patch(patch_packet, response, _validator)


def test_multiple_rejections_on_one_mount_keep_original_offsets_and_middle_success(tmp_path):
    source, packet_path, result_path, prior_packet, prior_result = _source(tmp_path)
    prior_result["items"][0]["scenarios"] = [
        _scene("rejected-a", "第一个原触发"),
        _scene("keep-middle", "必须保留在中间的成功项"),
        _scene("rejected-b", "第二个原触发"),
        _scene("keep-last", "末尾成功项"),
    ]
    write_json(result_path, prior_result)
    id_a = "G::M-1::rejected-a::第一个原触发"
    id_b = "G::M-1::rejected-b::第二个原触发"
    patch_packet, batch = _patch_packet(tmp_path, source, packet_path, result_path,
        prior_packet, prior_result, rejected_ids=[id_a, id_b])
    response = _patch_raw(batch, [
        {"source_scenario_id": id_a, "scenarios": [
            _scene("replacement-a1", "拆分触发一"), _scene("replacement-a2", "拆分触发二")]},
        {"source_scenario_id": id_b, "scenarios": [_scene("replacement-b", "替换触发") ]},
    ])

    _, merged = apply_generation_patch(patch_packet, response, _validator)

    assert merged["items"][0]["scenarios"] == [
        _scene("replacement-a1", "拆分触发一"), _scene("replacement-a2", "拆分触发二"),
        _scene("keep-middle", "必须保留在中间的成功项"),
        _scene("replacement-b", "替换触发"), _scene("keep-last", "末尾成功项")]


def test_empty_replacement_scenarios_are_rejected(tmp_path):
    source, packet_path, result_path, prior_packet, prior_result = _source(tmp_path)
    patch_packet, batch = _patch_packet(tmp_path, source, packet_path, result_path, prior_packet, prior_result)
    response = _patch_raw(batch, [{"source_scenario_id": "G::M-1::rejected::原触发", "scenarios": []}])

    with pytest.raises(ValueError, match="one or more complete replacement scenarios"):
        apply_generation_patch(patch_packet, response, _validator)


def test_patch_packet_cannot_include_checker_or_test_evidence(tmp_path):
    source, packet_path, result_path, prior_packet, prior_result = _source(tmp_path)
    patch_packet, batch = _patch_packet(tmp_path, source, packet_path, result_path, prior_packet, prior_result,
        test_scenarios=[{"id": "T-1"}])
    response = _patch_raw(batch, [{"source_scenario_id": "G::M-1::rejected::原触发",
        "scenarios": [_scene("repaired", "触发")]}])
    with pytest.raises(ValueError, match="checker or E/T"):
        apply_generation_patch(patch_packet, response, _validator)

def test_repair_resolves_generated_ids_absent_from_raw_and_preserves_success(tmp_path):
    from scene_completion.concern_gap_dag import Packets
    source, packet_path, result_path, prior_packet, prior_result = _source(tmp_path)
    runtime = object.__new__(Packets)
    captured = []
    def validate(packet, raw):
        if packet['input'].get('directed_patch'):
            original, merged = apply_generation_patch(packet, raw, _validator)
            return _validator(original, merged)
        return _validator(packet, raw)
    def execute(folder, validator):
        manifest = read_json(folder/'manifest.json')
        assert len(manifest['batches']) == 1
        batch = manifest['batches'][0]
        packet = read_json(folder/'packets'/(batch['batch_id']+'.json'))
        captured.append(packet)
        response = _patch_raw(batch, [{'source_scenario_id':'G::M-1::rejected::原触发',
            'scenarios':[_scene('repaired','具体单一原因')]}])
        return {'values':validator(packet,response)}
    runtime.execute = execute
    result = runtime.repaired(tmp_path,'source-fix',{'folder':str(source)},validate,
        {'action':'repair'}, {'findings':[{'source_scenario_id':'G::M-1::rejected::原触发'}]},1)
    assert captured[0]['input']['directed_patch']['rejected_scenario_ids'] == ['G::M-1::rejected::原触发']
    assert len(result['values']) == 3
    assert any(row['scenario_id']=='G::M-2::keep-2::另一个挂载保持原样' for row in result['values'])


def test_source_repair_rejects_noop_even_when_a_new_review_would_pass():
    from scene_completion.directed_patch import validate_generation_progress
    rows=[{'scenario_id':'G-bad'},{'scenario_id':'G-good'}]
    with pytest.raises(ValueError,match='unchanged'):
        validate_generation_progress(rows,rows,['G-bad'])
    validate_generation_progress(rows,[{'scenario_id':'G-fixed'},rows[1]],['G-bad'])
    with pytest.raises(ValueError,match='requires unique'):
        validate_generation_progress(None,rows,[])
