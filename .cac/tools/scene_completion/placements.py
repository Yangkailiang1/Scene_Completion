"""Architecture evidence confidence and proposed concern check locations."""
from __future__ import annotations

from html import escape
from pathlib import Path
import textwrap

from .concerns import CONCERN_DEFINITIONS
from .semantic_backend import read_json, write_json
from .sources import fingerprint
from .schemas import stable_id


def validate_architecture_review(calls, review):
    if (review.get("input_hash") != fingerprint(calls) or review.get("model") != "gpt-6-luna"
            or review.get("reasoning_effort") != "max"):
        raise ValueError("architecture evidence review differs from its inputs or required reviewer")
    decisions = review.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != len(calls):
        raise ValueError("architecture evidence review omitted relationships")
    by_index = {}
    for decision in decisions:
        index = decision.get("call_index")
        if (type(index) is not int or not 0 <= index < len(calls) or index in by_index or
                decision.get("status") not in {"confirmed", "needs_confirmation"} or
                not isinstance(decision.get("reason"), str) or not decision["reason"].strip()):
            raise ValueError("invalid architecture evidence decision")
        by_index[index] = decision
    return by_index


def annotate_composition_evidence(composition, architecture):
    by_id = {c["model_edge_id"]: c for c in architecture["calls"]}
    for edge in composition.get("edges", []):
        if edge.get("edge_id") in by_id:
            call = by_id[edge["edge_id"]]
            edge["evidence_status"] = call["evidence_status"]
            edge["evidence_assessment"] = call["evidence_assessment"]
    composition["call_evidence_review"] = {k: architecture[k] for k in
        ("dependency_claims_hash", "evidence_review_complete", "confirmed_call_count", "pending_call_count")}
    return composition


def export_placements(model, generated, output, evidence_review=None):
    root = Path(output)
    nodes = {n["node_id"]: n for n in model["system_composition"]["nodes"]}
    original = set(model.get("generator_provenance", {}).get("baseline_node_ids", nodes))
    added = [n for nid, n in nodes.items() if nid not in original]
    calls = []
    for uc in model["use_cases"]:
        for owner in uc["architecture"].get("ar", []):
            for dep in owner.get("dependencies", []):
                local = dep.get("caller_node_id") or owner["microservice_id"]
                peer = dep["target_node_id"]
                calls.append({"use_case_id": uc["use_case_id"], "use_case_name": uc["use_case_name"],
                    "caller_node_id": local if dep["direction"] == "outgoing" else peer,
                    "target_node_id": peer if dep["direction"] == "outgoing" else local,
                    "operation": dep["operation"], "direction": dep["direction"],
                    "source_step_index": dep["source_step_index"], "source_refs": dep.get("source_refs", []),
                    "source_location": dep.get("source_location", "章节未定位"),
                    "association_change": "existing_components" if local in original and peer in original else "includes_new_model_resource"})
    claims_hash = fingerprint(calls)
    review_file = root / "architecture_evidence_review.json"
    if evidence_review is None and review_file.exists():
        evidence_review = read_json(review_file)
    decisions = validate_architecture_review(calls, evidence_review) if evidence_review is not None else {}
    for index, call in enumerate(calls):
        decision = decisions.get(index, {})
        call["evidence_status"] = decision.get("status", "not_audited")
        call["evidence_assessment"] = decision.get("reason", "抽取的来源关联尚未独立核实；不宣称原文明示直接调用")
        local = call["target_node_id"] if call["direction"] == "incoming" else call["caller_node_id"]
        peer = call["caller_node_id"] if call["direction"] == "incoming" else call["target_node_id"]
        call["model_edge_id"] = stable_id("EDGE", call["use_case_id"], local, peer, call["operation"], call["direction"])
    mounts = [{k: s.get(k) for k in ("scenario_id", "use_case_id", "candidate_id", "constraint_id",
        "concern_keys", "subject_node_id", "check_target_name", "source_step_index", "exchange_id",
        "generation_status", "trace_mapping_status", "trace_mapping_reason", "source_refs",
        "implementation_owner_names", "mount_proposal")}
        for s in generated["scenarios"] if s["scenario_type"] == "concern_derived_exception"]
    changes = {"complete": True, "source_hash": model.get("generator_provenance", {}).get("source_hash"),
        "added_documented_components": [n for n in added if n.get("source_refs") and n.get("kind") == "internal_service"],
        "added_logical_resources": [n for n in added if n.get("model_role") == "logical_data_resource"],
        "calls": calls, "dependency_claims_hash": claims_hash, "evidence_review_complete": bool(evidence_review),
        "confirmed_call_count": sum(c["evidence_status"] == "confirmed" for c in calls),
        "pending_call_count": sum(c["evidence_status"] != "confirmed" for c in calls), "concern_mounts": mounts,
        "note": "数据表为逻辑资源；框架抽象服务为分析视图，不表示新增部署。缺少 SSD 对应交换时保留业务检查位置并明确待确认。"}
    write_json(root / "architecture_changes.json", changes)
    lines = [f"# {model['system_name']}：架构与关注点检查挂载", "", changes["note"], "",
        f"- 抽取关联 {len(calls)} 条：原文明示 {changes['confirmed_call_count']} 条；待确认 {changes['pending_call_count']} 条。",
        f"- 来源约束 {sum(m['generation_status'] == 'constraint_instantiation' for m in mounts)} 条；"
        f"{sum(bool(m.get('mount_proposal')) for m in mounts)} 条尚无精确 SSD 交换，保留责任方和待确认检查位置。", "",
        "## 有证据的组件补充", ""]
    for n in changes["added_documented_components"]:
        lines.append(f"- {n['name']}（{n['node_id']}）：{n.get('source_location', '')}")
    if not changes["added_documented_components"]:
        lines.append("- 无新增有文档证据的部署服务组件。")
    lines += ["", "## 调用与回调关联", "", "|用例/步骤|调用方 → 被调用方|操作|来源|证据状态与依据|", "|---|---|---|---|---|"]
    for c in calls:
        refs = "；".join(f"{r['document']}:{r['line_start']}-{r['line_end']}" for r in c["source_refs"]) or c["source_location"]
        lines.append(f"|{c['use_case_id']}/{c['source_step_index']}|{nodes[c['caller_node_id']]['name']} → {nodes[c['target_node_id']]['name']}|{c['operation'].replace('|', '/')}|{refs}|{c['evidence_status']}：{c['evidence_assessment'].replace('|', '/')}|")
    lines += ["", "## 检查位置与关注点", "", "|用例/步骤|检查对象|关注点|SSD 交换/定位状态|已有实现组件/待确认挂载|来源|", "|---|---|---|---|---|---|"]
    for m in mounts:
        name = nodes.get(m["subject_node_id"], {}).get("name") or m.get("check_target_name") or "对象未定位"
        labels = "；".join(CONCERN_DEFINITIONS[k]["label"] + f" ({k})" for k in m["concern_keys"])
        refs = "；".join(f"{r['document']}:{r['line_start']}-{r['line_end']}" for r in m["source_refs"])
        owners = "、".join(m.get("implementation_owner_names") or [])
        proposal = "（检查步骤待确认）" if m.get("mount_proposal") else ""
        lines.append(f"|{m['use_case_id']}/{m['source_step_index']}|{name}|{labels}|{m['exchange_id'] or m.get('trace_mapping_status')}|{owners}{proposal}|{refs}|")
    (root / "concern_placements.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Separate physical-call view: the existing overview depicts participation.
    width, row_height = 1400, 136
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{120 + len(calls)*row_height}" viewBox="0 0 {width} {120 + len(calls)*row_height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#2563eb"/></marker></defs>',
        f'<text x="30" y="32" font-size="22" font-family="Microsoft YaHei,sans-serif">{escape(model["system_name"])}：依赖调用与待确认关联</text>',
        '<text x="30" y="62" font-size="14" font-family="Microsoft YaHei,sans-serif">蓝色：已有组件；橙色：新文档组件；灰色：逻辑资源。实线：原文明示；虚线：待确认，不代表实际调用。</text>']
    for i, call in enumerate(calls):
        y = 100 + i*row_height
        svg.append(f'<g data-use-case="{escape(call["use_case_id"])}"><title>{escape(str(call))}</title>')
        svg.append(f'<text x="24" y="{y+16}" font-size="14" font-family="Microsoft YaHei,sans-serif">{escape(call["use_case_id"])} / 步骤 {call["source_step_index"]}</text>')
        for x, key in ((255, "caller_node_id"), (1060, "target_node_id")):
            n = nodes[call[key]]
            fill = "#f1f5f9" if n.get("kind") == "internal_database" else "#fff1df" if n["node_id"] not in original else "#eaf2ff"
            svg.append(f'<rect data-node-id="{escape(n["node_id"])}" x="{x}" y="{y}" width="300" height="56" rx="8" fill="{fill}" stroke="#64748b"/>')
            for j, text in enumerate(textwrap.wrap(n["name"], 29)[:2]):
                svg.append(f'<text x="{x+12}" y="{y+23+j*20}" font-size="15" font-family="Microsoft YaHei,sans-serif">{escape(text)}</text>')
        dash = ' stroke-dasharray="8 6"' if call["evidence_status"] != "confirmed" else ""
        svg.append(f'<line x1="558" y1="{y+28}" x2="1055" y2="{y+28}" stroke="#2563eb" stroke-width="2"{dash} marker-end="url(#arrow)"/>')
        operation_lines = textwrap.wrap(call["operation"], 53, break_long_words=False, break_on_hyphens=False)
        visible_lines = operation_lines[:2]
        if len(operation_lines) > 2:
            visible_lines[-1] += "…"
        for j, text in enumerate(visible_lines):
            svg.append(f'<text x="565" y="{y+64+j*19}" font-size="13" font-family="Microsoft YaHei,sans-serif">{escape(text)}</text>')
        source = call["source_refs"][0] if call["source_refs"] else None
        location = f"{source['document']}:{source['line_start']}-{source['line_end']}" if source else call["source_location"]
        state = "原文明示" if call["evidence_status"] == "confirmed" else "待确认关联"
        svg.append(f'<text x="255" y="{y+118}" font-size="12" font-family="Microsoft YaHei,sans-serif">来源：{escape(location)}；{call["direction"]}；{state}</text></g>')
    svg.append("</svg>")
    (root / "architecture_calls.svg").write_text("\n".join(svg), encoding="utf-8")
    return changes
