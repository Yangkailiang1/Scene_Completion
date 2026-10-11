"""SSD operation traits prevent an unrelated write from being invented on a read."""
import copy

import pytest

from scene_completion.interaction_protocol import route_mounts, baseline, validate_exchange_fields
from scene_completion.interaction_reports import coverage_diagnosis
from scene_completion.semantic_backend import SemanticClient, prepare_packets, run_agent_packets, read_json
from scene_completion.interaction_batches import checker_validator
from scene_completion.interaction_protocol import PROTOCOL
from scene_completion.sources import index_sources


def ssd(kinds, relations=None):
    return {"nodes": [
        {"node_id": "caller", "kind": "internal_service", "layer": "SR", "name": "目录服务", "service_types": ["query_retrieval", "resource_mutation"]},
        {"node_id": "db", "kind": "internal_service", "layer": "SR", "name": "商品资源服务", "service_role": "resource_service", "resource_origin": "internal"}],
        "exchanges": [{"exchange_id": "e", "requirement_layer": "SR", "use_case_id": "R", "layer_use_case_id": "S-read",
            "from_node": "caller", "to_node": "db", "operation_kinds": kinds, "data_relations": relations or [],
            "request_fields": ["productId"], "response_fields": ["name"], "message_ids": ["req", "ret"], "source_refs": []}]}


def test_read_does_not_inherit_writes_or_unproven_relations():
    keys = {m["concern_key"] for m in route_mounts(ssd(["read"]))}
    assert {"internal_database.availability", "internal_database.query_performance", "internal_database.resource_existence"} <= keys
    assert not keys & {"internal_database.persistence", "internal_database.uniqueness", "internal_database.referential_consistency",
        "internal_database.idempotency", "internal_database.concurrency_consistency", "service_relation.cascade_operation",
        "service_relation.idempotency", "service_relation.cross_service_consistency", "service_relation.concurrency_consistency"}
    assert not any(k.startswith("service.resource_mutation.") for k in keys)
    assert sum(k.startswith("internal_database.") for k in baseline()) == 10


@pytest.mark.parametrize('layer,boundary', [('RR', 'ui'), ('SR', 'ui'), ('SR', 'receiver')])
def test_five_functional_categories_never_mount_on_ui_or_receiving_boundary(layer, boundary):
    value = ssd(['read', 'display', 'update', 'process', 'publish'])
    # Contaminated extraction metadata cannot widen the authorized concern scope.
    value['nodes'][0].update(layer='RR', kind='frontend_ui', boundary_role=boundary,
        service_types=['display_interaction', 'query_retrieval', 'resource_mutation', 'analysis_generation', 'release_activation'])
    if layer == 'RR':
        value['exchanges'][0]['requirement_layer'] = 'RR'
    mounted = route_mounts(value)
    functional_prefixes = tuple('service.' + category + '.' for category in
        ('display_interaction', 'query_retrieval', 'resource_mutation', 'analysis_generation', 'release_activation'))
    assert not any(m['subject_node_id'] == 'caller' and m['concern_key'].startswith(functional_prefixes) for m in mounted)
    assert any(m['concern_key'].startswith('api.data.') for m in mounted)
    value['nodes'][0].update(layer='SR', kind='internal_service')
    value['nodes'][0].pop('boundary_role')
    value['exchanges'][0]['requirement_layer'] = 'SR'
    assert any(m['concern_key'].startswith('service.query_retrieval.') for m in route_mounts(value))


def test_source_backed_delete_cascade_and_update_mounts_remain():
    relation = {"object": "商品子项", "relation": "cascade", "source_refs": []}
    keys = {m["concern_key"] for m in route_mounts(ssd(["delete"], [relation]))}
    assert {"internal_database.persistence", "internal_database.idempotency", "internal_database.referential_consistency",
        "service_relation.cascade_operation", "service_relation.cross_service_consistency"} <= keys
    assert "internal_database.query_performance" not in keys
    assert "internal_database.uniqueness" in {m["concern_key"] for m in route_mounts(ssd(["update"]))}


@pytest.mark.parametrize("boundary,expected", [("ui", {"human.authentication", "human.authorization"}),
    ("receiver", {"external_service.identity", "external_service.permission"}), (None, set())])
def test_sr_identity_routes_by_real_caller_boundary(boundary, expected):
    value = ssd(["read"])
    caller = value["nodes"][0]
    if boundary:
        caller["boundary_role"] = boundary
    value["exchanges"][0]["identity_contract"] = "凭证契约"
    keys = {m["concern_key"] for m in route_mounts(value)}
    identity = {"human.authentication", "human.authorization", "external_service.identity", "external_service.permission"}
    assert keys & identity == expected


def test_llm_permission_is_incoming_only_and_receiver_preserves_actor():
    value = ssd(["process"])
    value["nodes"] += [{"node_id": "llm", "kind": "external_llm", "layer": "RR"},
        {"node_id": "receiver", "kind": "abstract_service", "layer": "RR", "boundary_role": "receiver"}]
    value["exchanges"][0].update(from_node="receiver", parent_exchange_id="rr", identity_contract="调用方合法凭证")
    rr = {**value["exchanges"][0], "exchange_id": "rr", "requirement_layer": "RR", "from_node": "llm", "to_node": "receiver"}
    value["exchanges"].insert(0, rr)
    mounted = route_mounts(value)
    assert any(m["exchange_id"] == "rr" and m["concern_key"] == "external_llm.access_permission" for m in mounted)
    assert any(m["exchange_id"] == "e" and m["concern_key"] == "external_llm.access_permission" for m in mounted)
    outbound = ssd(["external_call"])
    outbound["nodes"][1] = {"node_id": "db", "kind": "external_llm", "layer": "SR"}
    keys = {m["concern_key"] for m in route_mounts(outbound)}
    assert "external_llm.access_permission" not in keys
    assert len([k for k in keys if k.startswith("external_llm.quality.")]) == 5
    assert {"external_llm.availability", "external_llm.contract"} <= keys


def test_relation_requires_positive_clause_not_just_identifier():
    with pytest.raises(ValueError, match="data relation"):
        validate_exchange_fields({"data_relations": [{"object": "product_id", "relation": "unique_key", "source_refs": []}]})


def test_invalid_normal_operation_trait_rejected():
    with pytest.raises(ValueError, match="operation_kinds"):
        validate_exchange_fields({"operation_kinds": ["invented_write"]})


def test_generic_checker_expansion_needs_both_branch_and_contract_proof(tmp_path):
    path = tmp_path / 'sr.md'
    path.write_text('# SR\n## UC-1\npageSize <= 100\n查询参数非法，例如page<1\n', encoding='utf-8')
    index = index_sources([str(path)])
    index['documents'][0]['requirement_layer'] = 'SR'
    sections = index['documents'][0]['chapters'][1:]
    packet = {'input': {'protocol': PROTOCOL, 'sections': sections, 'requirement_layer': 'SR', 'use_case_id': 'R'}}
    branch = {'document': 'sr.md', 'line_start': 4, 'line_end': 4}
    contract = {'document': 'sr.md', 'line_start': 3, 'line_end': 3}
    scene = {'name': 'pageSize越界', 'layer_use_case_id': 'UC-1', 'exception_object': 'pageSize', 'operation': '查询',
        'failure_mechanism': '超出范围', 'trigger_condition': 'pageSize > 100', 'necessary_conditions': [], 'concern_keys': [],
        'source_refs': [branch, contract], 'extraction_basis': 'generic_failure_contract', 'failure_source_refs': [branch],
        'contract_source_refs': [contract]}
    result = {'covered_section_ids': [s['chapter_id'] for s in sections], 'scenarios': [scene]}
    assert checker_validator(index)(packet, result)[0]['extraction_basis'] == 'generic_failure_contract'
    broken = copy.deepcopy(result)
    broken['scenarios'][0]['contract_source_refs'] = []
    with pytest.raises(ValueError):
        checker_validator(index)(packet, broken)
    broken = copy.deepcopy(result)
    broken['scenarios'][0]['source_refs'] = [branch]
    with pytest.raises(ValueError, match='retain both'):
        checker_validator(index)(packet, broken)


def test_diagnosis_does_not_use_mount_from_another_sr_unit():
    value = ssd(["read"])
    mounts = route_mounts(value)
    checker = {"scenario_id": "C", "requirement_layer": "SR", "use_case_id": "R", "layer_use_case_id": "S-other",
        "source_refs": [], "exception_object": "商品", "operation": "查询", "failure_mechanism": "不存在",
        "trigger_condition": "商品不存在", "concern_keys": ["internal_database.resource_existence"]}
    metrics = {"layers": {"combined": {"overall": {"missed_checker_ids": ["C"]}}}, "assignment": {"selected_pairs": [], "eligible_but_unselected_pairs": []}}
    diagnosis = coverage_diagnosis([], [checker], [], metrics, value, mounts)[0]
    assert diagnosis["relevant_mounts"] == [] and diagnosis["check_components"] == []
    assert "未挂载" in diagnosis["gap_reason"]


def test_checker_cannot_expand_failure_with_another_sr_contract(tmp_path):
    path = tmp_path / 'sr.md'
    path.write_text('# SR\n## SR-A\n参数非法\n正常调用 API-A\n## SR-B\npageSize <= 100\n## API-A\npageSize <= 50\n', encoding='utf-8')
    index = index_sources([str(path)])
    index['documents'][0]['requirement_layer'] = 'SR'
    sections = index['documents'][0]['chapters'][1:]
    packet = {'input': {'protocol': PROTOCOL, 'sections': sections, 'requirement_layer': 'SR', 'use_case_id': 'R'}}
    ref = lambda n: {'document': 'sr.md', 'line_start': n, 'line_end': n}
    scene = {'name': 'pageSize越界', 'layer_use_case_id': 'SR-A', 'exception_object': 'pageSize', 'operation': '查询',
        'failure_mechanism': '超出范围', 'trigger_condition': 'pageSize > 100', 'necessary_conditions': [], 'concern_keys': [],
        'source_refs': [ref(3), ref(6)], 'extraction_basis': 'generic_failure_contract', 'failure_source_refs': [ref(3)],
        'contract_source_refs': [ref(6)]}
    result = {'covered_section_ids': [s['chapter_id'] for s in sections], 'scenarios': [scene]}
    with pytest.raises(ValueError, match='operation_binding'):
        checker_validator(index)(packet, result)
    scene.update(operation_binding={'source_id': 'API-A', 'source_refs': [ref(4)]}, source_refs=[ref(3), ref(4), ref(6)])
    with pytest.raises(ValueError, match='another operation'):
        checker_validator(index)(packet, result)
    scene.update(trigger_condition='pageSize > 50', source_refs=[ref(3), ref(4), ref(8)], contract_source_refs=[ref(8)])
    assert checker_validator(index)(packet, result)[0]['operation_binding']['source_id'] == 'API-A'


@pytest.mark.parametrize("content,finish", [('{}', 'length'), ('{"items": [', 'stop')])
def test_truncated_or_invalid_json_is_audited_not_completed(tmp_path, monkeypatch, content, finish):
    monkeypatch.setenv("TEST_ECNU_KEY", "test-secret")
    def transport(*args):
        return {"model": "provider", "choices": [{"finish_reason": finish,
            "message": {"content": content, "reasoning_content": "private reasoning"}}], "usage": {"completion_tokens": 10}}
    client = SemanticClient({"base_url": "https://example.invalid", "api_key_env": "TEST_ECNU_KEY",
        "agent_model": "ecnu-max", "semantic_max_attempts": 1}, transport)
    packet = prepare_packets(tmp_path, "interaction-fixture", [{}], [], {})["batches"][0]
    assert not run_agent_packets(tmp_path, client, lambda p, r: [])['complete']
    assert not (tmp_path / "results" / (packet['batch_id'] + '.json')).exists()
    record = read_json(next((tmp_path / "attempts").glob('*.json')))
    assert record['response_diagnostic']['finish_reason'] == finish
    assert record['response_diagnostic']['content'] == content
    assert 'private reasoning' not in str(record)
    # A later retry can read a diagnostic-only attempt without treating it as
    # structured output to repair or accepting its partial JSON.
    assert not run_agent_packets(tmp_path, client, lambda p, r: [])['complete']
