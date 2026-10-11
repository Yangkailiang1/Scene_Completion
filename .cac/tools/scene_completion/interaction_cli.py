"""Resumable RR/SR pipeline, with an explicit source-backed architecture gate."""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

from . import interaction_batches as batches
from .interaction_metrics import compare, adoption
from .interaction_protocol import PROTOCOL, baseline, build_ssd, route_mounts, validate_generated, skill_text
from .interaction_reports import coverage_diagnosis, export, refs_text, write_diagrams
from .schemas import stable_id
from .semantic_backend import collect_packets, read_json, run_agent_packets, write_json, prepare_packets
from .sources import fingerprint, index_sources


def versions():
    directory = Path(__file__).parent
    files = sorted(directory.glob("interaction_*.py")) + [directory / n for n in
        ("semantic_backend.py", "luna_subprocess.py", "role_cli.py", "sources.py", "schemas.py", "document_extract.py", "review.py", "assessment.py")]
    result = {p.name: hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest() for p in files}
    skills = directory.parents[1] / "skills"
    result["skill_hash"] = fingerprint(skill_text())
    for name in ("scene-extract", "scene-ssd", "scene-generate", "scene-check", "scene-recommend", "scenario-match", "dependency-graph", "test-scenario-extract", 'scene-assess', 'scene-participants'):
        for path in sorted((skills / name).rglob("*.md")):
            result["skill:" + path.relative_to(skills).as_posix()] = fingerprint(path.read_text(encoding="utf-8"))
    return result


def canonical_actor(name):
    # Explicit ACT annotations are identity metadata, not scenario similarity.
    match = re.fullmatch(r"ACT-\d+[（(]([^）)]+)[）)]", name.strip())
    return match[1] if match else name.strip()


def source_index(args):
    rr = getattr(args, "rr_spec_document", None) or getattr(args, "requirement_document", None) or []
    sr = getattr(args, "sr_spec_document", None) or getattr(args, "design_document", None) or []
    if not rr or not sr or getattr(args, "spec_document", None):
        raise ValueError("new protocol requires explicit RR and SR inputs; legacy spec-document is ambiguous")
    if set(map(str, rr)) & set(map(str, sr)):
        raise ValueError("one document cannot serve as both RR and SR")
    index = index_sources(rr + sr)
    names = {Path(p).name for p in rr}
    for document in index["documents"]:
        document["requirement_layer"] = "RR" if document["document"] in names else "SR"
    index["schema_version"] = PROTOCOL
    return index


def merge_model(results, base, index):
    policies = {r.get('query_data_policy') for r in results}
    if len(policies) != 1:
        raise ValueError('cannot merge normal models from different query data policies')
    nodes, use_cases, gaps = {}, [], []
    for result in results:
        component_ids, prepared = {}, []
        for raw in result["components"]:
            node = copy.deepcopy(raw)
            if node["layer"] == "SR" and node["kind"] in {"abstract_service", "internal_service"}:
                node["original_kind"] = node["kind"]
                node["kind"] = "internal_service"
            node["name"] = canonical_actor(node["name"]) if node["kind"] in {"human_actor", "external_service", "external_actor", "external_llm"} else node["name"]
            from .interaction_resources import physical_identity
            canonical, physical = physical_identity(node, index)
            if physical:
                node['source_aliases'] = [node['name']]
                node['name'] = canonical
                node['physical_identity'] = physical
            nid = (stable_id('NODE', node['name'], node['kind'], node['layer'], fingerprint(physical['documents']))
                if physical else stable_id('NODE', node['name'], node['kind'], node['layer']))
            if node.get('boundary_role'):
                # The same system display name can denote two distinct logical
                # interaction boundaries without adding deployment components.
                nid = stable_id('NODE', node['name'], node['kind'], node['layer'], node['boundary_role'])
            node["node_id"] = nid
            component_ids[raw["component_id"]] = nid
            prepared.append(node)
        for node in prepared:
            nid = node["node_id"]
            if node.get("physical_resource_id"):
                if node["physical_resource_id"] not in component_ids:
                    raise ValueError("resource facade references an unknown physical component")
                node["physical_resource_id"] = component_ids[node["physical_resource_id"]]
            if nid in nodes:
                # Merge only the same explicit component identity, preserving sources.
                nodes[nid]["source_refs"] = list({fingerprint(r): r for r in nodes[nid]["source_refs"] + node["source_refs"]}.values())
                nodes[nid]["service_types"] = sorted(set(nodes[nid].get("service_types", [])) | set(node.get("service_types", [])))
                if node.get('physical_identity'):
                    nodes[nid]['source_aliases'] = sorted(set(nodes[nid].get('source_aliases', [])) | set(node['source_aliases']))
            else:
                nodes[nid] = node
        exchanges = []
        for raw in result["exchanges"]:
            e = copy.deepcopy(raw)
            e["from_node"], e["to_node"] = component_ids[e.pop("from_component_id")], component_ids[e.pop("to_component_id")]
            exchanges.append(e)
        scenarios = []
        for position, raw in enumerate(result["normal_scenarios"]):
            scene = copy.deepcopy(raw)
            scene.update({"use_case_id": result["use_case_id"], "scenario_id": stable_id("NORMAL", result["use_case_id"], scene["requirement_layer"], position, scene["name"]), "concern_keys": []})
            scenarios.append(scene)
        use_cases.append({"use_case_id": result["use_case_id"], "use_case_name": result["use_case_name"],
            "use_case_hierarchy": result["use_case_hierarchy"], "exchanges": exchanges,
            "normal_scenarios": scenarios, "implementation_references": result["implementation_references"],
            "pending_details": result["pending_details"],
            'participants': [{'node_id': node['node_id'], 'name': node['name'], 'layer': node['layer'],
                'source_refs': node['source_refs'], 'origin': 'normal_interaction_endpoints'}
                for node in prepared if any(node['node_id'] in {e['from_node'], e['to_node']} for e in exchanges)]})
        gaps.extend({**gap, "use_case_id": result["use_case_id"], "gap_id": stable_id("GAP", result["use_case_id"], fingerprint(gap))} for gap in result["model_gaps"])
    expected = {u["use_case_id"] for u in base["use_cases"]}
    if len(results) != len(expected) or {r["use_case_id"] for r in results} != expected:
        raise ValueError("generator model use-case universe is incomplete")
    return {"protocol": PROTOCOL, **({'query_data_policy': next(iter(policies))} if next(iter(policies)) else {}), "source_hash": fingerprint(index), "nodes": list(nodes.values()),
        "use_cases": use_cases, "model_gaps": gaps, "generator_input_method": "source-normal-flow-ssd-only"}


def architecture_proposals(model, base):
    """Authorized boundaries and database facades are exempt; other additions wait."""
    known = {(n["name"], n["kind"], n.get("layer")) for n in base.get("system_composition", {}).get("nodes", [])}
    known_external_actors = {canonical_actor(n['name']) for n in base.get('system_composition', {}).get('nodes', [])
        if n.get('kind') in {'external_service', 'external_actor', 'external_llm'}}
    known_services = set()
    for uc in base["use_cases"]:
        hints = uc.get("architecture", {}).get("sr", {})
        for hint in hints if isinstance(hints, list) else [hints]:
            if hint.get("service_name"):
                known_services.add((hint["service_name"], "SR"))
            if hint.get('abstract_api_id'):
                # An existing SR interface identity is a service-role alias,
                # not a newly discovered deployment component.
                known_services.add((hint['abstract_api_id'], 'SR'))
    proposals = []
    for node in model["nodes"]:
        if node.get("boundary_role") in {"ui", "receiver"} or node["kind"] in {"internal_database", "external_database"}:
            continue
        identity = (node["name"], node["kind"], node["layer"])
        # Abstract service and internal service aliases describe the same SR node.
        already_known = (identity in known or ((node["name"], node["layer"]) in known_services and node["kind"] in {"abstract_service", "internal_service"})
            or (node['layer'] == 'RR' and node['kind'] in {'external_service', 'external_actor', 'external_llm'}
                and node['name'] in known_external_actors))
        if not already_known:
            proposals.append({"proposal_id": stable_id("PROPOSAL-NODE", *identity), "kind": "component_or_layer_mapping",
                "description": f'{node["name"]}：{node["kind"]} / {node["layer"]}',
                "source_refs": node["source_refs"], "node_id": node["node_id"],
                "impact": "更改架构组件或层级映射；可能增加该层交互和关注点挂载"})
    nodes = {n["node_id"]: n for n in model["nodes"]}
    for uc in model["use_cases"]:
        for e in uc["exchanges"]:
            source, target = nodes[e["from_node"]], nodes[e["to_node"]]
            # Already-authorized boundary-to-SR expansion and database service wrapping.
            if e["requirement_layer"] == "RR" or source.get("boundary_role") or target.get("boundary_role") or target["kind"] in {"internal_database", "external_database"}:
                continue
            proposals.append({"proposal_id": stable_id("PROPOSAL-EDGE", uc["use_case_id"], e["local_id"], source["name"], target["name"]),
                "kind": "sr_call_edge", "use_case_id": uc["use_case_id"],
                "description": f'{source["name"]} → {target["name"]}：{e["operation"]}',
                "source_refs": e["source_refs"], "local_exchange_id": e["local_id"],
                "impact": "纳入 SR 调用关系和依赖关注点分析；不更改原始需求"})
    return proposals


def write_pending(root, proposals, gaps, model_hash):
    write_json(root / "architecture_proposals.json", {"model_hash": model_hash, "proposals": proposals, "model_gaps": gaps,
        "authorization_note": "用户要求：其他组件、调用边或关注点的增删须先确认。边界与数据库服务化已授权。"})
    lines = ["# 需确认的架构/交互改动", "", f"模型版本：{model_hash}", "", "下列项目尚未执行异常生成或正式验收。", ""]
    for p in proposals:
        lines += [f'- {p["proposal_id"]}：{p["description"]}', f'  原文：{refs_text(p["source_refs"])}；影响：{p["impact"]}']
    for gap in gaps:
        lines.append(f'- {gap["gap_id"]}：{gap["description"]}；{refs_text(gap["source_refs"])}')
    (root / "architecture_proposals.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args):
    from .role_cli import _client
    if (getattr(args,'match_backend','agent') != 'agent'
            or getattr(args,'recommend_backend','agent') != 'agent' or getattr(args,'rerank',False)):
        raise ValueError('new formal protocol currently requires agent backends and rerank off; legacy command retains other backends')
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    index = source_index(args)
    base = read_json(args.model)
    # Keep only identity and architecture hints, not historical scene collections.
    base = {"use_cases": [{k: u[k] for k in ("use_case_id", "use_case_name", "architecture", "source_use_case_ids") if k in u} for u in base["use_cases"]],
        "system_composition": {"nodes": base.get("system_composition", {}).get("nodes", [])}}
    from .interaction_scope import assessment_base, select_cases
    selected = getattr(args, 'use_case_id', None)
    selected_exchanges = getattr(args, 'exchange_local_id', None)
    if selected_exchanges and (not selected or len(selected) != 1):
        raise ValueError('interaction-chain scope requires one explicit representative use case')
    scoped_base = assessment_base(base, selected)
    quality_gate=getattr(args,'source_quality_gate','strict')
    if quality_gate=='structural' and not selected:
        raise ValueError('structural workflow validation requires an explicit representative use-case scope')
    write_json(root / "generator_base_identity.json", base)
    from .interaction_metrics import EVALUATION_POLICY
    manifest = {"protocol": PROTOCOL, 'evaluation_policy': EVALUATION_POLICY,
        'evaluation_scope': {'kind': 'representative' if selected else 'full',
            'use_case_ids': selected or [u['use_case_id'] for u in base['use_cases']],
            'full_source_use_case_count': len(base['use_cases'])},
        'comparison_verification': getattr(args, 'comparison_verification', 'all'),
        'source_quality_gate':quality_gate,
        "complete": False, "accepted": False,
        "source_hash": fingerprint(index), "tool_versions": versions(), "stages": {},
        "model": "ecnu-max", "max_concurrency": 3, "rerank": args.rerank}
    if selected_exchanges:
        manifest['evaluation_scope'].update(exchange_local_ids=selected_exchanges,
            granularity='interaction_chain', original_case_denominators_retained=True)
    write_json(root / "sources_index.json", index)
    write_json(root / "concern_baseline.json", baseline())
    # Clear visibility of prior formal outputs before a resumed incomplete run.
    for name in ("metrics.json", "scene_assessment.xlsx", "report.md", "acceptance.json", "assessment_status.json"):
        (root / name).unlink(missing_ok=True)
    client = _client(args, root)
    manifest['model'] = client.model('agent')
    manifest['execution_runtime'] = getattr(args, 'agent_runtime', None) or client.config.get('agent_runtime', 'ecnu')
    client.config.setdefault("timeout_seconds", 600)
    client.config.setdefault("max_concurrency", 3)
    manifest["execution_config"] = {k: client.config.get(k, default) for k, default in
        (("timeout_seconds", 600), ("max_retries", 2), ("semantic_max_attempts", 4), ("max_tokens", 12000), ("max_concurrency", 3))}
    manifest["execution_config"].update(thinking=bool(client.config.get("thinking")), reasoning_effort=client.config.get("reasoning_effort") if client.config.get("thinking") else None)
    if manifest['execution_runtime'] == 'luna-subprocess':
        manifest['execution_config']['native_transport'] = client.config.get('native_transport', 'auto')
        manifest['execution_config']['native_structured_audit'] = client.config.get('native_structured_audit', False)
    if args.agent_mode == "external" and client.model("agent") not in {'ecnu-max', 'gpt-6-luna'}:
        raise ValueError("this experiment requires an authorized ecnu-max or Luna execution runtime")
    # Expose the actual input/runtime before a long first batch starts. A
    # partial running experiment must be inspectable without claiming results.
    write_json(root / "run_manifest.json", manifest)

    def stage(name, prepare, validator, source_context=None):
        directory = root / "batches" / name
        prepare(directory)
        manifest["stages"][name] = {"complete": False,
            "status": "running" if args.agent_mode == "external" else "prepared",
            "batch_count": len(read_json(directory / "manifest.json")["batches"])}
        write_json(root / "run_manifest.json", manifest)
        if args.agent_mode == "external":
            run_agent_packets(directory, client, validator)
        values, status = collect_packets(directory, validator)
        manifest["stages"][name] = status
        write_json(root / "run_manifest.json", manifest)
        print(name + ": " + ("complete" if status["complete"] else "pending"), flush=True)
        if status["complete"]:
            execution_evidence = []
            for batch in read_json(directory / "manifest.json")["batches"]:
                result = read_json(directory / "results" / (batch["batch_id"] + ".json"))
                evidence = result.get("execution_model_evidence", {})
                from .interaction_execution_identity import validate_result_execution
                validate_result_execution(result, result_path=directory / 'results' / (batch['batch_id'] + '.json'))
                execution_evidence.append({"batch_id": batch["batch_id"], "evidence": evidence})
            status["execution_evidence_hash"] = fingerprint(execution_evidence)
            status['actual_models'] = sorted({v['evidence']['requested_model'] for v in execution_evidence})
            status['actual_reasoning_configurations'] = sorted({
                (v['evidence']['requested_model'], bool(v['evidence'].get('thinking')),
                    v['evidence'].get('reasoning_effort') or '') for v in execution_evidence})
            status["provider_models"] = sorted({v["evidence"].get("provider_model") for v in execution_evidence if v["evidence"].get("provider_model")})
            status["provider_identity_complete"] = all(v["evidence"].get("provider_model") for v in execution_evidence)
            write_json(root / "run_manifest.json", manifest)
        return values if status["complete"] else None

    try:
        values = stage("interaction-model", lambda d: batches.model_packets(base, index, d), batches.model_validator(index))
        model = None
        pending = []
        approval = {}
        if values is not None:
            model = merge_model(select_cases(values, selected), scoped_base, index)
            write_json(root / 'scene_model.json', model)
            from .interaction_origins import audit_model_origins
            origin_audit = audit_model_origins(model, index)
            write_json(root / 'model_origin_checks.json', origin_audit)
            manifest['pending_model_origin_checks'] = [c for c in origin_audit['checks'] if not c['passed']]
            proposals = architecture_proposals(model, base)
            model_hash = fingerprint(model)
            write_pending(root, proposals, model['model_gaps'], model_hash)
            approval_file = getattr(args, 'architecture_approval', None)
            approval = read_json(approval_file) if approval_file else {}
            valid_approval = approval.get('model_hash') == model_hash
            pending = [p for p in proposals if not valid_approval or p['proposal_id'] not in approval.get('approved_proposal_ids', [])]
            manifest.update(pending_architecture_confirmation=pending, model_gaps=model['model_gaps'])
            write_json(root / 'run_manifest.json', manifest)
            from .interaction_model_audit import model_audit_packets, model_audit_validator
            model_review = stage('interaction-model-audit', lambda d: model_audit_packets(root / 'batches/interaction-model', index, d, use_case_ids=selected), model_audit_validator(index))
            manifest['pending_normal_graph_review'] = model_review is None or (quality_gate=='strict' and not all(r['passed'] for r in model_review))
            manifest['source_quality_passed'] = model_review is not None and all(r['passed'] for r in model_review)
            manifest['source_quality_findings_retained'] = model_review is not None and not manifest['source_quality_passed']
            if model_review is not None:
                write_json(root / 'model_source_audit.json', {'complete': True,
                    'passed': all(r['passed'] for r in model_review), 'items': model_review})
                origin_audit = audit_model_origins(model, index, model_review)
                write_json(root / 'model_origin_checks.json', origin_audit)
                manifest['pending_model_origin_checks'] = [c for c in origin_audit['checks'] if not c['passed']]
            from .interaction_graph_checks import check_graph_anchors
            graph_checks = check_graph_anchors(model, index, model_review)
            write_json(root / 'model_graph_checks.json', graph_checks)
            manifest['pending_model_graph_checks'] = graph_checks['checks']
            from .interaction_participants import participant_packets, participant_validator, write_participants
            # Optional participant evidence depends on a complete, passing
            # normal-source audit. Do not spend external calls on a graph
            # already known to need re-extraction. C still runs independently.
            actors = None
            if not manifest['pending_normal_graph_review']:
                actors = stage('interaction-participants', lambda d: participant_packets(root / 'batches/interaction-model', index, d, use_case_ids=selected), participant_validator(index))
            else:
                manifest['stages']['interaction-participants'] = {
                    'complete': False, 'status': 'awaiting_normal_source_audit',
                    'reason': 'Normal graph source audit must be complete and passed before participant reconciliation.'}
            manifest['pending_participant_checks'] = actors is None or not all(r['passed'] for r in actors)
            if actors is not None:
                write_participants(root, actors)
            write_json(root / 'run_manifest.json', manifest)
        # Checker independence is preserved even while architecture confirmation is pending.
        if getattr(args, "checker_input", None):
            from .interaction_baseline import import_baseline
            manifest["checker_baseline_import"] = import_baseline(args.checker_input, root, index, base, retain_source_packets=True)
        checker_prepare = (lambda d: read_json(d/'manifest.json')) if manifest.get('checker_baseline_import') else (lambda d: batches.checker_packets(base, index, d))
        checked = stage("interaction-checker", checker_prepare, batches.checker_validator(index))
        if checked is not None:
            from .interaction_audit import checker_audit_packets, checker_audit_validator
            audit = stage("interaction-checker-audit", lambda d: checker_audit_packets(root / "batches/interaction-checker", index, d), checker_audit_validator(index))
            if audit is None:
                return manifest, 2 if args.agent_mode == "external" else 0
            write_json(root / "checker_source_audit.json", {"complete": True,
                "passed": all(row["passed"] for row in audit), "items": audit})
            if not all(row["passed"] for row in audit):
                manifest["pending_checker_source_review"] = [r for r in audit if not r["passed"]]
                write_json(root / "run_manifest.json", manifest)
                return manifest, 2
            checker = {"protocol": PROTOCOL, "complete": True, "source_hash": fingerprint(index),
                "scenarios": checked, "baseline_hash": fingerprint(checked)}
            frozen = root / "existing_scenarios.json"
            if frozen.exists() and read_json(frozen) != checker:
                raise ValueError("frozen checker baseline changed; start a new documented round")
            write_json(frozen, checker)
            if not manifest.get('checker_baseline_import'):
                from .interaction_baseline import record_source_review
                record_source_review(root, index)
        if values is None or checked is None:
            return manifest, 2 if args.agent_mode == "external" else 0
        # Acknowledgement alone cannot repair missing/contradictory model evidence.
        if pending or model["model_gaps"] or manifest.get('pending_model_origin_checks') or manifest.get('pending_normal_graph_review') or manifest.get('pending_model_graph_checks') or manifest.get('pending_participant_checks'):
            manifest.update({"pending_architecture_confirmation": pending, "model_gaps": model["model_gaps"],
                "checker_counts": {layer: sum(s["requirement_layer"] == layer for s in checked) for layer in ("RR", "SR")}})
            write_json(root / "run_manifest.json", manifest)
            return manifest, 2
        write_json(root / "model_authorization.json", {"model_hash": model_hash,
            "approved_proposal_ids": approval.get("approved_proposal_ids", []), "proposals": proposals,
            "authorization_note": "逻辑边界/数据库包装已授权；其他新增项须由用户确认后提供本模型的 approval 文件"})
        checked = select_cases(checked, selected)
        write_json(root / 'assessment_checker_scenarios.json', {'evaluation_scope': manifest['evaluation_scope'], 'scenarios': checked,
            'source_baseline_hash': manifest.get('checker_baseline_import', {}).get('baseline_hash') or fingerprint(read_json(root/'existing_scenarios.json')['scenarios'])})
        ssd = build_ssd(model)
        mounts = route_mounts(ssd)
        from .interaction_scope import scope_mounts
        mounts = scope_mounts(ssd, mounts, selected_exchanges)
        write_json(root / "diagrams" / "ssd.json", ssd)
        write_json(root / "concern_mounts.json", mounts)
        write_diagrams(root / "diagrams", ssd, mounts)
        generated = stage("interaction-generation", lambda d: batches.generation_packets(ssd, mounts, d), batches.generation_validator(index))
        if generated is None:
            return manifest, 2
        generated += [s for uc in model["use_cases"] for s in uc["normal_scenarios"]]
        validate_generated(generated, ssd, mounts, index)
        write_json(root / "generated_scenarios.json", {"protocol": PROTOCOL, "complete": True,
            "llm_review_used": False, "source_hash": fingerprint(index), "scenarios": generated})
        pairs = stage("interaction-matching", lambda d: batches.pair_packets(generated, checked, d), batches.pair_validator)
        if pairs is None:
            return manifest, 2
        metrics = compare(generated, checked, pairs)
        write_json(root / "scenario_matches.json", {"protocol": PROTOCOL, "complete": True, "backend": "agent", "pairs": pairs,
            'assignment': metrics['assignment']})
        # Independent second pass includes accepted pairs and ALL peers of misses.
        audit_checked = checked
        audit_generated = [s for s in generated if s["scenario_type"] == "exception"]
        verify_all = manifest['comparison_verification'] == 'all'
        verified = stage("interaction-verification", lambda d: batches.pair_packets(audit_generated if verify_all else [], audit_checked if verify_all else [], d, "interaction-verification"), batches.pair_validator)
        if verified is None:
            return manifest, 2
        lookup = {(p["checker_scenario_id"], p["generated_scenario_id"]): p for p in verified}
        disagreements = [{"first": p, "independent": lookup[(p["checker_scenario_id"], p["generated_scenario_id"])]} for p in pairs if verify_all
            if batches.comparison_signature(p) != batches.comparison_signature(lookup[(p["checker_scenario_id"], p["generated_scenario_id"])])]
        if disagreements:
            write_json(root / "match_review_disagreements.json", disagreements)
            manifest["pending_match_review"] = len(disagreements)
            write_json(root / "run_manifest.json", manifest)
            return manifest, 2
        unmatched = set(metrics["layers"]["combined"]["overall"]["unmatched_generated_ids"])
        candidates = [s for s in generated if s["scenario_id"] in unmatched]
        recommendations = stage("interaction-recommendation", lambda d: batches.recommendation_packets(candidates, ssd, d, index), batches.recommendation_validator(index))
        if recommendations is None:
            return manifest, 2
        recommendations.sort(key=lambda r: (-r["confidence"], r["scenario_id"]))
        write_json(root / "recommendations.json", {"protocol": PROTOCOL, "complete": True, "items": recommendations})
        from .interaction_equivalence import equivalence_packets, equivalence_validator, recommendation_units
        equivalent = stage('interaction-equivalence', lambda d: equivalence_packets(candidates, ssd, d), equivalence_validator)
        if equivalent is None:
            return manifest, 2
        units = recommendation_units(candidates, ssd, equivalent)
        write_json(root / 'recommendation_units.json', units)
        tests = getattr(args, "test_spec_document", None) or []
        if not tests:
            raise ValueError("independent full test spec is required for adoption reporting")
        test_index = index_sources(tests)
        for document in test_index["documents"]:
            document["requirement_layer"] = "TEST"
        test_index["schema_version"] = PROTOCOL
        write_json(root / "test_sources_index.json", test_index)
        conditions = stage("interaction-test-conditions", lambda d: batches.test_packets(scoped_base, test_index, d), batches.test_validator(test_index))
        if conditions is None:
            return manifest, 2
        write_json(root / "test_conditions.json", {"protocol": PROTOCOL, "scenarios": conditions, "source_hash": fingerprint(test_index)})
        adopted_pairs = stage("interaction-adoption", lambda d: batches.pair_packets(units['units'], conditions, d, "interaction-adoption"), batches.pair_validator)
        if adopted_pairs is None:
            return manifest, 2
        adoption_result = adoption(units['units'], conditions, adopted_pairs, equivalence=units)
        write_json(root / "adoption_matches.json", {"protocol": PROTOCOL, "complete": True, "pairs": adopted_pairs})
        diagnosis = coverage_diagnosis(generated, checked, pairs, metrics, ssd, mounts)
        export(root, generated, checked, pairs, metrics, recommendations, adoption_result, diagnosis, mounts)
        manifest.update({"complete": True, "coverage_threshold_met": metrics["coverage_threshold_met"],
            "remaining_acceptance_checks": ["offline replay", "full regression", "gpt-6-luna/max effect review"],
            "formal_metrics": False, "checker_baseline_hash": fingerprint(checked),
            "generated_set_hash": fingerprint(generated), "comparison_hash": fingerprint(pairs),
            "metric_hash": fingerprint(metrics), 'recommendation_adoption': adoption_result,
            "miss_rates": {k: v["overall"]["miss_rate"] for k, v in metrics["layers"].items()}})
        write_json(root / "run_manifest.json", manifest)
        return manifest, 2
    except (ValueError, KeyError, TypeError, RuntimeError) as exc:
        manifest["error"] = str(exc)
        write_json(root / "run_manifest.json", manifest)
        raise
