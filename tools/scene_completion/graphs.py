"""Semantic use-case dependency graph and dependency-free SVG rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import ValidationFailure, validate_scene_model
from .svg_renderer import _esc, _text


def build_use_case_dependency_graph(model: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    ucs = normalized.get("use_cases", [])
    edges: list[dict[str, Any]] = []
    by_service: dict[str, list[str]] = {}
    for uc in ucs:
        for component in (uc.get("architecture") or {}).get("ar", []) or []:
            key = component.get("microservice_id") or component.get("microservice_name")
            if key:
                by_service.setdefault(str(key), []).append(uc["use_case_id"])
    for service, ids in by_service.items():
        for left in ids:
            for right in ids:
                if left != right:
                    edge = {"from_use_case": left, "to_use_case": right, "relation": "shared_ar_service", "service_id": service, "source_location": "architecture mapping"}
                    if edge not in edges:
                        edges.append(edge)
    explicit = normalized.get("use_case_dependencies") or normalized.get("dependencies") or []
    if isinstance(explicit, list):
        known = {u["use_case_id"] for u in ucs}
        for edge in explicit:
            if not isinstance(edge, dict):
                continue
            a, b = edge.get("from_use_case"), edge.get("to_use_case")
            if a in known and b in known:
                edges.append(dict(edge))
    return {"version": "6", "project": normalized["project"], "nodes": [{"use_case_id": u["use_case_id"], "name": u.get("use_case_name", ""), "rr_service_id": (u.get("architecture") or {}).get("rr", {}).get("service_id", "")} for u in ucs], "edges": edges, "semantics": {"shared_ar_service": "两个 RR 用例复用同一个 AR 微服务，因此形成可追踪依赖候选；不表示时序先后。"}}


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
    nodes = graph.get("nodes", [])
    width, row_h, margin = 1500, 86, 40
    height = max(360, 100 + len(nodes) * row_h)
    xs = {n["use_case_id"]: margin + (i % 4) * 350 for i, n in enumerate(nodes)}
    ys = {n["use_case_id"]: 80 + (i // 4) * row_h for i, n in enumerate(nodes)}
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#fff"/>', _text(margin, 38, f"{graph.get('project','')} · RR 用例依赖关系图", 22, "bold", "#153E75")]
    for edge in graph.get("edges", []):
        a, b = edge.get("from_use_case"), edge.get("to_use_case")
        if a not in xs or b not in xs:
            continue
        ax, ay, bx, by = xs[a]+130, ys[a]+28, xs[b]+130, ys[b]+28
        body.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#7192C5" stroke-width="1.5"/>')
        body.append(_text((ax+bx)/2, (ay+by)/2-4, edge.get("relation", "依赖"), 11, "normal", "#536273", "middle"))
    for n in nodes:
        x, y = xs[n["use_case_id"]], ys[n["use_case_id"]]
        body.append(f'<ellipse cx="{x+130}" cy="{y+28}" rx="130" ry="28" fill="#E8F1FF" stroke="#356FC4" stroke-width="2"/>')
        body.append(_text(x+130, y+24, f"{n['use_case_id']} {n.get('name','')}", 13, "bold", anchor="middle"))
    body.append("</svg>")
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True); output.write_text("\n".join(body), encoding="utf-8")
    return output
