"""Read fused SysOperation exports without promoting exception branches to G."""

import json
from copy import deepcopy
from pathlib import PurePosixPath

from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.colleague_formats import Facts
from scene_completion.inputs.structure_models import BRANCH_MARKER


def format_of(value):
    if not isinstance(value, dict):
        return None
    if (
        isinstance(value.get("operations"), dict)
        and isinstance(value.get("use_case"), str)
        and isinstance(value.get("resource"), str)
    ):
        return "system_operations"
    if isinstance(value.get("scenarios"), dict) and isinstance(value.get("use_case"), str):
        return "ordered_ssd"
    if (
        isinstance(value.get("ID"), str)
        and isinstance(value.get("participant"), dict)
        and isinstance(value.get("Order"), list)
        and isinstance(value.get("interaction"), list)
        and isinstance(value.get("action"), list)
    ):
        return "ordered_scenario"
    return None


def group_path(path):
    p = PurePosixPath(str(path).replace("\\", "/"))
    parts = p.parts
    if "behaviour" in parts:
        return "/".join(parts[: parts.index("behaviour")])
    return str(p.parent)


def context_for(path, files):
    group = group_path(path)
    siblings = [f for f in files if group_path(f["path"]) == group]
    names = {f["value"]["use_case"] for f in siblings if f["value"].get("use_case")}
    source = next((f["value"] for f in siblings if format_of(f["value"]) == "ordered_ssd"), None)
    parts = PurePosixPath(str(path).replace("\\", "/")).parts
    return {
        "group_path": group,
        "case_name": next(iter(names)) if len(names) == 1 else None,
        "case_ids": list(
            dict.fromkeys(
                f["value"]["use_case_id"] for f in siblings if f["value"].get("use_case_id")
            )
        ),
        "layer": "RR" if "IR" in parts else "SR" if "SR" in parts else None,
        "outer_ssd": deepcopy(source),
    }


def scenario_kind(record):
    kind = record.get("scenario_kind")
    if kind in {"main", "exception", "alternative", "pending"}:
        return kind
    if (
        record.get("source_key", "").endswith("::main_success")
        or record.get("ID", "").endswith("_main_success")
        or record.get("sourceSD", "").endswith("_main_success")
    ):
        return "main"
    text = json.dumps(record.get("source_refs", []), ensure_ascii=False)
    if "可选场景" in text or "正常备选" in text:
        return "alternative"
    return "pending"


def ordered_nodes(record, *, include_event=False):
    tables = {
        "interaction": record.get("interaction", []),
        "action": record.get("action", []),
        "response": record.get("system_response", []),
        "event": record.get("system_event", []),
    }
    lookup = {}
    for kind, rows in tables.items():
        for row in rows:
            key = (kind, row.get("id"))
            if not isinstance(row.get("id"), str) or key in lookup:
                raise ValueError("行为定义缺少ID或同类型ID重复")
            lookup[key] = row
    selected = []
    seen = set()

    def add(kind, ref):
        key = (kind, ref)
        if key not in lookup:
            raise ValueError("Order引用缺少定义：" + str(key))
        if key not in seen:
            selected.append((kind, lookup[key]))
            seen.add(key)

    if include_event:
        for row in tables["event"]:
            add("event", row["id"])
    for step in record.get("Order", []):
        if not isinstance(step, dict):
            raise ValueError("Order项必须是kind/ref对象")
        add(step.get("kind"), step.get("ref"))
    if include_event:
        for row in tables["response"]:
            add("response", row["id"])
    return selected


def compile_product(value, file_id, name, context, version):
    kind = format_of(value)
    case_name = value.get("use_case") or context.get("case_name")
    layer = context.get("layer") or "SR"
    facts = Facts(file_id + "-ordered", name)
    pending, retained, templates, links = [], [], [], []
    scenario_doc = None

    def warn(obj, reason):
        pending.append({"object": obj, "reason": reason})

    def emit_node(opid, record, node_kind, row, pointer):
        aliases = record.get("participant", {})
        sender = row.get("executor") if node_kind == "action" else row.get("sender")
        receiver = sender if node_kind == "action" else row.get("receiver")
        if sender not in aliases or receiver not in aliases:
            warn(opid, "参与者缩写缺少participant定义")
            return None
        if node_kind == "interaction" and sender == receiver:
            warn(opid, "interaction双方相同：输入数据问题，未自动改成action")
            return None
        refs = facts.add(
            {
                "operation_id": opid,
                "kind": node_kind,
                "node": row,
                "participant": {sender: aliases[sender], receiver: aliases[receiver]},
            },
            pointer,
        )
        text = row.get("content") if node_kind == "action" else row.get("message")
        if not isinstance(text, str) or not text:
            warn(opid, "步骤没有操作文字")
            return None

        def part(alias):
            return {
                "name": aliases[alias]["name"],
                "position": "待确认",
                "source_refs": refs,
            }

        node_layer = "RR" if node_kind in {"event", "response"} else "SR"
        data = []
        for field in row.get("data_ref") or []:
            names = (
                (field.get("fields") or [field.get("entity")])
                if isinstance(field, dict)
                else [field]
            )
            for field_name in names:
                if not isinstance(field_name, str):
                    continue
                prefix, _, rest = field_name.partition(".")
                location = (
                    prefix
                    if prefix in {"header", "path", "query", "body", "response"}
                    else "business"
                )
                data.append(
                    {
                        "name": rest if location != "business" else field_name,
                        "location": location,
                        "data_type": None,
                        "required": None,
                        "default": None,
                        "constraints": [],
                        "source_refs": refs,
                    }
                )
        kinds = list(
            dict.fromkeys(
                d.get("operation")
                for d in row.get("data_ref") or []
                if isinstance(d, dict)
                and d.get("operation") in {"read", "create", "update", "delete", "publish"}
            )
        )
        return {
            "id": "behavior-" + fingerprint([file_id, opid, node_kind, row["id"]])[:24],
            "case_id": case_name or "unbound",
            "sequence": 1,
            "parent_id": None,
            "layer": node_layer,
            "sender": part(sender),
            "receiver": part(receiver),
            "operation": {
                "name": text,
                "kinds": kinds or ["process"],
                "sequence": [text],
                "optional": [],
                "source_refs": refs,
            },
            "data": {"sequence": data},
            "direction": row.get("direction")
            or ("return" if node_kind == "response" else "request"),
            "api_id": row.get("api_id"),
            "source_refs": refs,
            "step_kind": "action" if node_kind == "action" else "interaction",
        }

    if kind == "system_operations":
        operations = value["operations"]
        if not operations:
            raise ValueError("SysOperation.operations不能为空")
        main = [(k, r) for k, r in operations.items() if scenario_kind(r) == "main"]
        outer = context.get("outer_ssd")
        if len(main) > 1:
            order = next(
                (
                    s.get("system_operations")
                    for s in (outer or {}).get("scenarios", {}).values()
                    if scenario_kind(s) == "main"
                ),
                None,
            )
            if not order or set(order) != {k for k, _ in main}:
                warn(case_name, "多个主成功操作段缺少明确跨段排序")
                main = []
            else:
                main = [(k, operations[k]) for k in order]
        for opid, op in main:
            start = len(templates)
            for node_kind, row in ordered_nodes(op, include_event=True):
                converted = emit_node(
                    opid,
                    op,
                    node_kind,
                    row,
                    "/operations/" + pointer_token(opid) + "/" + pointer_for(op, node_kind, row),
                )
                if converted:
                    templates.append(converted)
            segment = templates[start:]
            rr = [i for i in segment if i["layer"] == "RR" and i["direction"] == "request"]
            sr = [i["id"] for i in segment if i["layer"] == "SR"]
            if rr and sr:
                links.append(
                    {
                        "rr_id": rr[0]["id"],
                        "sr_ids": sr,
                        "status": "confirmed",
                        "basis": "输入系统操作段明确的入口与实现范围",
                        "source_refs": rr[0]["source_refs"],
                    }
                )
        retained = [
            {"id": k, "kind": scenario_kind(r)}
            for k, r in operations.items()
            if scenario_kind(r) != "main"
        ]
    elif kind == "ordered_scenario":
        sk = scenario_kind(value)
        if sk == "main":
            for node_kind, row in ordered_nodes(value):
                facts.add(
                    {"kind": node_kind, "node": row, "participant": value["participant"]},
                    "/" + pointer_for(value, node_kind, row),
                )
        elif sk == "exception":
            # Branch data has its own source document, never positive G inputs.
            branch = {
                "id": layer + "::ordered-" + file_id + "::" + value["ID"],
                "case_hint": case_name or "",
                "description": json.dumps(
                    {
                        "trigger": value.get("guard"),
                        "extends": value.get("extend_at_main"),
                        "resume": value.get("resume_at_main"),
                        "interaction": value["interaction"],
                        "action": value["action"],
                    },
                    ensure_ascii=False,
                ),
                "operation_hint": case_name or "",
                "party_hint": "",
            }
            line = BRANCH_MARKER + json.dumps(branch, ensure_ascii=False)
            sid = "import-ordered-existing-" + file_id
            scenario_doc = {
                "source_id": sid,
                "name": name,
                "channel": "existing",
                "lines": [{"number": 1, "text": line}],
            }
        else:
            retained.append({"id": value["ID"], "kind": sk})
            if sk == "pending":
                warn(value["ID"], "分支未明确异常/正常/可选类型，保留待确认，不自动计为E或GT")
    else:
        retained.append({"id": case_name, "kind": "order_context"})
    for source_layer in ("RR", "SR"):
        for n, item in enumerate([i for i in templates if i["layer"] == source_layer], 1):
            item["sequence"] = n
    for n, item in enumerate(templates):
        if item["direction"] == "return":
            parent = next(
                (
                    p
                    for p in reversed(templates[:n])
                    if p["layer"] == item["layer"]
                    and p["direction"] == "request"
                    and p["sender"]["name"] == item["receiver"]["name"]
                    and p["receiver"]["name"] == item["sender"]["name"]
                ),
                None,
            )
            if parent:
                item["parent_id"] = parent["id"]
            else:
                warn(item["id"], "返回没有可定位的反向请求，交由原流程补齐")
    normal = deepcopy(facts.document)
    return {
        "format": "ordered_behavior",
        "version": version,
        "kind": kind,
        "label": {
            "system_operations": "融合系统操作SSD",
            "ordered_ssd": "RR顺序及操作对应",
            "ordered_scenario": "IR/SR已有场景",
        }[kind],
        "layer": layer,
        "case_name": case_name,
        "case_ids": context.get("case_ids", []),
        "context": context,
        "counts": {"interactions": len(templates), "retained": len(retained)},
        "pending": pending,
        "normal_document": normal,
        "scenario_document": scenario_doc,
        "json_locations": facts.locations,
        "scenario_locations": [{"line": 1, "json_pointer": ""}] if scenario_doc else [],
        "retained": retained,
        "target_nodes": ["<用例>:fused-ssd", "<用例>:rr-ssd", "<用例>:sr-ssd"]
        if kind == "system_operations"
        else ["<用例>:existing-branches"]
        if kind == "ordered_scenario"
        else ["<用例>:fused-ssd"],
        "raw": deepcopy(value),
        "fused_template": {"interactions": templates, "rr_sr_links": links, "pending": []},
    }


def fused_candidate(rows, inputs):
    names = {
        inputs["case-group"]["id"],
        *inputs["case-group"].get("rr_ids", []),
        *inputs["case-group"].get("sr_ids", []),
    }
    source_ids = {d["source_id"] for d in inputs["RR"] + inputs["SR"]}
    matches = []
    for row in rows:
        p = row.get("behavior_product") or {}
        if not row.get("behavior_enabled") or p.get("kind") != "system_operations":
            continue
        if (
            p.get("case_name") not in names
            and not set(p.get("case_ids", [])) & names
            and p.get("normal_document", {}).get("source_id") not in source_ids
        ):
            continue
        if p["pending"]:
            continue
        value = deepcopy(p["fused_template"])
        components = {c["name"]: c["composition_type"] for c in inputs["components"]["components"]}
        if not value["interactions"] or any(
            i[s]["name"] not in components
            for i in value["interactions"]
            for s in ("sender", "receiver")
        ):
            continue
        for i in value["interactions"]:
            i["case_id"] = inputs["case-group"]["id"]
            for side in ("sender", "receiver"):
                i[side]["position"] = components[i[side]["name"]]
        # Validate literal imports through the same contract as model results.
        # Incomplete imports remain evidence for the original modeling path.
        from scene_completion.analysis.validation import validate_result

        try:
            validate_result("fused-ssd", value, inputs)
        except (ValueError, KeyError, TypeError):
            continue
        matches.append(value)
    unique = {fingerprint(v): v for v in matches}
    return next(iter(unique.values())) if len(unique) == 1 else None


def pointer_token(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def pointer_for(record, kind, row):
    field = {"event": "system_event", "response": "system_response"}.get(kind, kind)
    index = record[field].index(row)
    return field + "/" + str(index)
