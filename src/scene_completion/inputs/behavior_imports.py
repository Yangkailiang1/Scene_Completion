"""Literal, case-scoped input for resource/use-case behavior exports.

Directory names are navigation, not entity facts. Complete behavior includes E;
only explicitly selected main-success content is allowed into positive modeling.
The adapter never executes exporter instructions or follows external citations.
"""

import json
from copy import deepcopy
from pathlib import PurePosixPath

from scene_completion.inputs.colleague_formats import Facts
from scene_completion.inputs.structure_models import BRANCH_MARKER, CASE_MARKER, MARKER

VERSION = "resource-behavior-import-v2-complete-definitions"
LABELS = {
    "rr_ssd": "RR外部交互SSD",
    "sr_complete": "SR完整行为（含分支）",
    "sr_main": "SR主成功时序（引用）",
    "scenarios": "需求场景（主成功／异常／备选分流）",
}


def format_of(value):
    from scene_completion.inputs.ordered_behaviors import format_of as ordered_format

    if found := ordered_format(value):
        return found
    if not isinstance(value, dict):
        return None
    if (
        isinstance(value.get("use_case_id"), str)
        and isinstance(value.get("use_case_name"), str)
        and value.get("spec_level") in {"IR", "RR", "SR"}
        and isinstance(value.get("scenarios"), list)
    ):
        return "scenarios"
    if (
        isinstance(value.get("system_boundary"), str)
        and isinstance(value.get("interactions"), list)
        and isinstance(value.get("scenario_flows"), list)
    ):
        return "rr_ssd"
    if (
        value.get("spec_level") == "SR"
        and value.get("view_type") in {"complete", "main_success"}
        and isinstance(value.get("flow"), dict)
        and isinstance(value.get("operation_id"), str)
    ):
        if value["view_type"] == "main_success":
            return "sr_main"
        if isinstance(value.get("interactions"), list) and isinstance(value.get("actions"), list):
            return "sr_complete"
    return None


def group_path(path):
    """Only find sibling files; never assign business identity from the folder."""
    parts = PurePosixPath(str(path).replace("\\", "/")).parts
    if "operations" in parts:
        return "/".join(parts[: parts.index("operations")])
    return str(PurePosixPath(*parts).parent)


def context_for(path, files):
    from scene_completion.inputs.ordered_behaviors import context_for as ordered_context
    from scene_completion.inputs.ordered_behaviors import format_of as ordered_format

    if any(ordered_format(f["value"]) for f in files if f["path"] == path):
        return ordered_context(path, files)
    group = group_path(path)
    hits = []
    for item in files:
        if group_path(item["path"]) != group:
            continue
        v = item["value"]
        if format_of(v) == "scenarios":
            hits.append((v["use_case_id"], v["use_case_name"]))
    names = {name for _, name in hits}
    return {
        "case_name": next(iter(names)) if len(names) == 1 else None,
        "case_ids": list(dict.fromkeys(cid for cid, _ in hits)),
        "group_path": group,
        "reason": "仅用相邻场景文件的显式用例身份；目录名不作为实体或用例事实",
    }


def _records(rows, label):
    if not isinstance(rows, list) or any(
        not isinstance(r, dict) or not isinstance(r.get("id"), str) or not r["id"].strip()
        for r in rows
    ):
        raise ValueError(label + "必须为带非空id的对象数组")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(label + "含重复id")
    return {r["id"]: r for r in rows}


def flow_refs(flow, interactions, actions, *, allow_external=False):
    """Validate references; do not flatten branching into a fictitious sequence."""
    result = []

    def walk(node, depth=0):
        if depth > 60:
            raise ValueError("行为flow嵌套过深")
        if not isinstance(node, dict):
            raise ValueError("行为flow必须为对象")
        kind = node.get("type")
        if kind in {"interaction", "action"}:
            ref = node.get("ref")
            known = interactions if kind == "interaction" else actions
            if not isinstance(ref, str) or not ref.strip():
                raise ValueError("行为flow引用必须为非空字符串")
            if ref not in known and not allow_external:
                raise ValueError("行为flow引用不存在的" + kind + "：" + str(ref))
            result.append((kind, ref))
        elif kind == "sequence":
            if not isinstance(node.get("steps"), list):
                raise ValueError("sequence缺少steps")
            for step in node["steps"]:
                walk(step, depth + 1)
        elif kind == "choice":
            if not isinstance(node.get("branches"), list):
                raise ValueError("choice缺少branches")
            for branch in node["branches"]:
                if not isinstance(branch, dict):
                    raise ValueError("choice分支必须为对象")
                walk(branch.get("flow"), depth + 1)
        elif kind == "empty":
            pass
        elif kind == "optional":
            walk(node.get("body"), depth + 1)
        else:
            raise ValueError("暂不支持的flow类型：" + str(kind))

    walk(flow)
    return result


def compile_product(value, file_id, name, context=None):
    from scene_completion.inputs.ordered_behaviors import compile_product as compile_ordered
    from scene_completion.inputs.ordered_behaviors import format_of as ordered_format

    if ordered_format(value):
        return compile_ordered(value, file_id, name, context or {}, VERSION)
    kind = format_of(value)
    if not kind:
        return None
    context = deepcopy(context or {})
    facts = Facts(file_id, name)
    pending = []
    facts.document["source_id"] = "import-" + file_id + "-behavior-v2"
    layer = (
        "RR"
        if kind == "rr_ssd" or kind == "scenarios" and value["spec_level"] in {"IR", "RR"}
        else "SR"
    )
    case_name = value.get("use_case_name") or context.get("case_name")
    case_ids = list(
        dict.fromkeys(
            ([value["use_case_id"]] if value.get("use_case_id") else [])
            + context.get("case_ids", [])
        )
    )
    if not case_name:
        pending.append(
            {
                "object": name,
                "reason": "缺少显式用例身份；请同时导入同用例的ir_scenario/sr_scenario，或确认用例归属",
            }
        )
    branches = []
    retained = []
    locations = []
    scenario_doc = None
    if kind == "scenarios":
        scenes = _records(value["scenarios"], "scenarios")
        lines = []
        sid = "import-structure-behavior-v2-" + file_id

        def dumps(x):
            return json.dumps(x, ensure_ascii=False, separators=(",", ":"))

        def emit(text, pointer):
            lines.append({"number": len(lines) + 1, "text": text})
            locations.append({"line": len(lines), "json_pointer": pointer})
            return [
                {"source_id": sid, "line_start": len(lines), "line_end": len(lines), "quote": text}
            ]

        emit(MARKER + dumps({"layer": layer}) + " -->", "/spec_level")
        emit("## " + value["use_case_id"] + "：" + case_name, "/use_case_name")
        emit(
            CASE_MARKER
            + dumps(
                {
                    "id": value["use_case_id"],
                    "name": case_name,
                    "goal": case_name,
                    "actors": [],
                    "layer": layer,
                }
            )
            + " -->",
            "/use_case_id",
        )
        for n, s in enumerate(scenes.values()):
            if s.get("kind") != "main":
                continue
            p = "/scenarios/" + str(n)
            emit("### 主成功路径 " + s["id"], p + "/id")
            for k in ("trigger", "preconditions"):
                if s.get(k):
                    emit(dumps({k: s[k]}), p + "/" + k)
            for j, step in enumerate(s.get("steps", [])):
                if not isinstance(step, dict) or not isinstance(step.get("text"), str):
                    raise ValueError("场景steps必须包含text")
                emit(
                    dumps({k: step[k] for k in ("id", "text") if k in step}), p + "/steps/" + str(j)
                )
            success = (s.get("postconditions") or {}).get("success")
            if success:
                emit("成功结果：" + dumps(success), p + "/postconditions/success")
        emit("### 异常及备选分支（仅已有场景通道）", "/scenarios")
        for n, s in enumerate(scenes.values()):
            if s.get("kind") == "main":
                continue
            p = "/scenarios/" + str(n)
            if s.get("kind") == "exception":
                b = {
                    "id": layer + "::behavior-" + file_id + "::" + s["id"],
                    "case_hint": value["use_case_id"],
                    "description": dumps(
                        {
                            k: s[k]
                            for k in (
                                "id",
                                "name",
                                "trigger",
                                "preconditions",
                                "postconditions",
                                "extends",
                                "steps",
                            )
                            if k in s and k != "steps"
                        }
                        | {
                            "steps": [
                                {k: v for k, v in step.items() if k in {"id", "text"}}
                                for step in s.get("steps", [])
                            ]
                        }
                    ),
                    "operation_hint": case_name,
                    "party_hint": "",
                }
                refs = emit(BRANCH_MARKER + dumps(b), p)
                branches.append({**b, "source_refs": refs})
            else:
                retained.append({"id": s["id"], "kind": s.get("kind"), "json_pointer": p})
                emit(
                    "- 保留非异常分支 "
                    + dumps({k: s[k] for k in ("id", "name", "kind", "trigger") if k in s}),
                    p,
                )
        scenario_doc = {
            "source_id": sid,
            "name": name + " · " + layer + "场景可读投影.md",
            "channel": "existing",
            "lines": lines,
        }
        counts = {
            "main_scenarios": sum(s.get("kind") == "main" for s in scenes.values()),
            "exception_branches": len(branches),
            "retained_scenarios": len(retained),
        }
        # Not a complete project catalogue: these are case-local supplements.
        if not counts["main_scenarios"]:
            pending.append(
                {"object": case_name, "reason": "未提供主成功场景，正向建模继续使用原始需求"}
            )
    else:
        interactions = _records(value.get("interactions", []), "interactions")
        actions = _records(value.get("actions", []), "actions")
        for i in interactions.values() if kind != "sr_main" else []:
            if any(
                not isinstance(i.get(k), str) or not i[k].strip()
                for k in ("sender", "receiver", "message")
            ):
                raise ValueError("交互必须包含明确sender、receiver、message")
        flows = (
            [
                f["flow"]
                for f in value["scenario_flows"]
                if isinstance(f, dict) and isinstance(f.get("flow"), dict)
            ]
            if kind == "rr_ssd"
            else [value["flow"]]
        )
        for flow in flows:
            flow_refs(flow, interactions, actions, allow_external=kind == "sr_main")
        if kind == "sr_main":
            facts.add(
                {"operation_id": value["operation_id"], "spec_level": "SR", "flow": value["flow"]},
                "/flow",
            )
            # This is a reference/order view. Even when it happens to repeat
            # definitions, the complete view remains their authoritative source.
        elif kind == "rr_ssd":
            facts.add({"system_boundary": value["system_boundary"]}, "/system_boundary")
            for n, i in enumerate(value["interactions"]):
                facts.add(
                    {
                        k: i[k]
                        for k in (
                            "id",
                            "sender",
                            "receiver",
                            "message",
                            "source_steps",
                            "data_refs",
                            "origin_interaction_ids",
                        )
                        if k in i
                    },
                    "/interactions/" + str(n),
                )
        elif kind == "sr_complete":
            for collection, rows in (("interactions", interactions), ("actions", actions)):
                for n, i in enumerate(rows.values()):
                    facts.add(
                        {
                            k: i[k]
                            for k in (
                                "id",
                                "sender",
                                "receiver",
                                "message",
                                "description",
                                "source_steps",
                                "data_refs",
                                "direction",
                                "api_id",
                            )
                            if k in i
                        },
                        "/" + collection + "/" + str(n),
                    )
        # Mixed complete/SSD bodies are kept privately. Main-path extraction
        # uses sibling declarations below; it never sends exception guards to G.
        pending.append(
            {
                "object": value.get("operation_id") or case_name or name,
                "reason": "SR交互定义来自本完整行为文件；主成功时序只用于排序/引用；本地action不自动变成Service调用"
                if kind == "sr_complete"
                else "RR SSD需结合本用例主成功场景筛选；不将所有分支展开为正常交互"
                if kind == "rr_ssd"
                else "仅提供时序引用；向同操作complete_behavior解析交互定义，不要求本文件包含完整interactions/actions",
            }
        )
        counts = (
            {
                "ordered_references": len(
                    flow_refs(value["flow"], interactions, actions, allow_external=True)
                )
            }
            if kind == "sr_main"
            else {"interactions": len(interactions), "local_actions": len(actions)}
        )
    targets = (
        ["<用例>:existing-branches", "<用例>:ssd-context", "<用例>:fused-ssd"]
        if kind == "scenarios"
        else [
            "<用例>:ssd-context",
            "<用例>:fused-ssd",
            "<用例>:" + ("rr-ssd" if layer == "RR" else "sr-ssd"),
        ]
    )
    return {
        "format": "resource_behavior",
        "version": VERSION,
        "kind": kind,
        "label": LABELS[kind],
        "layer": layer,
        "case_name": case_name,
        "case_ids": case_ids,
        "context": context,
        "counts": counts,
        "pending": pending,
        "normal_document": deepcopy(facts.document),
        "scenario_document": scenario_doc,
        "json_locations": facts.locations,
        "scenario_locations": locations,
        "retained": retained,
        "target_nodes": targets,
        "raw": deepcopy(value),
    }


def selected(rows, scope):
    out = []
    for row in rows:
        p = row.get("behavior_product")
        if not p or not row.get("behavior_enabled", False) or p.get("version") != VERSION:
            continue
        if p.get("case_name") in scope or set(p.get("case_ids", [])) & set(scope):
            out.append((row, p))
    # Conflicting versions cannot be resolved by filename or newest timestamp.
    identities = {}
    for row, p in out:
        key = (
            p["case_name"],
            p["kind"],
            p["layer"],
            p["raw"].get("operation_id") or p["raw"].get("ID"),
        )
        if key in identities and identities[key] != row["hash"]:
            raise ValueError("行为导入存在同用例同视图多个版本，请停用旧版本")
        identities[key] = row["hash"]
    return out


def materials(rows, scope, *, diagnostics=None):
    from scene_completion.inputs.source_documents import normal_projection

    chosen = selected(rows, scope)
    out = {"RR": [], "SR": [], "existing": []}
    diagnostics = diagnostics if diagnostics is not None else []

    def issue(row, reason):
        diagnostics.append({"file_id": row["id"], "object": row["name"], "reason": reason})

    for row, p in chosen:
        if p["format"] == "ordered_behavior":
            if p.get("normal_document", {}).get("lines"):
                for layer in ("RR", "SR") if p["kind"] == "system_operations" else (p["layer"],):
                    out[layer].append(deepcopy(p["normal_document"]))
            from scene_completion.inputs.ordered_behaviors import scenario_kind

            if p.get("scenario_document") and scenario_kind(p["raw"]) == "exception":
                out["existing"].append(deepcopy(p["scenario_document"]))
            for entry in p["pending"]:
                issue(row, entry["reason"])
            continue
        if p["scenario_document"]:
            out[p["layer"]] += normal_projection([p["scenario_document"]])
            out["existing"].append(deepcopy(p["scenario_document"]))
        # A standalone order view is not an interaction definition. Validate
        # its references against the complete SR view before using the order.
        if p["kind"] == "sr_main" and not any(
            s["kind"] == "sr_complete"
            and s["raw"]["operation_id"] == p["raw"]["operation_id"]
            and s["context"].get("group_path") == p["context"].get("group_path")
            for _, s in chosen
        ):
            issue(row, "缺少同操作的complete_behavior交互定义；仅保留时序候选，原建模流程补齐")
        if p["kind"] == "sr_complete":
            used = set()
            order_document = None
            order_conflict = False
            siblings = [
                s
                for _, s in chosen
                if s["kind"] == "sr_main"
                and s["raw"]["operation_id"] == p["raw"]["operation_id"]
                and s["context"].get("group_path") == p["context"].get("group_path")
            ]
            if len(siblings) == 1:
                m = siblings[0]["raw"]
                try:
                    used = set(
                        flow_refs(
                            m["flow"],
                            _records(p["raw"]["interactions"], "interactions"),
                            _records(p["raw"]["actions"], "actions"),
                        )
                    )
                except ValueError as e:
                    issue(
                        row,
                        "主成功时序引用无法由完整SR定义解析："
                        + str(e)
                        + "；不补造交互，保留原流程",
                    )
                else:
                    order_document = deepcopy(siblings[0]["normal_document"])
            scenarios = [
                s
                for _, s in chosen
                if s["kind"] == "scenarios"
                and s["layer"] == "SR"
                and s["context"].get("group_path") == p["context"].get("group_path")
            ]
            main_steps = set()
            non_main_steps = set()
            if len(scenarios) == 1:
                for scene in scenarios[0]["raw"]["scenarios"]:
                    target = main_steps if scene.get("kind") == "main" else non_main_steps
                    target.update(step["id"] for step in scene.get("steps", []) if step.get("id"))
            allowed = set()
            for collection in ("interactions", "actions"):
                for n, i in enumerate(p["raw"][collection]):
                    steps = set(i.get("source_steps", []))
                    ref = (("interaction" if collection == "interactions" else "action"), i["id"])
                    # A reference in a short order view is not the whole SR inventory.
                    # Also retain explicitly normal scenario steps not in that view.
                    normal = ref in used or bool(steps and steps <= main_steps)
                    if steps & non_main_steps:
                        if ref in used:
                            order_conflict = True
                            issue(
                                row,
                                "时序引用与场景类型归属待确认：" + i["id"] + "；未进入确定正向交互",
                            )
                        continue
                    if normal:
                        allowed.add("/" + collection + "/" + str(n))
                    elif not steps or not steps <= non_main_steps:
                        issue(row, "未明确正常/异常/备选归属：" + i["id"] + "；原流程补齐")
            numbers = {x["line"] for x in p["json_locations"] if x["json_pointer"] in allowed}
            if order_document and not order_conflict:
                out["SR"].append(order_document)
            if numbers:
                out["SR"].append(
                    {
                        **deepcopy(p["normal_document"]),
                        "lines": [
                            deepcopy(r)
                            for r in p["normal_document"]["lines"]
                            if r["number"] in numbers
                        ],
                    }
                )
        if p["kind"] == "rr_ssd":
            # source_steps are local IDs, so match only a unique RR sibling.
            siblings = [
                s
                for _, s in chosen
                if s["kind"] == "scenarios"
                and s["layer"] == "RR"
                and s["context"].get("group_path") == p["context"].get("group_path")
            ]
            if len(siblings) != 1:
                continue
            main_steps = {
                step["id"]
                for s in siblings[0]["raw"]["scenarios"]
                if s["kind"] == "main"
                for step in s.get("steps", [])
            }
            exceptional_steps = {
                step["id"]
                for s in siblings[0]["raw"]["scenarios"]
                if s["kind"] != "main"
                for step in s.get("steps", [])
            }
            allowed = {"/system_boundary"}
            for n, i in enumerate(p["raw"]["interactions"]):
                steps = set(i.get("source_steps", []))
                if steps and steps <= main_steps and not steps & exceptional_steps:
                    allowed.add("/interactions/" + str(n))
            numbers = {x["line"] for x in p["json_locations"] if x["json_pointer"] in allowed}
            out["RR"].append(
                {
                    **deepcopy(p["normal_document"]),
                    "lines": [
                        deepcopy(r) for r in p["normal_document"]["lines"] if r["number"] in numbers
                    ],
                }
            )
    return out
