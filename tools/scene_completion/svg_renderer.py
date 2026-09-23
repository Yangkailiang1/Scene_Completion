"""Pure-Python SVG renderers used by Scene Completion V5."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any


COLORS = {"RR": "#E8F1FF", "SR": "#FFF4DE", "AR": "#EAF7EA", "system": "#E7F0FA"}


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _node_layer(node: dict[str, Any]) -> str:
    return str(node.get("layer") or ("SR" if node.get("kind") in {"external_service", "external_database", "external_llm"} else "AR" if node.get("kind") in {"internal_database", "internal_service", "implementation_api"} else "RR"))


def _text(x: float, y: float, text: str, size: int = 14, weight: str = "normal", fill: str = "#1F2937", anchor: str = "start") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="Arial,Helvetica,sans-serif" font-size="{size}px" font-weight="{weight}" fill="{fill}">{_esc(text)}</text>'


def _wrap(text: Any, width: int) -> list[str]:
    value = str(text or "")
    if not value:
        return [""]
    lines: list[str] = []
    for part in value.splitlines() or [""]:
        lines.extend(part[i:i + max(1, width)] for i in range(0, len(part), max(1, width)) or [""])
    return lines or [""]


def _node_label(node: dict[str, Any], name_width: int = 19) -> list[str]:
    lines = _wrap(node.get("name", node.get("node_id", "")), name_width)
    lines.append(f"{node.get('node_id', '')} · {_node_layer(node)}")
    if node.get("use_case_id"):
        lines.append(str(node["use_case_id"]))
    return lines


def _draw_node(body: list[str], node: dict[str, Any], box: tuple[float, float, float, float], ellipse: bool = False) -> None:
    x, y, w, h = box
    layer = _node_layer(node)
    fill = COLORS.get(layer, "#F3F4F6")
    if node.get("node_id") == "system":
        fill = COLORS["system"]
    if ellipse:
        body.append(f'<ellipse cx="{x+w/2:.1f}" cy="{y+h/2:.1f}" rx="{w/2:.1f}" ry="{h/2:.1f}" fill="{fill}" stroke="#356FC4" stroke-width="2"/>')
    else:
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="9" fill="{fill}" stroke="#5B6B7F" stroke-width="1.5"/>')
    lines = _node_label(node, 24 if ellipse else 19)
    start_y = y + h/2 - ((len(lines)-1) * 8)
    for i, line in enumerate(lines):
        body.append(_text(x+w/2, start_y + i*18, line, 13 if i else 14, "bold" if i == 0 else "normal", anchor="middle"))


def _box_center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x, y, w, h = box
    return x + w / 2, y + h / 2


def _boundary_anchor(
    box: tuple[float, float, float, float],
    toward: tuple[float, float],
    ellipse: bool = False,
) -> tuple[float, float]:
    """Return the point where a connection meets a node's visible boundary."""
    cx, cy = _box_center(box)
    dx, dy = toward[0] - cx, toward[1] - cy
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return cx, cy
    x, y, w, h = box
    if ellipse:
        rx, ry = w / 2, h / 2
        scale = 1 / math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
    else:
        candidates = []
        if abs(dx) > 1e-9:
            candidates.append((w / 2) / abs(dx))
        if abs(dy) > 1e-9:
            candidates.append((h / 2) / abs(dy))
        scale = min(candidates)
    return cx + dx * scale, cy + dy * scale


def render_system_composition_svg(model: dict[str, Any], output_path: str | Path) -> Path:
    """Render the RR-only system overview with stable, non-overlapping zones."""
    all_nodes = list(model.get("system_composition", {}).get("nodes", []))
    system = next((n for n in all_nodes if n.get("node_id") == "system"), {"node_id": "system", "name": model.get("system_name", "系统"), "kind": "internal_service", "layer": "RR"})
    rr = [n for n in all_nodes if n.get("kind") == "abstract_service" and n.get("layer", "RR") == "RR"]
    actors = [n for n in all_nodes if n.get("kind") in {"human_actor", "external_actor"}]
    devices = [n for n in all_nodes if n.get("kind") == "connection_device"]
    externals = [n for n in all_nodes if n.get("kind") in {"external_service", "external_database", "external_llm"}]
    databases = [n for n in all_nodes if n.get("kind") in {"internal_database", "internal_knowledge_base"}]
    deployment = [n for n in all_nodes if n.get("kind") in {"deployment_hardware", "runtime_environment"}]
    margin, gap = 34, 24
    col_w = {"actors": 255, "devices": 235, "system": 660, "external": 290}
    width = margin*2 + sum(col_w.values()) + gap*3
    rr_h = max(170, 95 + math.ceil(max(1, len(rr))/2) * 95)
    system_h = rr_h + 85
    external_h = max(170, 95 + len(externals) * 82)
    resource_h = max(135, 95 + math.ceil(max(1, len(databases)) / 3) * 88)
    deployment_h = max(120, 95 + math.ceil(max(1, len(deployment)) / 3) * 88)
    height = 70 + max(system_h, external_h) + 26 + resource_h + 18 + deployment_h + 70
    x_actor = margin
    x_device = x_actor + col_w["actors"] + gap
    x_system = x_device + col_w["devices"] + gap
    x_external = x_system + col_w["system"] + gap
    top_y = 62
    positions: dict[str, tuple[float,float,float,float]] = {}
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{math.ceil(width)}" height="{math.ceil(height)}" viewBox="0 0 {math.ceil(width)} {math.ceil(height)}">', '<rect width="100%" height="100%" fill="#FFFFFF"/>']
    body.append(_text(margin, 34, f"{model.get('system_name', model.get('project', '系统'))} 系统组成总览（RR 用例视图）", 24, "bold", "#153E75"))

    def group(title: str, x: float, y: float, w: float, h: float, fill: str) -> None:
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="14" fill="{fill}" stroke="#8AA4C4" stroke-width="2"/>')
        body.append(_text(x+16, y+28, title, 17, "bold", "#1F4E79"))

    group("外部 Actor", x_actor, top_y, col_w["actors"], system_h, "#F7FBF3")
    group("连接设备", x_device, top_y, col_w["devices"], system_h, "#FCFBF4")
    group("系统 / RR 用例", x_system, top_y, col_w["system"], system_h, "#F6F9FE")
    group("外部 Service / 数据库 / LLM（SR）", x_external, top_y, col_w["external"], max(system_h, external_h), "#F7FBF3")
    bottom_y = top_y + max(system_h, external_h) + 26
    group("内部资源（数据库 / 知识库）", x_system, bottom_y, col_w["system"], resource_h, "#F7F9FC")
    deployment_y = bottom_y + resource_h + 18
    group("部署硬件 / 运行环境", x_system, deployment_y, col_w["system"], deployment_h, "#FCFBF4")

    def place_stack(items: list[dict[str, Any]], x: float, y: float, w: float, item_h: float = 62, spacing: float = 12, ellipse: bool = False, cols: int = 1):
        if not items:
            return
        inner_y = y + 48
        actual_w = (w - (cols-1)*16 - 28) / cols
        for i, node in enumerate(items):
            row, col = divmod(i, cols)
            bx = x + 14 + col*(actual_w+16)
            by = inner_y + row*(item_h+spacing)
            box = (bx, by, actual_w, item_h)
            positions[node["node_id"]] = box
            _draw_node(body, node, box, ellipse)

    place_stack(actors, x_actor, top_y, col_w["actors"])
    place_stack(devices, x_device, top_y, col_w["devices"])
    positions[system["node_id"]] = (x_system+16, top_y+44, col_w["system"]-32, 50)
    _draw_node(body, system, positions[system["node_id"]])
    place_stack(rr, x_system, top_y+75, col_w["system"], item_h=62, spacing=14, ellipse=True, cols=2)
    place_stack(externals, x_external, top_y, col_w["external"], item_h=62, spacing=12)
    place_stack(databases, x_system, bottom_y, col_w["system"], item_h=58, spacing=12, cols=3)
    place_stack(deployment, x_system, deployment_y, col_w["system"], item_h=58, spacing=12, cols=3)

    rr_ids = {n["node_id"] for n in rr}
    node_by_id = {n.get("node_id"): n for n in all_nodes}
    # Explicit RR associations: actor to the ellipse's left tip, and external
    # dependencies to its right tip.  This uses stable semantic edges added by
    # model normalization, never labels or layout inference.
    for edge in model.get("system_composition", {}).get("edges", []):
        relation = edge.get("relation")
        if relation not in {"participates_in", "external_participates_in", "uses_external_service"}:
            continue
        a, b = edge.get("from_node"), edge.get("to_node")
        p, q = positions.get(a), positions.get(b)
        if not p or not q:
            continue
        if relation == "participates_in":
            actor_box, ellipse_box = p, q
            actor_center = _box_center(actor_box)
            source_anchor = _boundary_anchor(actor_box, _box_center(ellipse_box))
            _, cy = _box_center(ellipse_box)
            target_anchor = (ellipse_box[0], cy)
            start, end = source_anchor, target_anchor
        else:
            if relation == "external_participates_in":
                external_box, ellipse_box = p, q
            else:
                ellipse_box, external_box = p, q
            external_center = _box_center(external_box)
            source_anchor = (ellipse_box[0] + ellipse_box[2], _box_center(ellipse_box)[1])
            target_anchor = _boundary_anchor(external_box, _box_center(ellipse_box))
            start, end = (target_anchor, source_anchor) if relation == "external_participates_in" else (source_anchor, target_anchor)
        body.append(f'<line data-relation="{_esc(relation)}" data-use-case="{_esc(edge.get("use_case_id", ""))}" x1="{start[0]:.1f}" y1="{start[1]:.1f}" x2="{end[0]:.1f}" y2="{end[1]:.1f}" stroke="#7187A1" stroke-width="1.8"/>')

    for edge in model.get("system_composition", {}).get("edges", []):
        a, b = edge.get("from_node"), edge.get("to_node")
        if edge.get("relation") in {"participates_in", "external_participates_in", "uses_external_service"}:
            continue
        if a in rr_ids or b in rr_ids:
            continue
        if a == system.get("node_id") or b == system.get("node_id"):
            other = b if a == system.get("node_id") else a
            if node_by_id.get(other, {}).get("kind") != "connection_device":
                continue
        p, q = positions.get(a), positions.get(b)
        if not p or not q:
            continue
        p_center, q_center = _box_center(p), _box_center(q)
        p_anchor = _boundary_anchor(p, q_center, ellipse=node_by_id.get(a, {}).get("kind") == "abstract_service")
        q_anchor = _boundary_anchor(q, p_center, ellipse=node_by_id.get(b, {}).get("kind") == "abstract_service")
        body.append(f'<line x1="{p_anchor[0]:.1f}" y1="{p_anchor[1]:.1f}" x2="{q_anchor[0]:.1f}" y2="{q_anchor[1]:.1f}" stroke="#7A8797" stroke-width="1.8"/>')
    body.append(_text(margin, height-22, "RR 用例以椭圆表示；AR 微服务与软件实现接口详见各用例 SSD 和接口映射表。", 12, "normal", "#536273"))
    body.append("</svg>")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(body), encoding="utf-8")
    return output


def _participant_order(ssd: dict[str, Any], messages: list[dict[str, Any]]) -> list[str]:
    declared = [item.get("node_id") for item in ssd.get("lifelines", []) if item.get("node_id")]
    result = [item for item in declared if any(item in (m.get("from_node"), m.get("to_node")) for m in messages)]
    for message in messages:
        for node_id in (message.get("from_node"), message.get("to_node")):
            if node_id and node_id not in result:
                result.append(node_id)
    return result


def render_ssd_svg(ssd: dict[str, Any], model: dict[str, Any], output_path: str | Path) -> Path:
    nodes = {node["node_id"]: node for node in model.get("system_composition", {}).get("nodes", [])}
    messages = sorted(ssd.get("messages", []), key=lambda item: item.get("ssd_sequence", item.get("sequence", 0)))
    participants = _participant_order(ssd, messages)
    labels = {item["node_id"]: item.get("label", item["node_id"]) for item in ssd.get("lifelines", []) if item.get("node_id")}
    for node_id in participants:
        labels.setdefault(node_id, nodes.get(node_id, {}).get("name", node_id))
    max_label = max([len(str(labels[p])) for p in participants] + [8])
    col_w = max(190, min(300, 85 + max_label * 8))
    margin = max(90, col_w/2 + 30)
    width = max(1100, margin*2 + max(0, len(participants)-1) * col_w)
    top = 100
    row_gap = 22
    labels_by_message, row_heights = [], []
    for message in messages:
        label = f"[{message.get('source_step_index')}] {message.get('message', '')}"
        api = message.get("api_method") or message.get("resource_path") or message.get("abstract_api_id") or message.get("implementation_api_id")
        if api and message.get("layer") != "RR":
            label += f" · {api}"
        lines = _wrap(label, max(24, int((abs(len(participants)-1)*col_w)/8)))
        labels_by_message.append(lines)
        row_heights.append(max(48, 22*len(lines)+18))
    height = top + 62 + sum(row_heights) + row_gap*max(0, len(messages)-1) + 75
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{math.ceil(width)}" height="{math.ceil(height)}" viewBox="0 0 {math.ceil(width)} {math.ceil(height)}">', '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L9,3 L0,6 z" fill="#27364B"/></marker></defs>', '<rect width="100%" height="100%" fill="#FFFFFF"/>']
    body.append(_text(32, 38, f"{ssd.get('name', ssd.get('use_case_id', 'SSD'))} · {ssd.get('layer', 'fused')} SSD", 22, "bold", "#153E75"))
    xs = {node_id: margin + i * ((width-2*margin)/max(1, len(participants)-1)) for i, node_id in enumerate(participants)}
    for node_id in participants:
        x = xs[node_id]
        label_lines = _wrap(labels[node_id], max(16, int(col_w/10)))
        box_h = 42 + max(0, len(label_lines)-1)*17
        body.append(f'<rect x="{x-col_w/2:.1f}" y="{top:.1f}" width="{col_w:.1f}" height="{box_h}" rx="7" fill="#E9EEF7" stroke="#687A91"/>')
        for i, line in enumerate(label_lines):
            body.append(_text(x, top+25+i*17, line, 13, "bold" if i == 0 else "normal", anchor="middle"))
        body.append(f'<line x1="{x:.1f}" y1="{top+box_h:.1f}" x2="{x:.1f}" y2="{height-30:.1f}" stroke="#9AA6B2" stroke-dasharray="5,5"/>')
    y = top + 62
    for message, lines, row_h in zip(messages, labels_by_message, row_heights):
        x1, x2 = xs.get(message.get("from_node"), margin), xs.get(message.get("to_node"), width-margin)
        is_return = message.get("message_kind") in {"response", "internal_return", "feedback"}
        dash = ' stroke-dasharray="7,5"' if is_return else ""
        body.append(f'<line x1="{x1:.1f}" y1="{y+row_h/2:.1f}" x2="{x2:.1f}" y2="{y+row_h/2:.1f}" stroke="#27364B" stroke-width="2"{dash} marker-end="url(#arrow)"/>')
        base_x = min(x1, x2) + 8
        for i, line in enumerate(lines):
            body.append(_text(base_x, y+row_h/2 - (len(lines)-1)*9 + i*18 - 7, line, 12, "normal", "#27364B"))
        y += row_h + row_gap
    body.append("</svg>")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(body), encoding="utf-8")
    return output
