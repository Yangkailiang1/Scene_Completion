"""Reference test-scenario extraction, CRUD dependency graph, and match metrics."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any


REQUIRED_TEST_FIELDS = {
    "场景类型": "scenario_type",
    "前置条件": "preconditions",
    "触发条件": "trigger",
    "关联需求": "requirements",
    "测试目标": "objective",
    "预期结果": "expected_result",
    "来源定位": "source_location",
}
TYPE_MAP = {"正常": "normal", "异常": "exception", "可选": "optional", "normal": "normal", "exception": "exception", "optional": "optional"}


def extract_reference_test_scenarios(markdown: str) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    errors: list[str] = []
    for line_number, line in enumerate(markdown.splitlines(), 1):
        if line.lstrip().startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and cells[0].lower() in {"编号", "场景编号", "id"}:
                table_header = cells
                continue
            if "table_header" in locals() and cells and not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
                if len(cells) == len(table_header) and cells[0] and not cells[0].lower().startswith("编号"):
                    row = dict(zip(table_header, cells))
                    scenario = {"test_scenario_id": row.get("编号", row.get("场景编号", row.get("id", ""))),
                                "name": row.get("场景名称", row.get("名称", "")),
                                "scenario_type": TYPE_MAP.get(row.get("类型", ""), row.get("类型", "")),
                                "preconditions": row.get("前置条件", ""), "trigger": row.get("触发条件", ""),
                                "requirements": row.get("关联需求", ""), "objective": row.get("测试目标", ""),
                                "expected_result": row.get("预期结果", ""), "source_location": row.get("来源定位", ""),
                                "source_heading_line": line_number}
                    scenarios.append(scenario)
            continue
        heading = re.match(r"^###\s+([^：:]+)[：:]\s*(.+?)\s*$", line)
        if heading:
            if current:
                scenarios.append(current)
            current = {"test_scenario_id": heading.group(1).strip(), "name": heading.group(2).strip(), "source_heading_line": line_number}
            continue
        if current is None:
            continue
        field = re.match(r"^\s*(?:[-*]\s*)?([^：:]+)[：:]\s*(.*?)\s*$", line)
        if not field:
            continue
        label, value = field.group(1).strip(), field.group(2).strip()
        if label in REQUIRED_TEST_FIELDS and value:
            current[REQUIRED_TEST_FIELDS[label]] = value
    if current:
        scenarios.append(current)
    seen: set[str] = set()
    for index, scenario in enumerate(scenarios, 1):
        scenario_id = scenario.get("test_scenario_id", "")
        if not scenario_id:
            errors.append(f"scenario {index}: missing test_scenario_id")
        if scenario_id in seen:
            errors.append(f"duplicate test_scenario_id: {scenario_id}")
        seen.add(scenario_id)
        raw_type = scenario.get("scenario_type", "")
        scenario["scenario_type"] = TYPE_MAP.get(raw_type, raw_type)
        for label, key in REQUIRED_TEST_FIELDS.items():
            if not scenario.get(key):
                errors.append(f"{scenario_id}: missing {label}")
        digest = hashlib.sha1(scenario_id.encode("utf-8")).hexdigest()[:12].upper()
        scenario["stable_id"] = f"REF-{digest}"
    if not scenarios:
        errors.append("no test scenarios found (expected ### TEST-ID：场景名称 headings)")
    return {"schema_version": "1.0", "scenario_count": len(scenarios), "scenarios": scenarios, "valid": not errors, "errors": errors}


def extract_reference_test_scenarios_from_json(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    scenarios = value.get("scenarios") if isinstance(value, dict) else None
    if not isinstance(scenarios, list):
        return {"valid": False, "errors": ["scenarios must be a list"], "scenario_count": 0}
    seen: set[str] = set()
    for index, scenario in enumerate(scenarios, 1):
        if not isinstance(scenario, dict):
            errors.append(f"scenarios[{index}] must be an object")
            continue
        scenario_id = str(scenario.get("test_scenario_id", ""))
        if not scenario_id:
            errors.append(f"scenarios[{index}] needs test_scenario_id")
        if scenario_id in seen:
            errors.append(f"duplicate test_scenario_id: {scenario_id}")
        seen.add(scenario_id)
        for field in ("name", "scenario_type", "preconditions", "trigger", "requirements", "objective", "expected_result", "source_location"):
            if not str(scenario.get(field, "")).strip():
                errors.append(f"{scenario_id or index}: missing {field}")
        if scenario.get("scenario_type") not in {"normal", "exception", "optional"}:
            errors.append(f"{scenario_id or index}: invalid scenario_type")
    return {"schema_version": str(value.get("schema_version", "1.0")), "valid": not errors, "errors": errors, "scenario_count": len(scenarios), "scenarios": scenarios}


def build_crud_dependency_graph(model: dict[str, Any]) -> dict[str, Any]:
    operations = model.get("use_case_entity_operations", [])
    use_cases = {str(uc.get("use_case_id")): uc for uc in model.get("use_cases", [])}
    by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for operation in operations:
        if operation.get("operation") in {"C", "R", "U", "D"}:
            by_entity[str(operation.get("entity", ""))].append(operation)
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    quadruples = []
    for entity, rows in by_entity.items():
        creators = [row for row in rows if row.get("operation") == "C"]
        for source in rows:
            source_op = source.get("operation")
            if source_op not in {"R", "U", "D"}:
                continue
            for target in creators:
                source_uc, target_uc = str(source.get("use_case_id")), str(target.get("use_case_id"))
                if source_uc == target_uc:
                    continue
                key = (source_uc, target_uc)
                edge = pairs.setdefault(key, {"from_use_case": source_uc, "to_use_case": target_uc, "labels": set(), "entities": set(), "reasons": []})
                edge["labels"].add(f"{source_op}->C")
                edge["entities"].add(entity)
                reason = {"source_operation": source_op, "target_operation": "C", "entity": entity,
                          "source_operation_id": source.get("operation_id", ""), "target_operation_id": target.get("operation_id", ""),
                          "source_location": source.get("source_location", ""), "target_source_location": target.get("source_location", "")}
                if reason not in edge["reasons"]:
                    edge["reasons"].append(reason)
                    quadruples.append({"source_use_case": source_uc, "target_use_case": target_uc, **reason})
    label_order = {"R->C": 0, "U->C": 1, "D->C": 2}
    edges = []
    for edge in pairs.values():
        edges.append({**edge, "labels": sorted(edge["labels"], key=lambda value: label_order[value]), "entities": sorted(edge["entities"])})
    edges.sort(key=lambda item: (item["from_use_case"], item["to_use_case"]))
    quadruples.sort(key=lambda item: (item["source_use_case"], item["target_use_case"], item["entity"], label_order[f"{item['source_operation']}->C"]))
    dot_lines = ["digraph G {"]
    for uc_id in sorted(use_cases):
        dot_lines.append(f'  "{_dot_escape(uc_id)}" [shape=box];')
    for edge in edges:
        labels = ",".join(edge["labels"])
        dot_lines.append(f'  "{_dot_escape(edge["from_use_case"])}" -> "{_dot_escape(edge["to_use_case"])}" [label="{_dot_escape(labels)}"];')
    dot_lines.append("}")
    names = {uc_id: str(uc.get("name", uc_id)) for uc_id, uc in use_cases.items()}
    tuple_lines = [f"{names.get(row['source_use_case'], row['source_use_case'])}，数据依赖于，{names.get(row['target_use_case'], row['target_use_case'])}，依赖缘由：{row['source_operation']}（{row['entity']}）依赖于C（{row['entity']}）" for row in quadruples]
    edge_lines = [
        f"{edge['from_use_case']}（{names.get(edge['from_use_case'], edge['from_use_case'])}）"
        f" ──[{','.join(edge['labels'])}]──> "
        f"{edge['to_use_case']}（{names.get(edge['to_use_case'], edge['to_use_case'])}）"
        f"（实体：{', '.join(sorted(edge['entities']))}）"
        for edge in edges
    ]
    for edge in edges:
        edge["labels"] = ",".join(edge["labels"])
        edge["entities"] = sorted(edge["entities"])
    return {"schema_version": "1.0", "edge_semantics": "源用例依赖目标用例；R/U/D 依赖同实体创建用例 C", "edges": edges, "dot": "\n".join(dot_lines), "edge_list_markdown": "\n".join(f"- {line}" for line in edge_lines), "four_tuples": quadruples, "four_tuples_markdown": "\n".join(f"- {line}" for line in tuple_lines)}


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def score_scenario_matches(reference: dict[str, Any], generated: dict[str, Any], match_data: dict[str, Any]) -> dict[str, Any]:
    reference_items = reference.get("scenarios", []) if isinstance(reference, dict) else []
    generated_items = generated.get("scenarios", []) if isinstance(generated, dict) else generated
    if not isinstance(generated_items, list) or not isinstance(reference_items, list):
        return {"valid": False, "errors": ["reference and generated inputs must contain scenario arrays"]}
    ref_ids = {str(item.get("test_scenario_id") or item.get("scenario_id") or item.get("stable_id")) for item in reference_items}
    gen_ids = {str(item.get("scenario_id") or item.get("generated_scenario_id")) for item in generated_items}
    links = match_data.get("matches", []) if isinstance(match_data, dict) else None
    errors: list[str] = []
    if not isinstance(links, list):
        errors.append("matches must be a list")
        links = []
    seen: set[tuple[str, str]] = set()
    fully_covered: set[str] = set()
    partial_refs: set[str] = set()
    fully_matched_generated: set[str] = set()
    partial_links = 0
    for index, link in enumerate(links, 1):
        ref_id = str(link.get("test_scenario_id", ""))
        gen_id = str(link.get("generated_scenario_id", ""))
        status = str(link.get("match_status", ""))
        if ref_id not in ref_ids:
            errors.append(f"matches[{index}] references unknown test_scenario_id: {ref_id}")
        if gen_id not in gen_ids:
            errors.append(f"matches[{index}] references unknown generated_scenario_id: {gen_id}")
        if status not in {"full", "partial", "unmatched"}:
            errors.append(f"matches[{index}] has invalid match_status: {status}")
        if not str(link.get("evidence", "")).strip():
            errors.append(f"matches[{index}] needs evidence")
        pair = (ref_id, gen_id)
        if pair in seen:
            errors.append(f"duplicate match pair: {ref_id} -> {gen_id}")
        seen.add(pair)
        if status == "full":
            fully_covered.add(ref_id)
            fully_matched_generated.add(gen_id)
        elif status == "partial":
            partial_refs.add(ref_id)
            partial_links += 1
    ref_total, gen_total = len(reference_items), len(generated_items)
    return {"schema_version": "1.0", "valid": not errors, "errors": errors, "matches": links,
            "metrics": {"test_scenario_coverage": {"numerator": len(fully_covered), "denominator": ref_total, "rate": len(fully_covered) / ref_total if ref_total else None},
                        "auto_adoption_proxy": {"numerator": len(fully_matched_generated), "denominator": gen_total, "rate": len(fully_matched_generated) / gen_total if gen_total else None, "note": "自动采纳代理率，不是人工审核采纳率"},
                        "partial_match_test_scenarios": len(partial_refs), "partial_match_links": partial_links,
                        "unmatched_test_scenarios": sorted(ref_ids - fully_covered - partial_refs),
                        "unmatched_generated_scenarios": sorted(gen_ids - fully_matched_generated)},
            "match_count": len(links)}
