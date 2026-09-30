"""Semantic use-case dependency graph and dependency-free SVG rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import ValidationFailure, validate_scene_model
from .svg_renderer import _esc, _text
from .dependency_layout import dependency_layout


def build_sr_service_dependency_graph(model: dict[str, Any], ssd_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build only evidence-backed SR dependencies; shared AR implementations are not edges."""
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    nodes_by_id = {node["node_id"]: node for node in normalized["system_composition"]["nodes"]}
    graph_nodes = []
    service_by_uc = {}
    for uc in normalized.get("use_cases", []):
        sr = (uc.get("architecture") or {}).get("sr") or {}
        sid = str(sr.get("service_id", ""))
        if sid in nodes_by_id:
            service_by_uc[uc["use_case_id"]] = sid
            graph_nodes.append({"service_id": sid, "use_case_id": uc["use_case_id"], "name": sr.get("service_name", nodes_by_id[sid].get("name", sid)), "abstract_api_id": sr.get("abstract_api_id", ""), "service_type": sr.get("service_type", "unknown")})
    edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def add(source: str, target: str, relation: str, evidence: str, source_location: str = "", use_case_id: str = "", anchor_step_index: Any = "", mapping_status: str = "confirmed") -> None:
        if source not in nodes_by_id or target not in nodes_by_id or source == target:
            return
        if nodes_by_id[source].get("layer") != "SR" or nodes_by_id[target].get("layer") != "SR":
            return
        key = (source, target, relation, use_case_id)
        edge = edges.setdefault(key, {"from_service_id": source, "to_service_id": target, "relation": relation, "mapping_status": mapping_status, "evidence": [], "source_locations": [], "use_case_ids": [], "anchor_step_indices": []})
        if edge.get("mapping_status") != mapping_status:
            edge["mapping_status"] = "inferred"
        if evidence and evidence not in edge["evidence"]: edge["evidence"].append(evidence)
        if source_location and source_location not in edge["source_locations"]: edge["source_locations"].append(source_location)
        if use_case_id and use_case_id not in edge["use_case_ids"]: edge["use_case_ids"].append(use_case_id)
        if anchor_step_index not in (None, "") and anchor_step_index not in edge["anchor_step_indices"]: edge["anchor_step_indices"].append(anchor_step_index)

    for raw in normalized.get("service_dependencies", []):
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("from_service_id") or service_by_uc.get(str(raw.get("from_use_case", "")), ""))
        target = str(raw.get("to_service_id") or service_by_uc.get(str(raw.get("to_use_case", "")), ""))
        add(source, target, str(raw.get("relation", "depends_on")), str(raw.get("evidence", "")), str(raw.get("source_location", "")), str(raw.get("use_case_id", raw.get("from_use_case", ""))), raw.get("anchor_step_index", ""), str(raw.get("mapping_status", "inferred")))

    for uc in normalized.get("use_cases", []):
        source = service_by_uc.get(uc["use_case_id"], "")
        for dep in ((uc.get("architecture") or {}).get("sr") or {}).get("dependencies", []) or []:
            if not isinstance(dep, dict): continue
            target = str(dep.get("service_id") or service_by_uc.get(str(dep.get("use_case_id", "")), ""))
            add(source, target, str(dep.get("relation", "depends_on")), str(dep.get("evidence", "")), str(dep.get("source_location", uc.get("source_location", ""))), uc["use_case_id"], dep.get("anchor_step_index", ""), str(dep.get("mapping_status", "inferred")))

    manifest_cases = (ssd_manifest or {}).get("use_cases", []) if isinstance(ssd_manifest, dict) else []
    for entry in manifest_cases:
        uc_id = str(entry.get("use_case_id", ""))
        path = ((entry.get("artifacts") or {}).get("fused") or {}).get("json", "")
        if not path: continue
        try:
            ssd = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for message in (ssd.get("fused", ssd).get("messages", []) if isinstance(ssd, dict) else []):
            if message.get("layer") != "SR" or message.get("message_kind") not in {"request", "internal_call", "event"}: continue
            source = str(message.get("from_node", "")); target = str(message.get("to_node", ""))
            if nodes_by_id.get(source, {}).get("layer") == "SR" and nodes_by_id.get(target, {}).get("layer") == "SR":
                add(source, target, "direct_call", str(message.get("message", "")), str(message.get("source_location", "")), uc_id, message.get("source_step_index", ""), "confirmed")
    return {"version": "1", "project": normalized["project"], "analysis_layer": "SR", "nodes": graph_nodes, "edges": list(edges.values()), "review_items": normalized.get("service_dependency_review_items", []), "semantics": {"shared_ar_reuse": "仅实现复用，不构成业务依赖", "non_call_relations": "由模型中的需求/设计证据表达，不补造 SSD 消息"}}


def render_sr_service_dependency_svg(graph: dict[str, Any], output_path: str | Path) -> Path:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    box_w, box_h, gap_x, gap_y, margin = 300, 72, 440, 112, 52
    known = {n["service_id"] for n in nodes}
    # A dependent service is placed to the right of its prerequisite. Edges
    # retain the semantic direction (dependent -> prerequisite) but route in
    # the horizontal channel between boxes, never through node interiors.
    rank = {node_id: 0 for node_id in known}
    for _ in range(max(1, len(nodes))):
        changed = False
        for edge in edges:
            source, target = edge.get("from_service_id"), edge.get("to_service_id")
            if source in known and target in known and rank[source] <= rank[target]:
                rank[source] = rank[target] + 1
                changed = True
        if not changed:
            break
    groups: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        groups.setdefault(rank.get(node["service_id"], 0), []).append(node)
    max_rank = max(groups, default=0)
    max_rows = max((len(group) for group in groups.values()), default=1)
    width = margin * 2 + max_rank * gap_x + box_w
    height = max(340, 112 + max_rows * gap_y)
    points: dict[str, tuple[float, float]] = {}
    for column, group in groups.items():
        for row, node in enumerate(group):
            points[node["service_id"]] = (margin + column * gap_x + box_w / 2, 90 + row * gap_y + box_h / 2)
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#fff"/>', _text(margin, 42, f"{graph.get('project','')} · SR Service 依赖关系图", 23, "bold", "#153E75")]
    body.insert(1, '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#7189AA"/></marker></defs>')
    for edge_index, edge in enumerate(edges):
        a, b = points.get(edge.get("from_service_id")), points.get(edge.get("to_service_id"))
        if not a or not b: continue
        source_x = a[0] - box_w / 2
        target_x = b[0] + box_w / 2
        middle_x = (source_x + target_x) / 2
        lane = (edge_index % 3 - 1) * 7
        body.append(f'<path d="M {source_x} {a[1]} H {middle_x} V {b[1]} H {target_x}" fill="none" stroke="#7189AA" stroke-width="1.6" marker-end="url(#arrow)"/>')
        label_x = middle_x
        label_y = (a[1] + b[1]) / 2 + lane - 5
        label = str(edge.get("relation", "depends_on")) + (" · 推断" if edge.get("mapping_status") == "inferred" else "")
        body.append(f'<rect x="{label_x-73}" y="{label_y-13}" width="146" height="19" rx="5" fill="#fff" opacity="0.94"/>')
        body.append(_text(label_x, label_y, label, 11, "normal", "#536273", "middle"))
    for node in nodes:
        center_x, center_y = points[node["service_id"]]; x = center_x - box_w / 2; y = center_y - box_h / 2
        body.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="12" fill="#E9F2FF" stroke="#356FC4" stroke-width="2"/>')
        body.append(_text(center_x, y + 26, node.get("name", ""), 15, "bold", "#22364D", "middle"))
        body.append(_text(center_x, y + 50, f"{node.get('use_case_id','')} · {node.get('service_type','unknown')}", 12, "normal", "#536273", "middle"))
    if not graph.get("edges"):
        body.append(_text(width/2, height-36, "尚无经需求/设计证据确认的 SR Service 依赖关系；请补充 service_dependencies。", 14, "normal", "#8A4B08", "middle"))
    body.append("</svg>")
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True); output.write_text("\n".join(body), encoding="utf-8")
    return output


def build_use_case_dependency_graph(model: dict[str, Any]) -> dict[str, Any]:
    """Build evidence-backed use-case dependencies from entity CRUD mappings.

    Merely sharing a database entity or AR microservice is not a dependency.
    A consumer CRUD record must explicitly cite the prerequisite use case and
    its evidence; uncertain mappings are surfaced as review items.
    """
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    ucs = normalized.get("use_cases", [])
    known = {u["use_case_id"] for u in ucs}
    operations = normalized.get("use_case_entity_operations", [])
    op_by_id = {item["operation_id"]: item for item in operations}
    edges_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    reviews: list[dict[str, Any]] = []
    covered_ucs = {operation.get("use_case_id") for operation in operations}
    for uc in ucs:
        if uc["use_case_id"] not in covered_ucs:
            reviews.append({"type": "crud_mapping_missing", "use_case_id": uc["use_case_id"], "source_location": uc.get("source_location", ""), "message": "该用例尚无实体 CRUD 映射；请根据数据读写证据补充，不能由工具猜测。"})
    for operation in operations:
        if operation.get("mapping_status") == "needs_confirmation":
            reviews.append({"type": "crud_mapping_confirmation", "operation_id": operation["operation_id"], "use_case_id": operation["use_case_id"], "entity": operation["entity"], "source_location": operation["source_location"], "message": "用例对实体的 CRUD 操作映射待确认。"})
        prerequisites = operation.get("depends_on_operations", []) or []
        if isinstance(prerequisites, str):
            prerequisites = [prerequisites]
        for prerequisite_id in prerequisites:
            producer = op_by_id.get(str(prerequisite_id))
            if not producer:
                reviews.append({"type": "crud_dependency_missing_operation", "operation_id": operation["operation_id"], "prerequisite_operation_id": prerequisite_id, "source_location": operation["source_location"], "message": "依赖引用的 CRUD 操作不存在；不生成依赖边。"})
                continue
            if producer["use_case_id"] == operation["use_case_id"]:
                continue
            if producer["entity"] != operation["entity"] or producer["operation"] not in {"C", "U"} or operation["operation"] not in {"R", "U", "D"}:
                reviews.append({"type": "crud_dependency_semantics_invalid", "operation_id": operation["operation_id"], "prerequisite_operation_id": prerequisite_id, "source_location": operation["source_location"], "message": "前置/消费操作的实体或 CRUD 语义不兼容；不生成依赖边。"})
                continue
            evidence = str(operation.get("dependency_evidence", "")).strip()
            dependency_location = str(operation.get("dependency_source_location", operation.get("source_location", ""))).strip()
            if not evidence or not dependency_location:
                reviews.append({"type": "crud_dependency_evidence_missing", "operation_id": operation["operation_id"], "prerequisite_operation_id": prerequisite_id, "source_location": operation["source_location"], "message": "CRUD 映射声明了依赖，但缺少依赖依据或来源定位；不生成依赖边。"})
                continue
            relation = str(operation.get("dependency_relation") or ("consumes_created_resource" if producer["operation"] == "C" else "consumes_updated_state"))
            key = (producer["use_case_id"], operation["use_case_id"], operation["entity"])
            edge = edges_by_key.setdefault(key, {"edge_id": "", "from_use_case": key[0], "to_use_case": key[1], "relation": relation, "entity": key[2], "mapping_status": "confirmed", "evidence": [], "source_locations": [], "crud_operation_ids": []})
            if evidence not in edge["evidence"]:
                edge["evidence"].append(evidence)
            for location in (producer["source_location"], operation["source_location"], dependency_location):
                if location and location not in edge["source_locations"]:
                    edge["source_locations"].append(location)
            for op_id in (producer["operation_id"], operation["operation_id"]):
                if op_id not in edge["crud_operation_ids"]:
                    edge["crud_operation_ids"].append(op_id)
    for index, edge in enumerate(edges_by_key.values(), 1):
        edge["edge_id"] = f"UCDEP-{index:04d}"
    # Explicit dependency declarations remain supported, but need real evidence.
    for raw in normalized.get("use_case_dependencies", []) or []:
        if not isinstance(raw, dict):
            continue
        source, target = raw.get("from_use_case"), raw.get("to_use_case")
        if source not in known or target not in known or source == target:
            reviews.append({"type": "use_case_dependency_reference_invalid", "message": f"依赖关系引用了无效用例：{source} -> {target}"})
            continue
        evidence = str(raw.get("evidence", "")).strip()
        location = str(raw.get("source_location", "")).strip()
        if not evidence or not location:
            reviews.append({"type": "use_case_dependency_evidence_missing", "from_use_case": source, "to_use_case": target, "message": "显式依赖缺少证据或来源定位，未生成依赖边。"})
            continue
        if any(edge["from_use_case"] == source and edge["to_use_case"] == target for edge in edges_by_key.values()):
            continue
        edges_by_key[(source, target, str(raw.get("entity", "")))] = {"edge_id": f"UCDEP-{len(edges_by_key)+1:04d}", "from_use_case": source, "to_use_case": target, "relation": str(raw.get("relation", "evidence_backed_dependency")), "entity": str(raw.get("entity", "")), "mapping_status": str(raw.get("mapping_status", "inferred")), "evidence": [evidence], "source_locations": [location], "crud_operation_ids": list(raw.get("crud_operation_ids", []))}
    graph_edges = list(edges_by_key.values())
    operations_by_uc_entity: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for operation in operations:
        operations_by_uc_entity.setdefault((operation["use_case_id"], operation["entity"]), []).append(operation)
    matrix = []
    for uc in ucs:
        row: dict[str, Any] = {"use_case_id": uc["use_case_id"], "use_case_name": uc.get("use_case_name", ""), "operations": {}}
        for entity in normalized.get("entities", []):
            matches = operations_by_uc_entity.get((uc["use_case_id"], entity), [])
            row["operations"][entity] = {"crud": "/".join(dict.fromkeys(item["operation"] for item in matches)), "operation_ids": [item["operation_id"] for item in matches], "mapping_status": "; ".join(dict.fromkeys(item["mapping_status"] for item in matches)), "source_locations": list(dict.fromkeys(item["source_location"] for item in matches))}
        matrix.append(row)
    graph_nodes = [{"use_case_id": u["use_case_id"], "name": u.get("use_case_name", ""), "rr_service_id": (u.get("architecture") or {}).get("rr", {}).get("service_id", "")} for u in ucs]
    layout = dependency_layout(graph_nodes, graph_edges)
    cycle_edges = set(layout["cycle_edge_ids"])
    for edge in graph_edges:
        edge["cycle_requires_review"] = edge.get("edge_id") in cycle_edges
    for component in layout["cycles"]:
        reviews.append({"type": "use_case_dependency_cycle", "use_case_ids": component, "message": "用例依赖图存在有向环；语义边已保留，布局不代表循环内部顺序，需人工复核。"})
    return {
        "version": "10", "project": normalized["project"], "nodes": graph_nodes,
        "edges": graph_edges, "layout": layout, "er_model": normalized.get("er_model", {}), "use_case_entity_operations": operations, "crud_matrix": matrix,
        "review_items": reviews,
        "semantics": {"dependency_rule": "仅当消费方 CRUD 记录显式引用同实体的前置 C/U 操作，且附有关系证据和来源定位时才生成依赖边；仅共享实体或 AR 实现不构成依赖。", "direction": "前置/生产用例 → 消费/依赖用例；表示数据生命周期或有证据的状态前置，不表示全局执行顺序。"},
    }


def validate_use_case_dependency_graph(model: dict[str, Any], graph: dict[str, Any], raise_on_error: bool = False) -> dict[str, Any]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    known = {u["use_case_id"] for u in normalized.get("use_cases", [])}
    errors = []
    for node in graph.get("nodes", []):
        if node.get("use_case_id") not in known:
            errors.append(f"dependency graph references unknown use_case_id: {node.get('use_case_id')}")
    for edge in graph.get("edges", []):
        if edge.get("from_use_case") not in known or edge.get("to_use_case") not in known:
            errors.append(f"dependency edge references unknown use case: {edge}")
    result = {"valid": not errors, "errors": errors}
    if raise_on_error and errors:
        raise ValidationFailure(errors)
    return result


def render_use_case_dependency_svg(graph: dict[str, Any], output_path: str | Path) -> Path:
    nodes = list(graph.get("nodes", []))
    edges = graph.get("edges", [])
    layout = graph.get("layout") or dependency_layout(nodes, edges)
    layers = layout.get("layers", []) or [[node["use_case_id"] for node in nodes]]
    node_by_id = {node["use_case_id"]: node for node in nodes}
    box_w, box_h, gap_x, gap_y, margin, top = 196, 68, 42, 30, 30, 88
    row_positions = layout.get("row_positions", {})
    max_rows = max((int(row_positions.get(node_id, row)) for layer in layers for row, node_id in enumerate(layer)), default=0) + 1
    width = margin * 2 + max(1, len(layers)) * box_w + max(0, len(layers)-1) * gap_x
    node_bottom = top + max_rows * box_h + max(0, max_rows-1) * gap_y
    legend_top = node_bottom + 50
    height = legend_top + max(70, len(edges)*25) + 48
    boxes: dict[str, tuple[float, float, float, float]] = {}
    layer_of: dict[str, int] = {}
    for layer_index, layer in enumerate(layers):
        for row, node_id in enumerate(layer):
            if node_id not in node_by_id:
                continue
            x = margin + layer_index * (box_w + gap_x)
            y = top + int(row_positions.get(node_id, row)) * (box_h + gap_y)
            boxes[node_id] = (x, y, box_w, box_h)
            layer_of[node_id] = layer_index
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#fff"/>', '<defs><marker id="dep-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L9,4 z" fill="#6B82A0"/></marker><marker id="cycle-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L9,4 z" fill="#C44536"/></marker></defs>', _text(margin, 42, f"{graph.get('project','')} · 用例数据依赖关系图", 22, "bold", "#153E75")]
    for i, layer in enumerate(layers):
        x = margin + i * (box_w + gap_x)
        label = "根用例" if i == 0 else f"依赖层 {i+1}"
        body.append(_text(x+box_w/2, 74, label, 13, "bold", "#536273", "middle"))
    pairs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in edges:
        pairs.setdefault((str(edge.get("from_use_case", "")), str(edge.get("to_use_case", ""))), []).append(edge)
    for (source_id, target_id), pair_edges in pairs.items():
        a, b = boxes.get(source_id), boxes.get(target_id)
        if not a or not b:
            continue
        ax, ay, aw, ah = a; bx, by, bw, bh = b
        cycle = any(edge.get("cycle_requires_review") for edge in pair_edges)
        if layer_of.get(source_id, 0) < layer_of.get(target_id, 0):
            start = (ax+aw, ay+ah/2); end = (bx, by+bh/2)
        else:
            # Same-layer/back edges (normally cycle edges) use the facing
            # boundary points of the two boxes, keeping a single straight line.
            acx, acy, bcx, bcy = ax+aw/2, ay+ah/2, bx+bw/2, by+bh/2
            dx, dy = bcx-acx, bcy-acy
            scale_a = min((aw/2)/abs(dx) if dx else float("inf"), (ah/2)/abs(dy) if dy else float("inf"))
            scale_b = min((bw/2)/abs(dx) if dx else float("inf"), (bh/2)/abs(dy) if dy else float("inf"))
            start = (acx+dx*scale_a, acy+dy*scale_a)
            end = (bcx-dx*scale_b, bcy-dy*scale_b)
        edge_ids = ",".join(str(edge.get("edge_id", "")) for edge in pair_edges)
        color = "#C44536" if cycle else "#6B82A0"
        marker = "cycle-arrow" if cycle else "dep-arrow"
        dash = ' stroke-dasharray="6 4"' if cycle else ""
        body.append(f'<line data-relation="use_case_dependency" data-edge-ids="{_esc(edge_ids)}" data-cycle="{str(cycle).lower()}" x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" fill="none" stroke="{color}" stroke-width="1.8"{dash} marker-end="url(#{marker})"/>')
    for node in nodes:
        if node["use_case_id"] not in boxes:
            continue
        x, y, w, h = boxes[node["use_case_id"]]
        body.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="#E8F1FF" stroke="#356FC4" stroke-width="2"/>')
        body.append(_text(x+w/2, y+28, node["use_case_id"], 9, "normal", "#536273", "middle"))
        body.append(_text(x+w/2, y+49, node.get("name", ""), 12, "bold", "#22364D", "middle"))
    if not graph.get("edges"):
        body.append(_text(width/2, height-18, "暂无具备明确实体生命周期/状态前置证据的依赖边。", 13, "normal", "#8A4B08", "middle"))
    else:
        body.append(_text(margin, legend_top, "依赖证据（生产/前置用例 → 消费/依赖用例）", 14, "bold", "#153E75"))
        node_names = {node["use_case_id"]: node.get("name", node["use_case_id"]) for node in nodes}
        for index, edge in enumerate(edges):
            label = (f"{edge.get('edge_id','')}  {node_names.get(edge.get('from_use_case'), edge.get('from_use_case',''))} → "
                     f"{node_names.get(edge.get('to_use_case'), edge.get('to_use_case',''))}  |  {edge.get('entity','')} · {edge.get('relation','依赖')}")
            body.append(_text(margin + 4, legend_top + 23 + index * 24, label, 11, "normal", "#536273"))
    body.append("</svg>")
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True); output.write_text("\n".join(body), encoding="utf-8")
    return output
