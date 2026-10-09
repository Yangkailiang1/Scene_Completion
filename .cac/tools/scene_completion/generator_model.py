"""Independent, cited ECNU generator input extraction; never reads checker scenes."""
from __future__ import annotations

import copy
import re
from pathlib import Path

from .concerns import ACTIVE_CONCERN_KEYS, CONCERN_DEFINITIONS
from .schemas import stable_id, validate_scene_model
from .semantic_backend import collect_packets, prepare_packets, read_json, write_json
from .sources import fingerprint, use_case_sections, validate_refs


def generator_model_packets(base, index, directory):
    payloads = []
    skill = (Path(__file__).resolve().parents[2] / "skills" / "scene-generate" / "SKILL.md").read_text(encoding="utf-8")
    for uc in base["use_cases"]:
        sections = use_case_sections(index, uc["use_case_id"])
        if not sections:
            raise ValueError("generator use case has no original source sections")
        numbered = []
        for section in sections:
            doc = next(d for d in index["documents"] if d["document"] == section["document"])
            lines = doc["text"].splitlines()
            numbered.append({**section, "role": doc.get("role", "unspecified"),
                             "numbered_text": "\n".join(f"{n}: {lines[n-1]}" for n in
                                 range(section["line_start"], section["line_end"] + 1))})
        # Identity/architecture hints contain no old scenario or checker content.
        arch = copy.deepcopy(uc.get("architecture", {}))
        payloads.append({"use_case_id": uc["use_case_id"], "use_case_name": uc["use_case_name"],
                         "architecture_hint": arch, "sections": numbered,
                         "generator_skill": skill,
                         "taxonomy": [{"key": k, "label": CONCERN_DEFINITIONS[k]["label"],
                                       "definition": CONCERN_DEFINITIONS[k]["description"]}
                                      for k in sorted(ACTIVE_CONCERN_KEYS)]})
    return prepare_packets(directory, "generator-model", payloads, [
        "Extract generator input independently from ALL assigned original requirement/design sections. Never use checker outputs or test_spec.",
        "Retain one requirement-level main flow and ALL explicitly described alternative/exception branches. Ground each branch trigger, behavior, result and recovery in exact lines. Do not append success-after-failure steps.",
        "Keep requirement and design branches separate when their failure condition, reference object, operation or outcome differs. Never assert two constraints are equivalent unless the source explicitly does so. Preserve the exact requirement branch before adding independent design branches.",
        "For a branch, steps are ONLY the actual successful prefix before its divergence followed by its documented branch behavior. The failed/cancelled step cannot remain a successful step.",
        "Extract ALL concrete failure_conditions/constraints from branches AND normal validation, state, ownership, idempotency, concurrency, dependency and event rules. Conditions must identify the actual object and operation, not generic concern descriptions.",
        "Every documented exception/alternative check also needs a constraint instance with its independently assigned concern. A repeated business request returning HTTP success/existing resource still requires its specific idempotency condition and response; do not substitute a generic table write or omit it because it is an alternative.",
        "Choose concern_keys from the taxonomy independently. Stock insufficiency and off-sale purchase are business constraints; cancellation is service.workflow.interruption. Internal service failure is service.dependency.availability, not an external actor.",
        "For each constraint return the business/API step index, check_target_name, specific trigger, behavior steps, and actual outcome/recovery if explicitly stated; otherwise write 待需求确认. Include source citations supporting the condition and every claimed outcome.",
        "Dependencies describe actual direct calls including database access, internal service calls, external service calls AND incoming callbacks. One record per distinct call with caller_name, target_name, target_kind, operation, direction and exact sources. Do not invent calls from a generic database default.",
        "Use-case success preconditions/postconditions are context only, not exception branch guarantees. Resolve Chinese/service aliases ONLY when source establishes their identity.",
        "Return covered_section_ids for every assigned chapter and no checker IDs. Source lines must belong to the supplied sections.",
    ], {"covered_section_ids": ["all assigned IDs"], "preconditions": "requirement context",
        "postconditions": "requirement success guarantee", "trigger": "main trigger",
        "main_flow": [{"text": "requirement business step", "source_refs": [{"document": "name", "line_start": 1, "line_end": 2}]}],
        "scenarios": [{"scenario_type": "alternative|requirement_exception", "name": "branch",
            "anchor_step_index": 1, "trigger": "specific condition", "steps": ["actual path"],
            "expected_result": "documented or 待需求确认", "recovery": "documented or 待需求确认",
            "concern_keys": ["taxonomy key"], "source_refs": [{"document": "name", "line_start": 1, "line_end": 2}]}],
        "constraints": [{"name": "specific check", "check_target_name": "actual service or system",
            "source_step_index": 1, "trigger": "concrete failure condition", "scenario_steps": ["actual behavior"],
            "expected_result": "documented or 待需求确认", "recovery": "documented or 待需求确认",
            "concern_keys": ["taxonomy key"], "source_refs": [{"document": "name", "line_start": 1, "line_end": 2}]}],
        "dependencies": [{"caller_name": "primary microservice", "target_name": "actual dependency",
            "target_kind": "internal_service|external_service|internal_database",
            "operation": "documented operation", "direction": "outgoing|incoming",
            "source_step_index": 1, "request_fields": [], "response_fields": [],
            "source_refs": [{"document": "name", "line_start": 1, "line_end": 2}]}]})


def model_packet_validator(index):
    def validate(packet, result):
        data = copy.deepcopy(result)
        sections = packet["input"]["sections"]
        covered = data.get("covered_section_ids")
        expected = {s["chapter_id"] for s in sections}
        if not isinstance(covered, list) or len(covered) != len(expected) or set(covered) != expected:
            raise ValueError("generator omitted original source sections")
        for field in ("main_flow", "scenarios", "constraints", "dependencies"):
            if not isinstance(data.get(field), list):
                raise ValueError("generator missing " + field)
        if not data["main_flow"]:
            raise ValueError("generator needs a main flow")
        for collection in ("main_flow", "scenarios", "constraints", "dependencies"):
            for item in data[collection]:
                try:
                    item["source_refs"] = validate_refs(item.get("source_refs"), index, sections)
                except ValueError as exc:
                    allowed = [{"document": s["document"], "line_start": s["line_start"],
                                "line_end": s["line_end"]} for s in sections]
                    raise ValueError(f"{collection} {item.get('name', item.get('operation', item.get('text', '')))}: {exc}; "
                                     f"provided={item.get('source_refs')}; cite only assigned sections={allowed}") from exc
                if collection == "main_flow" and (not isinstance(item.get("text"), str) or not item["text"].strip()):
                    raise ValueError("main flow needs a nonempty behavior text")
                if collection in ("scenarios", "constraints"):
                    if not isinstance(item.get("name"), str) or not item["name"].strip():
                        raise ValueError("generator branch/check needs a name")
                    if not str(item.get("trigger", "")).strip():
                        raise ValueError("missing concrete failure condition")
                    keys = item.get("concern_keys")
                    if not isinstance(keys, list) or any(k not in ACTIVE_CONCERN_KEYS for k in keys):
                        raise ValueError("invalid generator concern keys")
                    if collection == "constraints" and not keys:
                        raise ValueError("constraint must have an independently assigned concern")
                    steps = item.get("steps" if collection == "scenarios" else "scenario_steps")
                    if not isinstance(steps, list) or not steps or any(not isinstance(s, str) or not s.strip() for s in steps):
                        raise ValueError("generator branch needs actual behavior")
                    step = item.get("anchor_step_index" if collection == "scenarios" else "source_step_index")
                    if type(step) is not int or not 1 <= step <= len(data["main_flow"]):
                        raise ValueError(f"{collection} '{item.get('name', item.get('trigger', ''))}' anchor {step} outside requirement main_flow 1..{len(data['main_flow'])}; map design steps to a VALID requirement business step, do not copy design numbering")
                    if collection == "scenarios" and item.get("scenario_type") not in {"alternative", "requirement_exception"}:
                        raise ValueError("invalid generator branch type")
                if collection == "dependencies":
                    if not isinstance(item.get("operation"), str) or not item["operation"].strip():
                        raise ValueError("dependency needs a documented operation")
                    if item.get("target_kind") not in {"internal_service", "external_service", "internal_database"}:
                        raise ValueError("unsupported dependency kind")
                    if item.get("direction") not in {"incoming", "outgoing"} or not item.get("target_name") or not item.get("caller_name"):
                        raise ValueError("invalid dependency direction/identity")
                    if type(item.get("source_step_index")) is not int or not 1 <= item["source_step_index"] <= len(data["main_flow"]):
                        raise ValueError("dependency anchor outside main flow")
        data["use_case_id"] = packet["input"]["use_case_id"]
        return [data]
    return validate


def _location(refs):
    r = refs[0]
    return f"{r['document']}:{r['line_start']}-{r['line_end']}"


def merge_generator_model(base, index, directory):
    values, status = collect_packets(directory, model_packet_validator(index))
    if not status["complete"]:
        return {"complete": False, "batch_status": status}
    expected = generator_model_packets(base, index, Path(directory) / "_expected")
    if read_json(Path(directory) / "manifest.json")["input_hash"] != expected["input_hash"]:
        raise ValueError("generator packet universe differs from original sources")
    model = copy.deepcopy(base)
    model["project"], model["system_name"] = base["project"], base["system_name"]
    model["source"] = {"path": index["documents"][0]["document"],
                      "locations": [{"path": d["document"], "hash": d["content_hash"]} for d in index["documents"]]}
    model["generator_provenance"] = {"source_hash": fingerprint(index), "complete": True,
                                    "method": "independent-source-constraints", "batch_status": status,
                                    "baseline_node_ids": [n["node_id"] for n in base["system_composition"]["nodes"]],
                                    "skill_hash": fingerprint((Path(__file__).resolve().parents[2] / "skills" /
                                        "scene-generate" / "SKILL.md").read_text(encoding="utf-8"))}
    nodes = model["system_composition"]["nodes"]
    system = next(n for n in nodes if n["node_id"] == "system")
    system["name"] = model["system_name"]
    existing = {(n["name"], n["kind"]): n for n in nodes}
    def canonical_name(name):
        # Structured actor/service annotations are aliases, not similarity rules.
        name = re.sub(r"(?:ACT-\d+)[（(]([^）)]+)[）)]", r"\1", name).strip()
        name = re.sub(r"[（(](?:ACT-\d+)[）)]", "", name).strip()
        wrapper = re.fullmatch(r"(?:在线商城系统|" + re.escape(model["system_name"]) + r")[（(]([^）)]+)[）)]", name)
        if wrapper and any(n["name"] == wrapper[1] and n["kind"] in {"internal_service", "abstract_service"} for n in nodes):
            return wrapper[1]
        if name in {"在线商城系统", model["system_name"], "system"}:
            return model["system_name"]
        if name == "OnlineMallSystem":
            return model["system_name"]
        # Table qualifiers are analysis notation, not separate databases.
        name = re.sub(r"[（(](?:内部数据库|数据库)[）)]$", "", name).strip()
        name = re.sub(r"(?<=[A-Za-z0-9_])\s*表$", " 表", name)
        return name
    def node(name, kind, refs):
        if name in {model["system_name"], "在线商城系统", "system"}:
            return system["node_id"]
        if (name, kind) not in existing:
            n = {"node_id": stable_id("NODE", kind, name), "name": name, "kind": kind,
                 "layer": "SR" if kind == "external_service" else "AR",
                 "source_location": _location(refs), "source_refs": refs}
            nodes.append(n); existing[name, kind] = n
        return existing[name, kind]["node_id"]
    by_id = {v["use_case_id"]: v for v in values}
    for uc in model["use_cases"]:
        value = by_id[uc["use_case_id"]]
        for field in ("trigger", "preconditions", "postconditions"):
            uc[field] = value.get(field) or "待需求确认"
        uc["main_flow"] = [{"step_index": i+1, "text": s["text"], "source_location": _location(s["source_refs"]),
                            "source_refs": s["source_refs"]} for i, s in enumerate(value["main_flow"])]
        uc["source_location"] = uc["main_flow"][0]["source_location"]
        uc["scenarios"] = [{"scenario_id": uc["use_case_id"]+"-main", "scenario_type": "main",
                            "name": "主成功场景", "trigger": uc["trigger"], "steps": uc["main_flow"],
                            "expected_result": uc["postconditions"], "source_location": uc["source_location"]}]
        branch_occurrences = {}
        for s in value["scenarios"]:
            refs = s["source_refs"]
            identity = fingerprint(s)
            occurrence = branch_occurrences.get(identity, 0)
            branch_occurrences[identity] = occurrence + 1
            uc["scenarios"].append({**s, "scenario_id": stable_id("BRANCH", uc["use_case_id"], identity, occurrence),
                "source_location": _location(refs), "steps": [{"step_index": i+1, "text": text,
                    "source_location": _location(refs)} for i, text in enumerate(s["steps"])]})
        uc["generation_constraints"] = []
        constraint_occurrences = {}
        for s in value["constraints"]:
            refs = s["source_refs"]
            target_name = s.get("check_target_name") or uc["architecture"]["sr"]["service_name"]
            target_id = next((n["node_id"] for n in nodes if n["name"] == target_name), "")
            identity = fingerprint(s)
            occurrence = constraint_occurrences.get(identity, 0)
            constraint_occurrences[identity] = occurrence + 1
            uc["generation_constraints"].append({**s, "constraint_id": stable_id("RULE", uc["use_case_id"], identity, occurrence),
                "check_node_id": target_id, "source_location": _location(refs)})
        arch = uc.get("architecture", {})
        for component in arch.get("ar", []):
            component["dependencies"] = []
            # Old inaccurate invented defaults must not survive independent extraction.
            component.pop("database_action", None)
            component.pop("external_dependency_node_id", None)
        for dep in value["dependencies"]:
            original_dep = copy.deepcopy(dep)
            dep = dict(dep)
            dep["caller_name"], dep["target_name"] = canonical_name(dep["caller_name"]), canonical_name(dep["target_name"])
            refs = dep["source_refs"]
            # Actor -> System business requests are already represented by RR.
            if any(n["name"] == dep["caller_name"] and n["kind"] == "human_actor" for n in nodes):
                continue
            if any(n["name"] == dep["target_name"] and n["kind"] == "human_actor" for n in nodes):
                arch.setdefault("human_interactions", []).append({**original_dep,
                    "mapping_basis": "已声明的人类参与者交互，保留于 RR；不是外部服务依赖"})
                continue
            if dep["direction"] == "outgoing" and dep["target_name"] == model["system_name"]:
                arch.setdefault("facade_returns", []).append({**original_dep,
                    "mapping_basis": "实现返回既有系统门面，保留响应证据；不是新增服务调用"})
                continue
            if dep["direction"] == "incoming":
                external_sender = next((n for n in nodes if n["name"] == dep["caller_name"]
                                        and n["kind"] == "external_service"), None)
                if external_sender:
                    dep["target_name"], dep["caller_name"] = dep["caller_name"], arch.get("ar", [{}])[0].get("microservice_name")
                    dep["target_kind"] = "external_service"
            # A System/facade -> local implementation call is the existing
            # SR/AR dispatch, not a new service-to-itself dependency.
            local_target = next((a for a in arch.get("ar", [])
                                 if a.get("microservice_name") == dep["target_name"]), None)
            if (dep["direction"] == "outgoing" and local_target and dep["caller_name"] in
                    {model["system_name"], arch.get("sr", {}).get("service_name")}):
                local_target["dispatch_source_refs"] = refs
                continue
            caller = next((a for a in arch.get("ar", []) if a.get("microservice_name") == dep["caller_name"]), None)
            caller_node = next((n for n in nodes if n["name"] == dep["caller_name"]
                                and n["kind"] == "internal_service"), None)
            if caller is None:
                # The requirement System delegates to the UC implementation.
                if dep["caller_name"] in {"在线商城系统", model["system_name"], "system",
                    arch.get("sr", {}).get("service_name")} and arch.get("ar"):
                    caller = arch["ar"][0]
                else:
                    if caller_node and arch.get("ar"):
                        caller = arch["ar"][0]
                        dep["caller_node_id"] = caller_node["node_id"]
                    else:
                        raise ValueError(f"dependency caller {dep['caller_name']} not mapped to this UC implementation")
            local_target = next((a for a in arch.get("ar", [])
                if a.get("microservice_name") == dep["target_name"]), None)
            target = (local_target["microservice_id"] if local_target and dep["target_kind"] == "internal_service"
                      else node(dep["target_name"], dep["target_kind"], refs))
            local_node = dep.get("caller_node_id") or caller["microservice_id"]
            caller["dependencies"].append({**dep, "target_node_id": target, "source_location": _location(refs),
                                            "extracted_dependency": original_dep})
            edge = {"edge_id": stable_id("EDGE", uc["use_case_id"], local_node, target,
                    dep["operation"], dep["direction"]), "from_node": local_node if dep["direction"] == "outgoing" else target,
                    "to_node": target if dep["direction"] == "outgoing" else local_node,
                    "relation": "calls" if dep["direction"] == "outgoing" else "callback", "use_case_id": uc["use_case_id"],
                    "source_location": _location(refs), "source_refs": refs}
            model["system_composition"]["edges"].append(edge)
    model["interfaces"] = [dict(i, source_location=i.get("source_location", "").replace("功能设计Delta_spec.md", "功能设计_spec.md"))
                           for i in model.get("interfaces", [])]
    for uc in model["use_cases"]:
        for rule in uc["generation_constraints"]:
            name = canonical_name(rule.get("check_target_name", ""))
            arch = uc["architecture"]
            local = next((a for a in arch.get("ar", []) if a.get("microservice_name") == name), None)
            rule["check_node_id"] = (local["microservice_id"] if local else system["node_id"]
                if name == model["system_name"] else next((n["node_id"] for n in nodes if n["name"] == name), ""))
            rule["check_mapping_status"] = "mapped" if rule["check_node_id"] else "needs_confirmation"
    for n in nodes:
        if n.get("kind") == "internal_database" and n["node_id"].startswith("NODE-"):
            n["model_role"] = "logical_data_resource"
            n["deployment_status"] = "not_a_new_deployment_component"
    result = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    # Normalization preserves extension fields; protect this contract.
    result["generator_provenance"] = model["generator_provenance"]
    result["complete"] = True
    return result
