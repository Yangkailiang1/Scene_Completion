"""RR/SR exception identification contract; historical protocols remain separate.

Generation has exactly one entrance: a real SSD exchange and its concern mount.
This module deliberately cannot consume checker or acceptance-test scenarios.
"""
from __future__ import annotations

import copy
from pathlib import Path

from .concerns import ACTIVE_CONCERN_KEYS, CONCERN_DEFINITIONS
from .schemas import stable_id
from .sources import fingerprint, validate_refs
from .interaction_hierarchy import bind_exchanges, validate_hierarchy

PROTOCOL = "rr-sr-ssd-identification-v1"
LAYERS = ("RR", "SR")
SERVICE_TYPES = ("display_interaction", "query_retrieval", "resource_mutation",
                 "analysis_generation", "release_activation")
OPERATION_KINDS = {"read", "create", "update", "delete", "display", "process", "publish", "external_call"}
WRITE_KINDS = {"create", "update", "delete", "publish"}
DEVICE_KEY = "service.display_interaction.device_adaptation"
EXCHANGE_FIELDS = {"local_id", "requirement_layer", "hierarchy_unit_id", "parent_rr_local_id", "parent_sr_local_id",
    "from_node", "to_node", "from_component_id", "to_component_id", "operation", "path_type", "guard",
    "request_fields", "response_fields", "contracts", "request_contracts", "response_contracts", "identity_contract",
    "cancellable", "return_description", "source_refs", "layer_use_case_id", "source_step_index", "source_step_label",
    "operation_kinds", "data_relations", 'business_service_roles', 'derived_response_data'}


def reject_generation_bypass(value):
    if isinstance(value, dict):
        forbidden = {"generation_constraints", "exception_scenarios", "failure_conditions", "constraint_scenarios",
            "explicit_exceptions", "abnormal_scenarios", "checker_scenarios", "test_scenarios", "constraints"}
        if set(value) & forbidden:
            raise ValueError("forbidden direct-constraint/exception generation field: " + ", ".join(sorted(set(value) & forbidden)))
        for item in value.values():
            reject_generation_bypass(item)
    elif isinstance(value, list):
        for item in value:
            reject_generation_bypass(item)


def validate_exchange_fields(exchange):
    reject_generation_bypass(exchange)
    from .interaction_query_data import validate_derived_response_shape
    validate_derived_response_shape(exchange)
    if set(exchange) - EXCHANGE_FIELDS:
        raise ValueError("unknown normal exchange fields: " + ", ".join(sorted(set(exchange) - EXCHANGE_FIELDS)))
    if "operation_kinds" in exchange and (not isinstance(exchange["operation_kinds"], list) or
            not exchange["operation_kinds"] or not set(exchange["operation_kinds"]) <= OPERATION_KINDS):
        raise ValueError("invalid operation_kinds=" + repr(exchange.get("operation_kinds")) + "; use only " + ", ".join(sorted(OPERATION_KINDS)) + "; classify the documented operation without inventing another operation")
    if not isinstance(exchange.get("data_relations", []), list):
        raise ValueError("data_relations must be a list")
    for relation in exchange.get("data_relations", []):
        if (set(relation) != {"object", "relation", "evidence_quote", "source_refs"} or
                not isinstance(relation["object"], str) or not relation["object"].strip() or
                not isinstance(relation["evidence_quote"], str) or not relation["evidence_quote"].strip() or
                relation["relation"] not in {"reference", "foreign_key", "cascade", "unique_key"}):
            raise ValueError("data relation must name an evidenced object and relation with sources")
    for field in ("contracts", "request_contracts", "response_contracts"):
        if not isinstance(exchange.get(field, []), list):
            raise ValueError("bound contracts must be a list")
        for contract in exchange.get(field, []):
            if set(contract) - {"rule", "source_refs"} or not isinstance(contract.get("rule"), str) or not contract["rule"].strip():
                raise ValueError("bound contract permits only positive rule and source_refs")
    roles = exchange.get('business_service_roles', [])
    if not isinstance(roles, list) or (roles and exchange['requirement_layer'] != 'RR'):
        raise ValueError('business service roles belong to RR logical business interactions')
    if len({r.get('service_type') for r in roles}) != len(roles):
        raise ValueError('duplicate RR business service role')
    for role in roles:
        if (set(role) != {'service_type', 'evidence_quote', 'source_refs', 'mapped_sr_local_ids'}
                or role['service_type'] not in SERVICE_TYPES or not role['evidence_quote']
                or not role['source_refs'] or not isinstance(role['mapped_sr_local_ids'], list)
                or not role['mapped_sr_local_ids'] or len(set(role['mapped_sr_local_ids'])) != len(role['mapped_sr_local_ids'])):
            raise ValueError('RR service role requires positive source and explicit SR mappings')


def same_comparison_scope(a, b, scope="layer_use_case"):
    if scope not in {"layer_use_case", "business_use_case", 'test_all'}:
        raise ValueError("unknown comparison scope")
    if scope == 'test_all':
        return True  # Exhaustive recommendations x independent test conditions.
    same = a["requirement_layer"] == b["requirement_layer"] and a["use_case_id"] == b["use_case_id"]
    return same and (scope == "business_use_case" or a.get("layer_use_case_id", a["use_case_id"]) == b.get("layer_use_case_id", b["use_case_id"]))


def baseline():
    """Every user-required concern is active in this protocol, including LLM quality.

    Historical ACTIVE_CONCERN_KEYS is frozen for reconstructing old experiments.
    Device adaptation was explicitly authorized in the mandatory baseline.
    """
    definitions = {k: copy.deepcopy(CONCERN_DEFINITIONS[k]) for k in sorted(ACTIVE_CONCERN_KEYS)}
    definitions[DEVICE_KEY] = {"key": DEVICE_KEY, "label": "设备适配性",
        "group": "service_display_interaction", "description": "设备、分辨率或横竖屏切换导致布局或交互异常"}
    for value in definitions.values():
        value.update({"draft": False, "layers": list(LAYERS), "registry_version": PROTOCOL})
    return definitions


def identification(scene):
    """Only identification fields are visible to coverage and adoption matchers."""
    return {key: scene.get(key) for key in ("scenario_id", "requirement_layer",
        "use_case_id", "layer_use_case_id", "name", "exception_object", "operation",
        "failure_mechanism", "trigger_condition", "necessary_conditions")}


def identification_text(scene):
    return "\n".join(str(scene.get(k, "")) for k in ("exception_object", "operation",
        "failure_mechanism", "trigger_condition", "necessary_conditions"))


def validate_identification(scene):
    for field in ("name", "exception_object", "operation", "failure_mechanism", "trigger_condition"):
        if not isinstance(scene.get(field), str) or not scene[field].strip():
            raise ValueError("exception identification missing " + field)
    if not isinstance(scene.get("necessary_conditions", []), list) or any(not isinstance(v, str) or not v.strip() for v in scene.get("necessary_conditions", [])):
        raise ValueError("necessary_conditions must be a list")


def normalized_conditions(scene):
    return sorted({v.strip() for v in scene.get("necessary_conditions", [])})


def skill_text():
    return (Path(__file__).resolve().parents[2] / "skills" / "scene-generate" / "SKILL.md").read_text(encoding="utf-8")


def normalize_resource_services(nodes):
    """Wrap both kinds of databases. No new endpoint or deployment is invented."""
    output = copy.deepcopy(nodes)
    mappings = []
    for physical in list(output):
        if physical.get("kind") not in {"internal_database", "external_database"}:
            continue
        existing = [n for n in output if n.get("physical_resource_id") == physical["node_id"]]
        if len(existing) > 1:
            raise ValueError("multiple resource facades for one physical database")
        facade = existing[0] if existing else None
        origin = "external" if physical["kind"] == "external_database" else "internal"
        if facade is not None:
            if facade.get("kind") not in {"internal_service", "abstract_service"} or facade.get("layer", "SR") != "SR" or facade.get("resource_origin", origin) != origin or facade.get("service_role", "resource_service") != "resource_service":
                raise ValueError("existing facade has incompatible service identity or database origin")
            facade.update({"layer": "SR", "service_role": "resource_service", "resource_origin": origin})
        if facade is None:
            facade = {"node_id": stable_id("SR-RESOURCE", physical["node_id"]),
                "name": physical["name"] + "资源服务", "kind": "internal_service",
                "layer": "SR", "service_role": "resource_service",
                "physical_resource_id": physical["node_id"],
                "resource_origin": origin,
                "logical_only": True, "source_refs": physical.get("source_refs", [])}
            output.append(facade)
        mappings.append({"physical_resource_id": physical["node_id"],
            "resource_service_id": facade["node_id"], "origin": facade["resource_origin"]})
    return output, mappings


def build_ssd(model):
    """Build actual request/return exchanges, rewriting physical DB endpoints first.

    Normal/optional paths are extracted before this function. Explicit exceptions
    and free-standing generation_constraints are rejected, never appended.
    """
    if model.get("protocol") != PROTOCOL or model.get("generation_constraints"):
        raise ValueError("wrong protocol or forbidden direct-constraint generation")
    reject_generation_bypass(model)
    nodes, mappings = normalize_resource_services(model["nodes"])
    resources = {m["physical_resource_id"]: m["resource_service_id"] for m in mappings}
    node_map = {n["node_id"]: n for n in nodes}
    exchanges, messages, business_roles = [], [], []
    hierarchies = []
    for uc in model["use_cases"]:
        raw_exchanges = uc["exchanges"]
        if uc.get("use_case_hierarchy"):
            units = validate_hierarchy(uc["use_case_hierarchy"])
            raw_exchanges = bind_exchanges(units, raw_exchanges)
            hierarchies.append({"use_case_id": uc["use_case_id"], "units": units})
        rr = {e["local_id"]: e for e in raw_exchanges if e["requirement_layer"] == "RR"}
        for number, raw in enumerate(raw_exchanges, 1):
            validate_exchange_fields(raw)
            layer = raw["requirement_layer"]
            if layer not in LAYERS:
                if layer == "AR":
                    continue
                raise ValueError("invalid exchange layer")
            item = copy.deepcopy(raw)
            for endpoint in ("from_node", "to_node"):
                item[endpoint] = resources.get(item[endpoint], item[endpoint])
                if item[endpoint] not in node_map:
                    raise ValueError("unknown SSD endpoint")
            endpoints = [node_map[item[k]] for k in ("from_node", "to_node")]
            source, target = endpoints
            service_kinds = {"internal_service", "abstract_service"}
            external_kinds = {"external_actor", "external_service", "external_llm"}
            if layer == "RR":
                human = source.get("kind") == "human_actor" and target.get("kind") == "frontend_ui" and target.get("boundary_role") == "ui"
                incoming = source.get("kind") in external_kinds and target.get("boundary_role") == "receiver"
                outgoing = source.get("boundary_role") == "receiver" and target.get("kind") in external_kinds
                if not (human or incoming or outgoing):
                    raise ValueError(f"RR requires human->UI or external<->receiving boundary: exchange={raw['local_id']}, from={item['from_node']} ({source.get('kind')}), to={item['to_node']} ({target.get('kind')}); human actors have no boundary_role, the UI endpoint has boundary_role=ui")
                if any(n.get("layer") not in {"RR", "SR"} for n in endpoints):
                    raise ValueError("RR boundary/actor must have an explicit valid layer")
            if layer == "SR":
                if any(n.get("layer") == "AR" and not n.get("service_role") == "resource_service" for n in endpoints):
                    raise ValueError("AR implementation calls cannot enter SR analysis")
                source_service = source.get("kind") in service_kinds and source.get("layer") == "SR" and not source.get("boundary_role")
                target_service = target.get("kind") in service_kinds and target.get("layer") == "SR" and not target.get("boundary_role")
                boundary_call = source.get("boundary_role") in {"ui", "receiver"} and source.get("layer") in {"RR", "SR"} and target_service
                # Explicit SR external integrations retain direction-specific concerns.
                service_call = source_service and (target_service or target.get("kind") in external_kinds and target.get("layer") == "SR")
                if not (boundary_call or service_call):
                    raise ValueError("SR requires boundary->SR service or an explicit SR service call")
                if not item.get("parent_rr_local_id") or item["parent_rr_local_id"] not in rr:
                    raise ValueError("SR exchange requires a corresponding RR interaction")
                if service_call and not item.get("parent_sr_local_id"):
                    raise ValueError(f"nested SR service call requires an enclosing SR parent: exchange={raw['local_id']}, from={item['from_node']}, to={item['to_node']}; retain the source-backed boundary->entry SR request, then set parent_sr_local_id to that earlier exchange whose target equals this caller")
                if boundary_call:
                    rr_parent = rr[item["parent_rr_local_id"]]
                    rr_source = node_map[rr_parent['from_node']]
                    # Kind identifies a human actor even when an extractor adds
                    # redundant UI metadata to it. RR validation above already
                    # verifies that the actual target is the real UI boundary.
                    parent_boundary = (rr_parent['to_node'] if rr_source.get('kind') == 'human_actor'
                        or not rr_source.get('boundary_role') else rr_parent['from_node'])
                    if item["from_node"] != parent_boundary:
                        raise ValueError("SR boundary differs from its RR parent boundary")
            item.update({"use_case_id": uc["use_case_id"], "sequence": number,
                "exchange_id": stable_id(layer + "-EX", uc["use_case_id"], item["local_id"]),
                "layer_use_case_id": item.get("layer_use_case_id") or uc.get("layer_use_case_ids", {}).get(layer, uc["use_case_id"])})
            if layer == "SR":
                item["parent_exchange_id"] = stable_id("RR-EX", uc["use_case_id"], item["parent_rr_local_id"])
                if item.get("parent_sr_local_id"):
                    item["parent_sr_exchange_id"] = stable_id("SR-EX", uc["use_case_id"], item["parent_sr_local_id"])
            item["message_ids"] = [item["exchange_id"] + "-REQ", item["exchange_id"] + "-RET"]
            exchanges.append(item)
            for direction, mid in zip(("request", "response"), item["message_ids"]):
                messages.append({"message_id": mid, "exchange_id": item["exchange_id"],
                    "requirement_layer": layer, "use_case_id": uc["use_case_id"],
                    "from_node": item["from_node" if direction == "request" else "to_node"],
                    "to_node": item["to_node" if direction == "request" else "from_node"],
                    "direction": direction, "text": item["operation"] if direction == "request" else item.get("return_description", "返回数据待确认"),
                    "fields": item.get("request_fields" if direction == "request" else "response_fields", []),
                    "derived_data": copy.deepcopy(item.get('derived_response_data', [])) if direction == 'response' else [],
                    "source_refs": item["source_refs"]})
    if not exchanges:
        raise ValueError("no real SSD exchanges")
    by_exchange = {e["exchange_id"]: e for e in exchanges}
    if len(by_exchange) != len(exchanges):
        raise ValueError("duplicate SSD exchange IDs")
    for e in exchanges:
        parent = by_exchange.get(e.get("parent_sr_exchange_id"))
        if e.get("parent_sr_exchange_id") and (not parent or parent["requirement_layer"] != "SR" or
                parent["parent_exchange_id"] != e["parent_exchange_id"] or parent["to_node"] != e["from_node"] or parent["sequence"] >= e["sequence"]):
            raise ValueError(f"nested SR call has invalid caller/order/parent: child={e['local_id']}, parent={parent['local_id'] if parent else 'missing'}, expected_from={parent['to_node'] if parent else 'unknown'}, actual_from={e['from_node']}; child must follow its parent and remain inside the same RR request")
        for role in e.get('business_service_roles', []):
            mapped = [by_exchange.get(stable_id('SR-EX', e['use_case_id'], sid)) for sid in role['mapped_sr_local_ids']]
            if any(not m or m['requirement_layer'] != 'SR' or m.get('parent_exchange_id') != e['exchange_id'] for m in mapped):
                raise ValueError('RR business service role must map to real SR expansions of its own interaction')
            business_roles.append({**role, 'role_id': stable_id('RR-BUSINESS', e['exchange_id'], role['service_type']),
                'rr_exchange_id': e['exchange_id'], 'mapped_sr_exchange_ids': [m['exchange_id'] for m in mapped],
                'logical_only': True, 'subject_node_id': e['to_node'] if node_map[e['to_node']].get('boundary_role') else e['from_node'],
                'use_case_id': e['use_case_id']})
    ordered = []
    def expand(e):
        ordered.append(e["message_ids"][0])
        for child in exchanges:
            parent = child.get("parent_sr_exchange_id") or child.get("parent_exchange_id")
            if parent == e["exchange_id"]:
                expand(child)
        ordered.append(e["message_ids"][1])
    for e in exchanges:
        if e["requirement_layer"] == "RR":
            expand(e)
    if len(ordered) != len(messages) or set(ordered) != {m["message_id"] for m in messages}:
        raise ValueError("fused SSD has missing or cyclic interactions")
    message_lookup = {m["message_id"]: m for m in messages}
    messages = [{**message_lookup[mid], "sequence": i} for i, mid in enumerate(ordered, 1)]
    return {"protocol": PROTOCOL, "nodes": nodes, "resource_service_mappings": mappings,
        "exchanges": exchanges, "messages": messages, "fused_message_ids": ordered,
        "use_case_hierarchies": hierarchies, 'rr_business_service_roles': business_roles, "source_hash": model["source_hash"]}


def route_mounts(ssd):
    definitions = baseline()
    nodes = {n["node_id"]: n for n in ssd["nodes"]}
    mounts = []
    by_exchange = {e["exchange_id"]: e for e in ssd["exchanges"]}
    for exchange in ssd["exchanges"]:
        layer = exchange["requirement_layer"]
        source, target = [nodes[exchange[k]] for k in ("from_node", "to_node")]
        candidates = set()
        # Semantic extraction supplies positive normal-operation traits. Routing
        # is deterministic; no LLM candidate applicability review occurs here.
        kinds = set(exchange.get("operation_kinds", []))
        legacy_unspecified = not kinds
        writes = bool(kinds & WRITE_KINDS)
        relations = {r["relation"] for r in exchange.get("data_relations", [])}

        def add(key, subject, direction="request"):
            if key not in definitions:
                raise ValueError("unregistered mandatory concern")
            candidates.add((key, subject["node_id"], direction))

        add("common.timeout", target, "transport")
        # Actor concerns are attached only to the actual RR actor exchange.
        # SR has its own explicit caller/identity contract, never copied RR output.
        if source.get("kind") == "human_actor":
            for key in ("human.authentication", "human.authorization"):
                add(key, source)
        if source.get("kind") in {"external_actor", "external_service", "external_llm"}:
            for key in ("external_service.permission", "external_service.identity"):
                add(key, source)
            if source.get("kind") == "external_llm":
                add("external_llm.access_permission", source)
                for key in definitions:
                    if key.startswith("external_llm.quality."):
                        add(key, source, "request")
        if layer == "SR" and exchange.get("identity_contract"):
            if source.get("boundary_role") == "ui":
                for key in ("human.authentication", "human.authorization"):
                    add(key, source)
            elif source.get("boundary_role") == "receiver":
                for key in ("external_service.identity", "external_service.permission"):
                    add(key, source)
                parent = by_exchange.get(exchange.get("parent_exchange_id"), {})
                actor = nodes.get(parent.get("from_node"), {})
                if actor.get("kind") == "external_llm":
                    add("external_llm.access_permission", source)
        if layer == "SR" and target.get("kind") in {"internal_service", "abstract_service"} and not target.get("boundary_role"):
            add("service.dependency.availability", target)
        for direction in ("request", "response"):
            # Data traits determine checked fields; all seven remain available.
            if exchange.get(direction + "_fields") or exchange.get(direction + "_contracts"):
                for key in definitions:
                    if key.startswith("api.data."):
                        add(key, target if direction == "request" else source, direction)
        for node in (source, target):
            if node.get("service_role") == "resource_service":
                prefix = "internal_database." if node["resource_origin"] == "internal" else "external_database."
                for key in definitions:
                    if key.startswith(prefix):
                        suffix = key[len(prefix):]
                        if not legacy_unspecified:
                            if suffix in {"persistence", "idempotency", "concurrency_consistency"} and not writes:
                                continue
                            if suffix == "uniqueness" and not (writes or "unique_key" in relations):
                                continue
                            if suffix == "referential_consistency" and not relations & {"reference", "foreign_key", "cascade"}:
                                continue
                            if suffix == "query_performance" and "read" not in kinds:
                                continue
                        add(key, node)
                if node["resource_origin"] == "external":
                    for key in ("external_service.availability", "external_service.contract"):
                        add(key, node)
            # The five functional categories belong only to actual SR service
            # roles. RR UI inspection is outside this service-concern scope.
            functional_types = node.get("service_types", []) if (layer == 'SR' and node.get('layer') == 'SR'
                and node.get('kind') in {'internal_service', 'abstract_service'} and not node.get('boundary_role')) else []
            for service_type in functional_types:
                if service_type not in SERVICE_TYPES:
                    raise ValueError("invalid functional service category")
                if not legacy_unspecified:
                    applicable = {"display_interaction": "display" in kinds,
                        "query_retrieval": "read" in kinds,
                        "resource_mutation": writes, "analysis_generation": "process" in kinds,
                        "release_activation": "publish" in kinds}
                    if not applicable[service_type]:
                        continue
                for key in definitions:
                    if key.startswith("service." + service_type + "."):
                        add(key, node)
        if target.get("kind") in {"external_service", "external_llm"}:
            for key in ("external_service.availability", "external_service.contract"):
                add(key, target)
            if target["kind"] == "external_llm":
                for key in definitions:
                    if key in {"external_llm.availability", "external_llm.contract"} or key.startswith("external_llm.quality."):
                        add(key, target, "response")
        if layer == "SR" and all(n.get("kind") in {"internal_service", "abstract_service"} and n.get("resource_origin") != "external" for n in (source, target)):
            for key in definitions:
                if key.startswith("service_relation.") or key == "service.dependency.availability":
                    if not legacy_unspecified:
                        if key == "service_relation.cascade_operation" and not ("delete" in kinds and "cascade" in relations):
                            continue
                        if key in {"service_relation.idempotency", "service_relation.cross_service_consistency", "service_relation.concurrency_consistency"} and not writes:
                            continue
                    add(key, target, "relation")
        # cancellable describes an ordinary voluntary option, never proof of
        # an abnormal interruption. The legacy workflow concern remains in the
        # registry for historical replay, but is not automatically mounted.
        for key, node_id, direction in sorted(candidates):
            mounts.append({"mount_id": stable_id("MOUNT", exchange["exchange_id"], key, node_id, direction),
                "concern_key": key, "concern_description": ("本交换查询超过允许时限；阈值待确认，不假设联查、索引或执行计划" if key.endswith(".query_performance") else definitions[key]["description"]),
                "requirement_layer": layer, "use_case_id": exchange["use_case_id"],
                "exchange_id": exchange["exchange_id"], "message_ids": exchange["message_ids"],
                "subject_node_id": node_id, "payload_direction": direction,
                "source_refs": exchange["source_refs"]})
        # RR business responsibilities are source-backed logical roles, not
        # deployment components or copied SR exception candidates. Each keeps
        # its own RR exchange, positive evidence and actual SR expansion links.
        for role in ssd.get('rr_business_service_roles', []):
            if role['rr_exchange_id'] != exchange['exchange_id']:
                continue
            for key in sorted(k for k in definitions if k.startswith('service.' + role['service_type'] + '.')):
                mounts.append({'mount_id': stable_id('MOUNT', exchange['exchange_id'], key, role['role_id'], 'business_role'),
                    'concern_key': key, 'concern_description': definitions[key]['description'],
                    'requirement_layer': 'RR', 'use_case_id': exchange['use_case_id'],
                    'exchange_id': exchange['exchange_id'], 'message_ids': exchange['message_ids'],
                    'subject_node_id': role['subject_node_id'], 'payload_direction': 'business_role',
                    'business_role_id': role['role_id'], 'mapped_sr_exchange_ids': role['mapped_sr_exchange_ids'],
                    'source_refs': role['source_refs']})
    return mounts


def validate_generated(scenes, ssd, mounts, index):
    by_mount = {m["mount_id"]: m for m in mounts}
    exchange_ids = {e["exchange_id"] for e in ssd["exchanges"]}
    message_ids = {m["message_id"] for m in ssd["messages"]}
    seen, represented = set(), set()
    for scene in scenes:
        sid = scene["scenario_id"]
        if sid in seen:
            raise ValueError("duplicate generated ID")
        seen.add(sid)
        if scene["scenario_type"] in {"main_success", "alternative"}:
            continue
        if scene["scenario_type"] != "exception" or scene.get("generation_source") != "ssd_concern":
            raise ValueError("forbidden exception generation bypass")
        validate_identification(scene)
        mount = by_mount.get(scene.get("mount_id"))
        if not mount or scene.get("requirement_layer") != mount["requirement_layer"] or scene.get("use_case_id") != mount["use_case_id"]:
            raise ValueError("exception must reference a same-layer, same-UC concern mount")
        if scene.get("exchange_id") != mount["exchange_id"] or scene["exchange_id"] not in exchange_ids:
            raise ValueError("invalid SSD exchange")
        if scene.get("message_ids") != mount["message_ids"] or not set(scene["message_ids"]) <= message_ids:
            raise ValueError("invalid SSD messages")
        if scene.get("concern_keys") != [mount["concern_key"]]:
            raise ValueError("generated concern differs from its mount")
        validate_refs(scene["source_refs"], index)
        represented.add(mount["mount_id"])
    if represented != set(by_mount):
        raise ValueError("every valid mount needs retained exception candidates; filtering forbidden")
    return True
