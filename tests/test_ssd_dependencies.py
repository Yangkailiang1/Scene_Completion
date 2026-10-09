"""Evidence-backed architecture dependency expansion and legacy compatibility."""
import copy

import pytest

from scene_completion.schemas import ValidationFailure
from scene_completion.ssd import generate_ssd_bundle, validate_ssd
from tests.test_scene_completion import sample_model


def model_with_dependencies(dependencies, version="6"):
    model = sample_model()
    model["version"] = version
    # Deliberately anchor dispatch after the first business step. Dependency
    # source indices are evidence, not permission to precede their parent.
    model["use_cases"][0]["main_flow"] = [
        {"step_index": 1, "text": "用户提交订单", "source_location": "requirements.md:10"},
        {"step_index": 2, "text": "系统调用订单接口", "source_location": "design.md:20"},
        {"step_index": 3, "text": "系统展示结果", "source_location": "requirements.md:12"},
    ]
    component = model["use_cases"][0]["architecture"]["ar"][0]
    component["source_step_index"] = 2
    if dependencies is not None:
        component["dependencies"] = copy.deepcopy(dependencies)
    return model


def dependency(target, operation="处理请求", **changes):
    return {"target_node_id": target, "operation": operation,
            "source_step_index": 1,
            "source_refs": [{"document": "design.md", "line_start": 42, "line_end": 44}],
            "request_fields": ["orderId"], "response_fields": ["status"],
            "direction": "outgoing", **changes}


def dependency_requests(bundle):
    return [m for m in bundle["fused"]["messages"]
            if m.get("dependency_node_id") and m["message_kind"] in {"internal_call", "event"}]


def test_architecture_report_separates_source_confirmed_and_proposed_edges(tmp_path):
    from scene_completion.placements import export_placements, validate_architecture_review
    from scene_completion.sources import fingerprint
    model = model_with_dependencies([dependency("int-db", "写入订单"), dependency("ext-service", "可能调用支付")])
    generated = {"scenarios": []}
    provisional = export_placements(model, generated, tmp_path)
    calls = [{k: v for k, v in c.items() if k not in {"evidence_status", "evidence_assessment", "model_edge_id"}}
             for c in provisional["calls"]]
    review = {"input_hash": fingerprint(calls), "model": "gpt-6-luna", "reasoning_effort": "max",
              "decisions": [{"call_index": 0, "status": "confirmed", "reason": "原文明示写入"},
                            {"call_index": 1, "status": "needs_confirmation", "reason": "只有接口错误码"}]}
    final = export_placements(model, generated, tmp_path, evidence_review=review)
    assert final["evidence_review_complete"] and final["confirmed_call_count"] == final["pending_call_count"] == 1
    assert len(final["calls"]) == 2  # review never drops generated relationships
    assert (tmp_path / "architecture_calls.svg").read_text(encoding="utf-8").count('stroke-dasharray="8 6"') == 1
    with pytest.raises(ValueError):
        validate_architecture_review(calls, {**review, "input_hash": "stale"})
    with pytest.raises(ValueError):
        validate_architecture_review(calls, {**review, "decisions": review["decisions"][:1]})


@pytest.mark.parametrize("version", ["4", "6", "9"])
def test_database_and_external_payment_are_both_preserved(version):
    model = model_with_dependencies([
        dependency("int-db", "保存订单", failure_conditions=["数据库不可用"]),
        dependency("ext-service", "发起支付"),
    ], version)
    bundle = generate_ssd_bundle(model, "UC-001")
    requests = dependency_requests(bundle)
    assert {m["to_node"] for m in requests} == {"int-db", "ext-service"}
    assert len(requests) == 2
    assert len({m["exchange_id"] for m in requests}) == 2
    assert {m["layer"] for m in requests} == {"AR", "SR"}
    for request in requests:
        returns = [m for m in bundle["fused"]["messages"] if m["exchange_id"] == request["exchange_id"]
                   and m["message_kind"] in {"internal_return", "response"}]
        assert len(returns) == 1
        assert (returns[0]["from_node"], returns[0]["to_node"]) == (request["to_node"], request["from_node"])
        assert returns[0]["reply_to_message_id"] == request["message_id"]
        assert request["source_refs"][0]["line_start"] == 42
        assert request["request_fields"] == ["orderId"]
        assert returns[0]["response_fields"] == ["status"]
    assert next(m for m in requests if m["to_node"] == "int-db")["failure_conditions"] == ["数据库不可用"]
    assert validate_ssd(bundle["fused"], model)["valid"]


def test_two_internal_dependencies_and_two_databases_keep_ids_even_with_identical_names():
    model = model_with_dependencies([
        dependency("inventory-a", "扣减库存"), dependency("inventory-b", "查询可售库存"),
        dependency("int-db", "保存订单"), dependency("audit-db", "写入审计记录"),
    ])
    model["system_composition"]["nodes"].extend([
        {"node_id": "inventory-a", "name": "InventoryService", "kind": "internal_service", "layer": "AR"},
        {"node_id": "inventory-b", "name": "InventoryService", "kind": "internal_service", "layer": "AR"},
        {"node_id": "audit-db", "name": "订单数据库", "kind": "internal_database", "layer": "AR"},
    ])
    bundle = generate_ssd_bundle(model, "UC-001")
    assert {m["to_node"] for m in dependency_requests(bundle)} == {"inventory-a", "inventory-b", "int-db", "audit-db"}
    ids = {line["node_id"] for line in bundle["fused"]["lifelines"]}
    assert {"inventory-a", "inventory-b", "int-db", "audit-db"} <= ids
    assert {m["to_node"] for m in dependency_requests(bundle)} <= {l["node_id"] for l in bundle["ar"]["lifelines"]}


@pytest.mark.parametrize("version", ["4", "6"])
def test_callback_reverses_endpoints_and_reply_and_retains_source_and_parent_anchor(version):
    model = model_with_dependencies([dependency("ext-service", "支付结果回调", direction="incoming")], version)
    bundle = generate_ssd_bundle(model, "UC-001")
    callback, = dependency_requests(bundle)
    owner = "compute" if version == "4" else "impl-order"
    assert (callback["from_node"], callback["to_node"]) == ("ext-service", owner)
    assert callback["direction"] == "incoming"
    assert callback["message_kind"] == "event"
    assert callback["source_step_index"] == 1
    assert callback["execution_step_index"] == 2
    assert callback["source_location"] == "design.md:42-44"
    parent, = [m for m in bundle["fused"]["messages"] if m["exchange_id"] == callback["parent_exchange_id"]
               and m["message_kind"] == "internal_call"]
    assert parent["ssd_sequence"] < callback["ssd_sequence"]
    response, = [m for m in bundle["fused"]["messages"] if m.get("reply_to_message_id") == callback["message_id"]]
    assert (response["from_node"], response["to_node"], response["direction"]) == (owner, "ext-service", "outgoing")
    assert response["source_refs"] == callback["source_refs"]


@pytest.mark.parametrize("changes, expected", [
    ({"target_node_id": "invented-service"}, "unknown or invalid"),
    ({"target_node_id": "user", "direction": "incoming"}, "unknown or invalid"),
    ({"target_node_id": "int-db", "direction": "incoming"}, "callback source"),
    ({"source_refs": [], "source_location": ""}, "evidence"),
    ({"source_step_index": 0}, "positive source_step_index"),
    ({"source_step_index": True}, "positive source_step_index"),
    ({"source_refs": [{"document": "design.md", "line_start": 3, "line_end": 2}]}, "invalid source reference"),
    ({"direction": "sideways"}, "direction"),
    ({"layer": "RR"}, "layer"),
    ({"request_fields": "orderId"}, "request_fields"),
])
def test_invalid_dependency_evidence_and_endpoints_are_rejected(changes, expected):
    with pytest.raises(ValidationFailure, match=expected):
        generate_ssd_bundle(model_with_dependencies([dependency("ext-service", **changes)]), "UC-001")


@pytest.mark.parametrize("version", ["4", "6"])
def test_legacy_db_default_and_explicit_external_id_priority(version):
    model = model_with_dependencies(None, version)
    bundle = generate_ssd_bundle(model, "UC-001")
    request, = dependency_requests(bundle)
    assert request["to_node"] == "int-db"
    assert request["explicitness"] == "inferred"
    component = model["use_cases"][0]["architecture"]["ar"][0]
    component["external_dependency_node_id"] = "ext-service"
    bundle = generate_ssd_bundle(model, "UC-001")
    request, = dependency_requests(bundle)
    assert request["to_node"] == "ext-service"


def test_explicit_empty_dependency_list_disables_legacy_default_and_name_inference():
    model = model_with_dependencies([])
    assert dependency_requests(generate_ssd_bundle(model, "UC-001")) == []
    model = model_with_dependencies(None)
    model["system_composition"]["nodes"] = [n for n in model["system_composition"]["nodes"] if n["node_id"] != "int-db"]
    model["interactions"] = [i for i in model["interactions"] if i["to_node"] != "int-db"]
    model["use_cases"][0]["architecture"]["ar"][0]["microservice_id"] = "payment"
    model["system_composition"]["nodes"].append({"node_id": "payment", "name": "PaymentService", "kind": "internal_service", "layer": "AR"})
    next(n for n in model["system_composition"]["nodes"] if n["node_id"] == "ext-service")["name"] = "PaymentService"
    assert dependency_requests(generate_ssd_bundle(model, "UC-001")) == []


def test_source_location_only_and_explicit_layer_are_supported():
    dep = dependency("ext-service", source_refs=[], source_location="design.md:section 4.2", layer="AR")
    request, = dependency_requests(generate_ssd_bundle(model_with_dependencies([dep]), "UC-001"))
    assert request["source_location"] == "design.md:section 4.2"
    assert request["layer"] == "AR"
    assert request["direction"] == "outgoing"


@pytest.mark.parametrize("version", ["4", "6", "9"])
def test_secondary_service_database_call_uses_actual_caller_and_preserves_evidence(version):
    model = model_with_dependencies([
        dependency("catalog", "查询商品与SKU"),
        dependency("int-db", "读取product/sku表", caller_node_id="catalog"),
    ], version)
    model["system_composition"]["nodes"].append({"node_id": "catalog", "name": "ProductCatalogService",
                                                "kind": "internal_service", "layer": "AR"})
    bundle = generate_ssd_bundle(model, "UC-001")
    db, = [m for m in dependency_requests(bundle) if m["to_node"] == "int-db"]
    primary, = [m for m in dependency_requests(bundle) if m["to_node"] == "catalog"]
    assert primary["from_node"] == ("compute" if version == "4" else "impl-order")
    assert (db["from_node"], db["to_node"], db["direction"]) == ("catalog", "int-db", "internal")
    assert db["microservice_id"] == db["service_id"] == db["caller_node_id"] == "catalog"
    assert db["source_step_index"] == 1 and db["execution_step_index"] == 2
    assert db["source_refs"] == primary["source_refs"]
    assert db["parent_exchange_id"] == primary["parent_exchange_id"]
    response, = [m for m in bundle["fused"]["messages"] if m.get("reply_to_message_id") == db["message_id"]]
    assert (response["from_node"], response["to_node"]) == ("int-db", "catalog")
    assert response["microservice_id"] == "catalog"
    assert validate_ssd(bundle["fused"], model)["valid"]


def test_callback_targets_declared_local_caller_and_caller_has_lifeline():
    model = model_with_dependencies([dependency("ext-service", "支付状态回调", direction="incoming", caller_node_id="callback-handler")])
    model["system_composition"]["nodes"].append({"node_id": "callback-handler", "name": "CallbackService",
                                                "kind": "internal_service", "layer": "AR"})
    bundle = generate_ssd_bundle(model, "UC-001")
    callback, = dependency_requests(bundle)
    assert (callback["from_node"], callback["to_node"]) == ("ext-service", "callback-handler")
    assert callback["direction"] == "incoming" and callback["microservice_id"] == "callback-handler"
    assert "callback-handler" in {line["node_id"] for line in bundle["fused"]["lifelines"]}


@pytest.mark.parametrize("caller", ["unknown-caller", "ext-service", "int-db", "user", ""])
def test_invalid_or_external_local_caller_is_rejected(caller):
    with pytest.raises(ValidationFailure, match="caller_node_id must reference"):
        generate_ssd_bundle(model_with_dependencies([dependency("int-db", caller_node_id=caller)]), "UC-001")


@pytest.mark.parametrize("caller", ["impl-order", "sr-order"])
def test_implementation_api_and_abstract_service_callers_are_supported(caller):
    request, = dependency_requests(generate_ssd_bundle(model_with_dependencies([
        dependency("int-db", caller_node_id=caller)]), "UC-001"))
    assert request["from_node"] == request["microservice_id"] == caller
