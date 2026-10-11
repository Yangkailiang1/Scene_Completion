"""Regressions for review findings, atomic identities and resumable execution."""
import copy

import pytest

from tests.test_interaction_protocol import model, scene, reference, pair
from scene_completion.interaction_protocol import build_ssd, route_mounts
from scene_completion.interaction_batches import checker_validator, generation_validator, pair_validator, test_validator as acceptance_test_validator
from scene_completion.semantic_backend import prepare_packets, run_agent_packets, collect_packets, write_json, read_json
from scene_completion.sources import index_sources


@pytest.fixture
def index(tmp_path):
    path = tmp_path / "rr.md"
    path.write_text("# Requirements\n## UC-1\n异常条件\n", encoding="utf-8")
    value = index_sources([str(path)])
    value["documents"][0]["requirement_layer"] = "RR"
    return value


@pytest.mark.parametrize("change", ["human_receiver", "external_ui", "reversed_rr", "non_service_sr", "missing_sr_layer", "missing_parent_sr"])
def test_wrong_graph_endpoint_shapes_rejected(index, change):
    value = model(index)
    if change == "human_receiver":
        value["nodes"][1]["boundary_role"] = "receiver"
    elif change == "external_ui":
        value["nodes"][0]["kind"] = "external_service"
    elif change == "reversed_rr":
        value["use_cases"][0]["exchanges"][0].update(from_node="ui", to_node="actor")
    elif change == "non_service_sr":
        value["nodes"][2]["kind"] = "human_actor"
    elif change == "missing_sr_layer":
        value["nodes"][2].pop("layer")
    elif change == "missing_parent_sr":
        value["use_cases"][0]["exchanges"][2].pop("parent_sr_local_id")
    with pytest.raises(ValueError):
        build_ssd(value)


def test_nested_return_order_is_inside_rr_response(index):
    ssd = build_ssd(model(index))
    exchanges = ssd["exchanges"]
    messages = ssd["fused_message_ids"]
    rr, parent, child = exchanges[:3]
    assert messages.index(rr["message_ids"][0]) < messages.index(parent["message_ids"][0])
    assert messages.index(child["message_ids"][1]) < messages.index(parent["message_ids"][1]) < messages.index(rr["message_ids"][1])


def test_reused_facade_has_all_database_concerns(index):
    value = model(index)
    value["nodes"].append({"node_id": "facade", "name": "existing", "kind": "internal_service", "physical_resource_id": "db"})
    ssd = build_ssd(value)
    facade = next(n for n in ssd["nodes"] if n["node_id"] == "facade")
    assert facade["layer"] == "SR" and facade["service_role"] == "resource_service"
    keys = {m["concern_key"] for m in route_mounts(ssd) if m["subject_node_id"] == "facade"}
    assert sum(k.startswith("internal_database.") for k in keys) == 10


@pytest.mark.parametrize("bad", [{"layer": "AR"}, {"resource_origin": "external"}, {"service_role": "ordinary_service"}, {"kind": "external_service"}])
def test_incompatible_existing_facade_rejected(index, bad):
    value = model(index)
    value["nodes"].append({"node_id": "facade", "name": "existing", "kind": "internal_service", "physical_resource_id": "db", **bad})
    with pytest.raises(ValueError, match="incompatible"):
        build_ssd(value)


def test_checker_necessary_conditions_form_distinct_atomic_ids(index):
    sections = [index["documents"][0]["chapters"][-1]]
    packet = {"input": {"sections": sections, "requirement_layer": "RR", "use_case_id": "UC-1"}}
    first = {**scene("C"), "source_refs": reference(index), "necessary_conditions": ["属于商家A"]}
    second = {**first, "necessary_conditions": ["属于商家B"]}
    result = {"covered_section_ids": [sections[0]["chapter_id"]], "scenarios": [first, second]}
    values = checker_validator(index)(packet, result)
    assert len({s["scenario_id"] for s in values}) == 2


def test_generation_necessary_conditions_form_distinct_ids(index):
    ssd = build_ssd(model(index))
    mount = route_mounts(ssd)[0]
    exchange = next(e for e in ssd["exchanges"] if e["exchange_id"] == mount["exchange_id"])
    packet = {"input": {"mounts": [mount], "exchanges": [exchange]}}
    a = {**scene("G"), "source_refs": reference(index), "necessary_conditions": ["归属A"]}
    b = {**a, "necessary_conditions": ["归属B"]}
    values = generation_validator(index)(packet, {"items": [{"mount_id": mount["mount_id"], "scenarios": [a, b]}]})
    assert len({s["scenario_id"] for s in values}) == 2


def test_match_cannot_use_operation_as_failure_evidence():
    packet = {"input": {"generated": [scene("G")], "checker": [scene("C")]}}
    item = pair("C", "G")
    item["identification_evidence"]["failure_mechanism"]["checker"] = "查询商品"
    with pytest.raises(ValueError, match="field-specific"):
        pair_validator(packet, {"pairs": [item]})


def test_test_optional_abnormal_conditions_allowed_normal_not_allowed(index):
    ref = reference(index)
    def packet(kind):
        return {"input": {"records": [{"test_scenario_id": "T1", "scenario_type": kind, "requirements": "UC-1", "source_refs": ref}], "valid_use_case_ids": ["UC-1"]}}
    a = {**scene("T"), "source_refs": ref, "concern_key": "service.query_retrieval.resource_existence", "interaction_location": "查询商品", "source_basis": "explicit", "original_condition_quote": "异常条件"}
    b = {**a, "operation": "删除商品", "necessary_conditions": ["已删除过"]}
    result = {"items": [{"test_scenario_id": "T1", "conditions": [a, b]}]}
    values = acceptance_test_validator(index)(packet("optional"), result)
    assert len({s["scenario_id"] for s in values}) == 2
    assert all(s["requirement_layer"] == 'TEST' for s in values)
    with pytest.raises(ValueError, match="ordinary normal"):
        acceptance_test_validator(index)(packet("normal"), result)


def test_resume_rejects_wrong_model_and_reuses_complete_actual_batch(tmp_path):
    manifest = prepare_packets(tmp_path, "interaction-test-fixture", [{"value": 1}], [], {"items": []})
    batch = manifest["batches"][0]
    write_json(tmp_path / "results" / (batch["batch_id"] + ".json"), {**batch, "model": "other", "items": ["wrong"]})
    class Client:
        config = {"max_concurrency": 1}
        calls = 0
        def model(self, kind):
            return "ecnu-max"
        def agent(self, packet):
            self.calls += 1
            return {"items": ["actual"], "execution_model_evidence": {"requested_model": "ecnu-max", "thinking": False, "reasoning_effort": None}}
    client = Client()
    validator = lambda p, r: r["items"]
    assert run_agent_packets(tmp_path, client, validator)["complete"]
    assert client.calls == 1
    assert run_agent_packets(tmp_path, client, validator)["complete"]
    assert client.calls == 1
    values, status = collect_packets(tmp_path, validator)
    assert values == ["actual"] and status["complete"]
    # Changed packet content is invalid even if the old result exists.
    path = tmp_path / "packets" / (batch["batch_id"] + ".json")
    packet = read_json(path)
    packet["input"]["value"] = 2
    write_json(path, packet)
    assert not collect_packets(tmp_path, validator)[1]["complete"]
