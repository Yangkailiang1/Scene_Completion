"""System-composition diagrams with separate participation and dependency views."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .svg_renderer import _esc, _text
from .schemas import validate_scene_model
from .dependency_layout import dependency_layout


def build_system_composition_semantics(model: dict[str, Any], view: str = "participation") -> dict[str, Any]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    composition = normalized["system_composition"]
    edges = composition.get("edges", [])
    human_frontend = [edge for edge in edges if edge.get("relation") == "uses_frontend"]
    frontend_cases = [edge for edge in edges if edge.get("relation") == "serves_use_case"]
    node_by_id = {node.get("node_id"): node for node in composition.get("nodes", [])}
    external_cases = []
    for edge in edges:
        relation = edge.get("relation")
        if relation == "external_participates_in" and edge.get("use_case_id"):
            external_cases.append({"from_node": edge.get("from_node"), "to_use_case": edge.get("use_case_id"), "relation": relation, "source_location": edge.get("source_location", "")})
        elif relation == "uses_external_service":
            service = node_by_id.get(edge.get("from_node"), {})
            use_case_id = edge.get("use_case_id") or service.get("use_case_id")
            if use_case_id:
                external_cases.append({"from_node": edge.get("to_node"), "to_use_case": use_case_id, "relation": relation, "source_location": edge.get("source_location", "")})
    graph = normalized.get("use_case_dependency_graph") or {}
    return {
        **composition,
        "view_id": "system_composition_dependencies" if view == "dependencies" else "system_composition",
        "view_purpose": "参与关系：Actor → 专属 UI/前端 → 实际参与用例；外部 Service → 有证据的用例" if view != "dependencies" else "依赖关系：Actor → 专属 UI/前端 → 用例区域；展示用例依赖和有证据的外部 Service 参与",
        "participation_relations": {"actor_to_frontend": human_frontend, "frontend_to_use_case": frontend_cases if view != "dependencies" else [], "external_service_to_use_case": external_cases},
        "frontend_area_attachments": ([{"frontend_id": edge.get("to_node"), "use_case_area": "use_case_region"} for edge in human_frontend] if view == "dependencies" else []),
        "use_case_dependency_graph": graph if view == "dependencies" else {"edges": []},
        "layout": dependency_layout(graph.get("nodes", []), graph.get("edges", [])) if view == "dependencies" else {"type": "grid"},
    }


def render_system_composition_svg(model: dict[str, Any], output_path: str | Path, view: str = "participation") -> Path:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    composition = normalized["system_composition"]
    nodes = composition["nodes"]
    by_id = {node["node_id"]: node for node in nodes}
    actors = [n for n in nodes if n.get("kind") == "human_actor"]
    frontends = [n for n in nodes if n.get("kind") == "frontend_ui"]
    external = [n for n in nodes if n.get("kind") in {"external_actor", "external_service", "external_database", "external_llm"}]
    resources = [n for n in nodes if n.get("kind") in {"internal_database", "internal_knowledge_base"}]
    deployment = [n for n in nodes if n.get("kind") in {"deployment_hardware", "runtime_environment"}]
    devices = [by_id[node_id] for node_id in normalized.get("supported_devices", []) if node_id in by_id]
    dependency_graph = normalized.get("use_case_dependency_graph") or {}
    dependencies = dependency_graph.get("edges", []) if view == "dependencies" else []
    cases = list(normalized.get("use_cases", []))
    actor_order = {actor["node_id"]: i for i, actor in enumerate(actors)}
    actor_name_id = {actor["name"]: actor["node_id"] for actor in actors}
    case_order = {uc["use_case_id"]: i for i, uc in enumerate(cases)}
    def case_key(uc: dict[str, Any]) -> tuple[int, str]:
        indices = [actor_order[actor_name_id[name]] for name in uc.get("actors", []) if name in actor_name_id]
        return (min(indices) if indices else len(actors), uc["use_case_id"])

    cols, ew, eh, gx, gy = (3, 260, 78, 38, 44) if view != "dependencies" else (1, 190, 68, 28, 34)
    graph_layout = dependency_layout(dependency_graph.get("nodes", []), dependencies) if view == "dependencies" else None
    if view == "dependencies":
        case_layers = graph_layout.get("layers", []) or [[uc["use_case_id"] for uc in cases]]
        uc_by_id = {uc["use_case_id"]: uc for uc in cases}
        cases = [uc_by_id[uc_id] for layer in case_layers for uc_id in layer if uc_id in uc_by_id]
        cols = max(1, len(case_layers))
        rows = max((max(graph_layout.get("row_positions", {}).get(uc_id, row) for row, uc_id in enumerate(layer)) for layer in case_layers), default=0) + 1
    else:
        case_layers = []
        cases.sort(key=lambda uc: (case_key(uc), case_order[uc["use_case_id"]]))
        rows = max(1, math.ceil(len(cases) / cols))
    x0, y0, margin = (630 if view != "dependencies" else 570), 126, 34
    grid_w = max(1, cols) * ew + (max(1, cols) - 1) * gx
    grid_h = rows * eh + (rows - 1) * gy
    top_zone_h = grid_h + 112
    actor_x, actor_w, ui_x, ui_w = margin, 230, 300, 250
    ext_x, ext_w = x0 + grid_w + (100 if view != "dependencies" else 56), (250 if view != "dependencies" else 210)
    bottom_y = y0 + grid_h + 90
    res_h = max(120, 68 + math.ceil(max(1, len(resources))/3)*76)
    deploy_y = bottom_y + res_h + 18
    deploy_h = max(112, 68 + math.ceil(max(1, len(deployment))/3)*76)
    device_h = 100
    width, height = ext_x + ext_w + margin, deploy_y + deploy_h + 52
    case_boxes: dict[str, tuple[float, float, float, float]] = {}
    case_rows: dict[str, int] = {}
    rr_by_uc = {n.get("use_case_id"): n for n in nodes if n.get("kind") == "abstract_service" and n.get("layer", "RR") == "RR"}
    for i, uc in enumerate(cases):
        if view == "dependencies":
            col = next((j for j, layer in enumerate(case_layers) if uc["use_case_id"] in layer), 0)
            row = graph_layout.get("row_positions", {}).get(uc["use_case_id"], case_layers[col].index(uc["use_case_id"]))
        else:
            row, col = divmod(i, cols)
        case_boxes[uc["use_case_id"]] = (x0 + col*(ew+gx), y0 + row*(eh+gy), ew, eh)
        case_rows[uc["use_case_id"]] = row

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{math.ceil(width)}" height="{math.ceil(height)}" viewBox="0 0 {math.ceil(width)} {math.ceil(height)}">',
           '<rect width="100%" height="100%" fill="#FFFFFF"/>',
           '<defs><marker id="dep-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L0,8 L9,4 z" fill="#C07A2A"/></marker></defs>',
           _text(margin, 36, f"{normalized.get('system_name', normalized['project'])} 系统组成总览", 24, "bold", "#153E75")]

    def group(title: str, x: float, y: float, w: float, h: float, fill: str) -> None:
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="#8AA4C4" stroke-width="2"/>')
        svg.append(_text(x+15, y+27, title, 16, "bold", "#1F4E79"))

    group("外部 Actor", actor_x, 58, actor_w, top_zone_h, "#F7FBF3")
    group("UI/前端", ui_x, 58, ui_w, top_zone_h, "#FCFBF4")
    group("用例及依赖关系", x0-22, 58, grid_w+44, top_zone_h, "#F6F9FE")
    group("外部系统", ext_x, 58, ext_w, top_zone_h, "#F7FBF3")
    group("连接设备", ui_x, bottom_y, ui_w, device_h, "#FCFBF4")
    group("内部资源（数据库 / 知识库）", x0-22, bottom_y, grid_w+44, res_h, "#F7F9FC")
    group("部署硬件 / 运行环境", x0-22, deploy_y, grid_w+44, deploy_h, "#FCFBF4")

    positions: dict[str, tuple[float, float, float, float]] = {}
    actor_boxes: dict[str, tuple[float, float, float, float]] = {}
    frontend_boxes: dict[str, tuple[float, float, float, float]] = {}
    external_boxes: dict[str, tuple[float, float, float, float]] = {}

    def box_node(node: dict[str, Any], rect: tuple[float, float, float, float], fill: str, oval: bool=False, labels: list[str] | None=None) -> None:
        x,y,w,h=rect
        positions[node["node_id"]]=rect
        if oval:
            svg.append(f'<ellipse data-node-id="{_esc(node["node_id"])}" cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="#356FC4" stroke-width="2"/>')
        else:
            svg.append(f'<rect data-node-id="{_esc(node["node_id"])}" x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="#5B6B7F" stroke-width="1.5"/>')
        lines=labels or [node.get("name","")]
        step=18; y_text=y+h/2-(len(lines)-1)*step/2+5
        for j,line in enumerate(lines):
            svg.append(_text(x+w/2,y_text+j*step,line,13 if oval else 14,"bold" if j==0 else "normal","#23364D","middle"))

    # Actor-specific frontends are placed before their links; old generic
    # web/mobile nodes are not interpreted as hardware support.
    mapping_by_actor={m.get("actor_id"):m for m in normalized.get("frontend_mappings",[])}
    for i, actor in enumerate(actors):
        y=y0+12+i*94
        rect=(actor_x+14,y,actor_w-28,62); actor_boxes[actor["node_id"]]=rect
        box_node(actor,rect,"#E8F1FF")
        mapping=mapping_by_actor.get(actor["node_id"],{})
        front=by_id.get(mapping.get("frontend_id")) or next((n for n in frontends if n.get("actor_id")==actor["node_id"]),None)
        if front:
            frect=(ui_x+14,y,ui_w-28,62); frontend_boxes[front["node_id"]]=frect
            box_node(front,frect,"#FFF4DE")
            cy=y+31
            svg.append(f'<path data-relation="uses_frontend" d="M {rect[0]+rect[2]} {cy} H {frect[0]}" fill="none" stroke="#7187A1" stroke-width="1.5"/>')

    for i, node in enumerate(external):
        rect=(ext_x+12,y0+12+i*78,ext_w-24,58); external_boxes[node["node_id"]]=rect
        box_node(node,rect,"#FFF4DE")

    for uc in cases:
        rect=case_boxes[uc["use_case_id"]]
        node=rr_by_uc.get(uc["use_case_id"],{"node_id":f"usecase-{uc['use_case_id']}"})
        box_node(node,rect,"#E8F1FF",True,[uc["use_case_id"],uc.get("use_case_name","")])

    # In dependency view the frontend attaches only to the use-case region.
    if view == "dependencies":
        for frontend_id, frect in frontend_boxes.items():
            cy = frect[1] + frect[3]/2
            svg.append(f'<path data-relation="frontend_to_use_case_area" data-frontend="{_esc(frontend_id)}" d="M {frect[0]+frect[2]} {cy} H {x0-22}" fill="none" stroke="#7187A1" stroke-width="1.4"/>')

    # Human frontend -> use case: direct straight lines. Participation view
    # places all ellipses in one column, leaving a clean gap between the UI
    # panel and ellipse endpoints; actor colors distinguish the associations.
    serves_by_frontend: dict[str, list[str]] = {}
    for edge in composition.get("edges", []):
        if edge.get("relation") == "serves_use_case" and edge.get("from_node") in frontend_boxes:
            serves_by_frontend.setdefault(str(edge["from_node"]), []).append(str(edge.get("use_case_id", "")))
    actor_colors = {actor["node_id"]: ["#2563EB", "#16A34A", "#9333EA", "#D97706"][i % 4] for i, actor in enumerate(actors)}
    frontend_owner = {mapping.get("frontend_id"): mapping.get("actor_id") for mapping in normalized.get("frontend_mappings", [])}
    for frontend_index, (frontend_id, uc_ids) in enumerate(serves_by_frontend.items() if view != "dependencies" else []):
        frect=frontend_boxes[frontend_id]
        owner = frontend_owner.get(frontend_id)
        color = actor_colors.get(owner, "#7187A1")
        for uc_id in dict.fromkeys(uc_ids):
            target = case_boxes.get(uc_id)
            if not target:
                continue
            x,y,w,h=target
            svg.append(f'<line data-relation="serves_use_case" data-frontend="{_esc(frontend_id)}" data-actor="{_esc(owner or "")}" data-use-case="{_esc(uc_id)}" x1="{frect[0]+frect[2]}" y1="{frect[1]+frect[3]/2}" x2="{x}" y2="{y+h/2}" stroke="{color}" stroke-width="1.8"/>')

    # External-system actor -> use case enters from the right ellipse endpoint.
    external_links: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in composition.get("edges", []):
        if edge.get("relation") == "external_participates_in":
            external_links[(str(edge.get("use_case_id", "")), str(edge.get("from_node", "")))] = edge
        elif edge.get("relation") == "uses_external_service":
            rr_node = by_id.get(edge.get("from_node"), {})
            uc_id = str(rr_node.get("use_case_id", ""))
            if uc_id:
                external_links.setdefault((uc_id, str(edge.get("to_node", ""))), edge)
    external_by_node: dict[str, list[str]] = {}
    for uc_id, node_id in external_links:
        external_by_node.setdefault(node_id, []).append(uc_id)
    for service_index, (node_id, uc_ids) in enumerate(external_by_node.items()):
        source=external_boxes.get(node_id)
        if not source:
            continue
        for uc_id in dict.fromkeys(uc_ids):
            target=case_boxes.get(uc_id)
            if not target:
                continue
            x,y,w,h=target
            if view == "dependencies":
                # Keep this direct association outside the use-case frame;
                # the row aligns with the evidenced target UC but the segment
                # never cuts through later-layer ellipses on its way back.
                x1,y1,x2,y2 = source[0],source[1]+source[3]/2,x0+grid_w+22,y+h/2
            else:
                x1,y1,x2,y2 = source[0],source[1]+source[3]/2,x+w,y+h/2
            svg.append(f'<line data-relation="external_participates_in" data-node="{_esc(node_id)}" data-use-case="{_esc(uc_id)}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#D97706" stroke-width="1.65"/>')

    # Dependency view places prerequisites to the left and consumers to the
    # right. Edges use the inter-column gutters and touch ellipse endpoints.
    dependency_pairs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in dependencies:
        dependency_pairs.setdefault((str(edge.get("from_use_case", "")), str(edge.get("to_use_case", ""))), []).append(edge)
    gap_lane_counts: dict[int, int] = {}
    for index, ((source_id, target_id), pair_edges) in enumerate(dependency_pairs.items()):
        a=case_boxes.get(source_id); b=case_boxes.get(target_id)
        if not a or not b: continue
        ax,ay,aw,ah=a; bx,by,bw,bh=b
        if view == "dependencies":
            cycle = any(edge.get("cycle_requires_review") for edge in pair_edges)
            edge_ids=",".join(str(edge.get("edge_id","")) for edge in pair_edges)
            color="#C44536" if cycle else "#C07A2A"
            dash=' stroke-dasharray="7 4"' if cycle else ''
            source_layer=next((i for i,layer in enumerate(case_layers) if source_id in layer),0)
            target_layer=next((i for i,layer in enumerate(case_layers) if target_id in layer),0)
            if source_layer < target_layer:
                x1,y1,x2,y2 = ax+aw,ay+ah/2,bx,by+bh/2
            else:
                x1,y1,x2,y2 = _ellipse_edge_points(a,b)
            svg.append(f'<line data-relation="use_case_dependency" data-edge-ids="{_esc(edge_ids)}" data-from-use-case="{_esc(source_id)}" data-to-use-case="{_esc(target_id)}" data-cycle="{str(cycle).lower()}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" fill="none" stroke="{color}" stroke-width="1.65"{dash} marker-end="url(#dep-arrow)"/>')
            continue
        source_row, target_row=case_rows[source_id], case_rows[target_id]
        target_col=next(i for i, uc in enumerate(cases) if uc["use_case_id"]==target_id)%cols
        if source_row == target_row:
            lane_index=gap_lane_counts.get(source_row, 0); gap_lane_counts[source_row]=lane_index+1
            lane=ay+ah+8+(lane_index%max(1,(gy-16)//7))*7
            d=f"M {ax+aw/2} {ay+ah} V {lane} H {bx+bw/2} V {by+bh}"
        else:
            source_gap=source_row if target_row>source_row else source_row-1
            target_gap=target_row-1 if target_row>source_row else target_row
            source_slot=gap_lane_counts.get(source_gap,0); gap_lane_counts[source_gap]=source_slot+1
            target_slot=gap_lane_counts.get(target_gap,0); gap_lane_counts[target_gap]=target_slot+1
            lane_offset=max(1,(gy-16)//7)
            source_lane=y0+source_gap*(eh+gy)+eh+8+(source_slot%lane_offset)*7
            target_lane=y0+target_gap*(eh+gy)+eh+8+(target_slot%lane_offset)*7
            if target_col == 0:
                gutter=x0-8
            else:
                gutter=x0+target_col*(ew+gx)-gx/2
            if target_row > source_row:
                d=f"M {ax+aw/2} {ay+ah} V {source_lane} H {gutter} V {target_lane} H {bx+bw/2} V {by}"
            else:
                d=f"M {ax+aw/2} {ay} V {source_lane} H {gutter} V {target_lane} H {bx+bw/2} V {by+bh}"
        edge_ids=",".join(str(edge.get("edge_id","")) for edge in pair_edges)
        svg.append(f'<path data-relation="use_case_dependency" data-edge-ids="{_esc(edge_ids)}" d="{d}" fill="none" stroke="#C07A2A" stroke-width="1.55" stroke-dasharray="5 3" marker-end="url(#dep-arrow)"/>')

    for i,node in enumerate(resources):
        box_node(node,(x0+10+(i%3)*320,bottom_y+46+(i//3)*72,300,56),"#EAF7EA")
    for i,node in enumerate(deployment):
        box_node(node,(x0+10+(i%3)*320,deploy_y+46+(i//3)*72,300,56),"#E8F1FF")
    for i,node in enumerate(devices):
        box_node(node,(ui_x+12+(i%2)*122,bottom_y+42+(i//2)*42,112,30),"#E8F1FF")
    if view != "dependencies":
        legend_y = height - 44
        for i, actor in enumerate(actors):
            color = actor_colors[actor["node_id"]]
            lx = margin + i * 150
            svg.append(f'<line x1="{lx}" y1="{legend_y}" x2="{lx+28}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
            svg.append(_text(lx+36, legend_y+4, actor.get("name", actor["node_id"]), 12, "normal", "#536273"))
    note = "用例依赖边表示有证据的数据生命周期/状态前置关系；红色虚线为依赖环，需人工复核。" if view == "dependencies" else "参与关系图：不同颜色表示不同 Actor 的 UI/前端参与连线；外部服务仅绘制有证据的直线关系。"
    svg.append(_text(margin,height-18,note,12,"normal","#536273"))
    svg.append("</svg>")
    output=Path(output_path); output.parent.mkdir(parents=True,exist_ok=True); output.write_text("\n".join(svg),encoding="utf-8")
    return output


def _ellipse_edge_points(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Return a direct segment between ellipse borders, without entering either oval."""
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    acx, acy, arx, ary = ax + aw/2, ay + ah/2, aw/2, ah/2
    bcx, bcy, brx, bry = bx + bw/2, by + bh/2, bw/2, bh/2
    dx, dy = bcx-acx, bcy-acy
    if dx == 0 and dy == 0:
        return acx+arx, acy, bcx-brx, bcy
    sa = 1 / math.sqrt((dx/arx)**2 + (dy/ary)**2)
    sb = 1 / math.sqrt((dx/brx)**2 + (dy/bry)**2)
    return acx+dx*sa, acy+dy*sa, bcx-dx*sb, bcy-dy*sb


def _rect_ellipse_edge_points(rect: tuple[float, float, float, float], ellipse: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    rx, ry, rw, rh = rect; ex, ey, ew, eh = ellipse
    rcx, rcy, ecx, ecy = rx+rw/2, ry+rh/2, ex+ew/2, ey+eh/2
    dx, dy = ecx-rcx, ecy-rcy
    scale_rect = min((rw/2)/abs(dx) if dx else float("inf"), (rh/2)/abs(dy) if dy else float("inf"))
    scale_ellipse = 1 / math.sqrt((dx/(ew/2))**2 + (dy/(eh/2))**2) if dx or dy else 1
    return rcx+dx*scale_rect, rcy+dy*scale_rect, ecx-dx*scale_ellipse, ecy-dy*scale_ellipse
