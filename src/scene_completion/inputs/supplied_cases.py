"""Admission for runs based on supplied, validated behavior files."""

import json
from collections import defaultdict
from copy import deepcopy
from pathlib import PurePosixPath

from scene_completion.analysis.validation import validate_result
from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.ordered_behaviors import scenario_kind
from scene_completion.inputs.source_documents import normal_projection
from scene_completion.inputs.structure_models import catalogue, imported_sources


def case_catalogues(rows):
    structures = imported_sources(rows)
    return {
        layer: (catalogue(normal_projection([structures[layer]]), layer) or {"cases": []})["cases"]
        if layer in structures
        else []
        for layer in ("RR", "SR")
    }


def correspondence(cases):
    from scene_completion.analysis.use_cases import canonical_correspondence

    by_name = {layer: defaultdict(list) for layer in cases}
    for layer, entries in cases.items():
        for case in entries:
            by_name[layer][case["name"]].append(case)
    groups = []
    for name, rr in by_name["RR"].items():
        sr = by_name["SR"].get(name, [])
        if len(rr) != 1 or len(sr) != 1:
            continue
        groups.append(
            {
                "id": rr[0]["id"],
                "rr_ids": [rr[0]["id"]],
                "sr_ids": [sr[0]["id"]],
                "status": "confirmed",
                "reason": "已有结构化目录中的用例全名唯一对应",
                "source_refs": rr[0]["source_refs"] + sr[0]["source_refs"],
            }
        )
    # Allocate before applying a run filter. Appending a previously excluded case
    # must not renumber any of the existing, paired cases.
    return canonical_correspondence(
        {"groups": groups},
        {layer.lower() + "-cases": {"cases": entries} for layer, entries in cases.items()},
    )["groups"]


def participant_types(product, declared_types):
    types = defaultdict(set)
    for operation in product["raw"]["operations"].values():
        if scenario_kind(operation) != "main":
            continue
        for participant in operation.get("participant", {}).values():
            name = participant.get("name")
            kind = participant.get("kind")
            element = participant.get("element_type")
            if kind == "system":
                position = "系统边界"
            elif kind == "internal":
                position = "内部数据库" if element == "database" else "内部服务"
            elif kind == "external":
                if element == "human" or (not element and declared_types.get(name) == {"actor"}):
                    position = "外部Actor（人类）"
                elif element == "database":
                    position = "外部数据库"
                else:
                    position = "外部Actor（系统）"
            else:
                continue
            if name:
                types[name].add(position)
    return types


def validated_product(product, group, declared_types):
    if product["pending"]:
        raise ValueError("；".join(dict.fromkeys(item["reason"] for item in product["pending"])))
    fused = deepcopy(product["fused_template"])
    types = participant_types(product, declared_types)
    components = {}
    for interaction in fused["interactions"]:
        interaction["case_id"] = group["id"]
        for side in ("sender", "receiver"):
            participant = interaction[side]
            name = participant["name"]
            positions = types.get(name, set())
            if len(positions) != 1:
                raise ValueError("参与者缺少明确类型或类型冲突：" + name)
            position = next(iter(positions))
            participant["position"] = position
            components.setdefault(
                name,
                {
                    "id": "supplied-" + fingerprint(name)[:20],
                    "name": name,
                    "composition_type": position,
                    "parent_id": None,
                    "source_status": "explicit",
                    "source_refs": participant["source_refs"],
                },
            )
    document = product["normal_document"]
    composition = {"components": list(components.values()), "relations": []}
    validate_result("components", composition, {"RR": [document], "SR": [document]})
    inputs = {"RR": [document], "SR": [document], "case-group": group, "components": composition}
    validate_result("fused-ssd", fused, inputs)
    return fused, composition


def inspect_cases(rows, case_ids=()):
    cases = case_catalogues(rows)
    declared_types = defaultdict(set)
    for document in imported_sources(rows).values():
        for line in document["lines"]:
            if line["text"].startswith("- {"):
                fact = json.loads(line["text"][2:])
                if "canonical_name" in fact and "entity_type" in fact:
                    declared_types[fact["canonical_name"]].add(fact["entity_type"])
    groups = correspondence(cases)
    by_id = {c["id"]: c for entries in cases.values() for c in entries}
    by_name = {by_id[g["rr_ids"][0]]["name"]: g for g in groups}
    candidates = defaultdict(list)
    selected = set(case_ids)
    for row in rows:
        product = row.get("behavior_product") or {}
        path = row.get("relative_path") or product.get("context", {}).get("group_path", "")
        if product.get("kind") == "system_operations" or (
            PurePosixPath(path).name.casefold() == "sysoperation.json"
            or row.get("name", "").casefold() == "sysoperation.json"
        ):
            candidates[product.get("case_name") or path or row["name"]].append(row)
    diagnostics, accepted = [], {}
    for name, items in sorted(candidates.items()):
        group = by_name.get(name)
        # Previously disabled versions remain visible without conflicting with the active file.
        enabled = [row for row in items if row.get("behavior_enabled")]
        for row in items:
            record = {
                "file_id": row["id"],
                "file": row.get("relative_path") or row["name"],
                "name": name,
                "case_id": group["id"] if group else None,
                "target": group["id"] + ":fused-ssd" if group else None,
                "status": "excluded",
            }
            diagnostics.append(record)
            product = row.get("behavior_product")
            try:
                if not product:
                    raise ValueError(row.get("behavior_error") or "行为文件转换未通过")
                if not row.get("behavior_enabled"):
                    raise ValueError("文件尚未启用")
                if len({item.get("hash", item["id"]) for item in enabled}) > 1:
                    raise ValueError("同一用例存在多个已启用的 SSD 版本")
                if group is None:
                    raise ValueError("无法唯一对应 RR 和 SR 结构化用例")
                aliases = {group["id"], *group["rr_ids"], *group["sr_ids"]}
                if product.get("case_ids") and not set(product["case_ids"]) & aliases:
                    raise ValueError("行为文件的用例编号与目录不一致")
                fused, components = validated_product(product, group, declared_types)
            except (ValueError, TypeError, KeyError) as error:
                record["reason"] = str(error)
                continue
            if selected and not selected & aliases:
                record.update(status="outside_scope", reason="本轮未选择该用例")
                continue
            record.update(status="ready", reason="融合 SSD 已通过参与者、来源和交互校验")
            accepted[group["id"]] = {
                "row": row,
                "fused": fused,
                "components": components,
                "group": group,
            }
    return {"cases": diagnostics, "accepted": list(accepted)}, cases, groups, accepted
