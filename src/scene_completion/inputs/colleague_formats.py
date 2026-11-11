"""Literal adapters for the two colleague positive JSON formats.

Only values in the uploaded file are facts. Error codes, external citations and
missing-constraint notes are never promoted to positive requirements. Unknown
request/response direction or ownership stays visible rather than being guessed.
"""

import json
import re
from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.api_layers import scoped_api_document

VERSION = "colleague-positive-json-v2-response-contract"


def format_of(value):
    if not isinstance(value, dict):
        return None
    if (
        isinstance(value.get("functions"), list)
        and value["functions"]
        and all(
            isinstance(f, dict) and "ucId" in f and "rrLayer" in f and "srLayer" in f
            for f in value["functions"]
        )
    ):
        return "function_tree"
    if (
        isinstance(value.get("apis"), list)
        and value["apis"]
        and all(
            isinstance(a, dict) and {"API序号", "资源路径", "方法"} <= a.keys()
            for a in value["apis"]
        )
    ):
        return "api_extraction"
    return None


class Facts:
    def __init__(self, file_id, name):
        self.document = {
            "source_id": "import-" + file_id + "-facts-v1",
            "name": name + " · 已声明事实.md",
            "channel": "normal",
            "lines": [],
        }
        self.locations = []

    def add(self, value, pointer):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        n = len(self.document["lines"]) + 1
        self.document["lines"].append({"number": n, "text": text})
        self.locations.append({"line": n, "json_pointer": pointer})
        return [
            {"source_id": self.document["source_id"], "line_start": n, "line_end": n, "quote": text}
        ]

    def artifact(self, task, payload, **extra):
        return {
            "task": task,
            "case_hint": None,
            "coverage": "partial",
            "payload": payload,
            "document": deepcopy(self.document),
            "json_locations": deepcopy(self.locations),
            "literal_adapter": VERSION,
            **extra,
        }

    def heading(self, text, pointer):
        n = len(self.document["lines"]) + 1
        self.document["lines"].append({"number": n, "text": "## " + text})
        self.locations.append({"line": n, "json_pointer": pointer})
        return n


def constraints(rules, field, refs):
    out = []

    def add(kind, value, status="explicit"):
        out.append(
            {
                "id": "constraint-" + fingerprint([field, kind, value, refs])[:20],
                "kind": kind,
                "value": value,
                "status": status,
                "source_refs": deepcopy(refs),
            }
        )

    for record in rules:
        rule = record.get("rule") if isinstance(record, dict) else record
        if not isinstance(rule, str) or not rule.strip():
            continue
        text = rule.strip()
        compact = re.sub(r"\s+", "", text).replace("≤", "<=").replace("≥", ">=")
        enum = re.fullmatch(r"\{([^{}]+)\}", text)
        if enum:
            add("enum", [v.strip() for v in re.split(r"[|,，]", enum[1])])
            continue
        if "格式" in text:
            add("format", text)
            continue
        if re.search(r"长度|字符", text):
            add("length", text)
            continue
        if re.search(r"大小|字节|(?:MB|KB|bytes)", text, re.I):
            add("size", text)
            continue
        interval = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(?:至|到|[-~～])\s*(-?\d+(?:\.\d+)?)", text)
        if interval:
            add("minimum", float(interval[1]) if "." in interval[1] else int(interval[1]))
            add("maximum", float(interval[2]) if "." in interval[2] else int(interval[2]))
            continue
        escaped = re.escape(field)
        both = re.fullmatch(r"(-?\d+(?:\.\d+)?)<=\s*" + escaped + r"<=(-?\d+(?:\.\d+)?)", compact)

        def number(x):
            return float(x) if "." in x else int(x)

        if both:
            add("minimum", number(both[1]))
            add("maximum", number(both[2]))
            continue
        lower = re.fullmatch(r"(?:" + escaped + r")?>=(-?\d+(?:\.\d+)?)", compact)
        upper = re.fullmatch(r"(?:" + escaped + r")?<=(-?\d+(?:\.\d+)?)", compact)
        reverse = re.fullmatch(r"(-?\d+(?:\.\d+)?)<=" + escaped, compact)
        if lower or reverse:
            add("minimum", number((lower or reverse)[1]))
            continue
        if upper:
            add("maximum", number(upper[1]))
            continue
        add("other", text)
    return list({fingerprint([c["kind"], c["value"]]): c for c in out}.values())


def parameter(name, location, refs, *, dtype=None, required=None, rules=()):
    return {
        "name": name,
        "location": location,
        "data_type": dtype,
        "required": required,
        "default": None,
        "constraints": constraints(rules, name, refs),
        "source_refs": deepcopy(refs),
    }


def request_parameters(text, facts, pointer, *, response=False):
    """Parse only literal field positions and explicit properties, not prose meaning."""
    parameters = []
    unresolved = []
    segments = []
    chunk = []
    depth = 0
    for char in text or "":
        if char in "（(":
            depth += 1
        elif char in "）)":
            depth = max(0, depth - 1)
        if char in "；;\n" and depth == 0:
            segments.append("".join(chunk))
            chunk = []
        else:
            chunk.append(char)
    if chunk:
        segments.append("".join(chunk))
    for n, segment in enumerate(segments):
        segment = segment.strip()
        if not segment:
            continue
        refs = facts.add(
            {"response_parameter" if response else "request_parameter": segment}, pointer
        )
        m = re.match(
            r"^(header|head|path|query|body|response)\.([A-Za-z_][\w.\[\]-]*)", segment, re.I
        )
        if m:
            location = (
                m[1].lower().replace("head", "header") if m[1].lower() == "head" else m[1].lower()
            )
            name = m[2]
            if (location == "response") != response:
                unresolved.append(
                    {
                        "object": segment,
                        "reason": "字段声明与请求/返回方向不符，未跨方向合并",
                        "source_refs": refs,
                    }
                )
                continue
        elif re.match(r"^Authorization\s+Token\b", segment, re.I):
            location = "header"
            name = "Authorization"
        else:
            unresolved.append(
                {
                    "object": segment,
                    "reason": "未声明字段位置，需补充后才能绑定；不把未知字段猜作body",
                    "source_refs": refs,
                }
            )
            continue
        required_flag = re.search(r"[（(]\s*(必填|必选|可选)", segment)
        required = (required_flag[1] != "可选") if required_flag else None
        p = parameter(name, location, refs, required=required)
        type_ = re.search(
            r"(?:类型\s*[:：=]\s*|\btype\s*[:=]\s*)(integer|int|string|number|boolean|array|object)\b",
            segment,
            re.I,
        )
        if type_:
            p["data_type"] = {"int": "integer"}.get(type_[1].lower(), type_[1].lower())
        default = re.search(r"默认(?:值)?\s*[:：=]?\s*(-?\d+(?:\.\d+)?|true|false)", segment, re.I)
        if default:
            p["default"] = json.loads(default[1].lower())
        rules = []
        opening = next((pos for pos, char in enumerate(segment) if char in "（("), None)
        if opening is not None:
            detail = segment[opening + 1 :].rstrip("）)")
            for clause in re.split(r"[；;]", detail):
                clause = clause.strip()
                if not clause or re.match(
                    r"^(必填|必选|可选|类型\s*[:：]|type\s*[:=]|默认)", clause, re.I
                ):
                    continue
                enum = re.fullmatch(r"枚举\s*(\{.*\})", clause)
                rules.append({"rule": enum[1] if enum else clause})
        p["constraints"] = constraints(rules, name, refs)
        parameters.append(p)
    return parameters, unresolved


def api_product(value, file_id, name):
    facts = Facts(file_id, name)
    services = {}
    apis = []
    pending = []
    seen = set()
    ranges = {}
    for n, api in enumerate(value["apis"]):
        aid = api["API序号"]
        method = api["方法"]
        path = api["资源路径"]
        pointer = "/apis/" + str(n)
        if not isinstance(aid, str) or not aid or aid in seen:
            raise ValueError("接口编号缺失或重复：" + str(aid))
        seen.add(aid)
        start = facts.heading(
            aid + " " + str(api.get("接口名称") or aid) + " " + str(method) + " " + str(path),
            pointer,
        )
        layer = api.get("source_layer") or ("SR" if api.get("SR编号") else None)
        if layer not in {"RR", "SR"}:
            raise ValueError("接口未声明RR/SR归属：" + aid)
        units = [
            u["name"]
            for u in value.get("software_units", [])
            if aid in u.get("api_keys", [])
            and u.get("review_status", "confirmed") == "confirmed"
            and not u.get("candidate")
        ]
        owners = units or [
            s["name"] for s in value.get("services", []) if aid in s.get("api_keys", [])
        ]
        owners = list(dict.fromkeys(owners))
        refs = facts.add(
            {
                "api_id": aid,
                "name": api.get("接口名称") or aid,
                "method": method,
                "address": path,
                "source_layer": layer,
                "implementing_services": owners,
            },
            pointer,
        )
        if len(owners) == 1:
            services.setdefault((layer, owners[0]), []).append(
                {
                    "id": aid,
                    "declared_id": aid,
                    "name": api.get("接口名称") or aid,
                    "method": method,
                    "address": path,
                    "source_layer": layer,
                    "source_refs": refs,
                }
            )
        else:
            pending.append(
                {
                    "object": aid,
                    "reason": "所属服务缺失或有多个候选；不按URL或名称猜测",
                    "source_refs": refs,
                }
            )
        ps, unknown = request_parameters(
            api.get("API请求参数", ""), facts, pointer + "/API请求参数"
        )
        pending += unknown
        responses = []
        if api.get("API成功响应参数"):
            success, unknown = request_parameters(
                api["API成功响应参数"], facts, pointer + "/API成功响应参数", response=True
            )
            pending += unknown
            ps += success
            responses.append(
                {
                    "kind": "success",
                    "status_code": str(api["成功状态码"])
                    if api.get("成功状态码") is not None
                    else None,
                    "parameters": success,
                    "source_refs": [r for p in success for r in p["source_refs"]],
                }
            )
        for j, error in enumerate(api.get("API失败响应", [])):
            error_ps, unknown = request_parameters(
                error.get("参数", ""),
                facts,
                pointer + "/API失败响应/" + str(j) + "/参数",
                response=True,
            )
            pending += unknown
            responses.append(
                {
                    "kind": "error",
                    "status_code": str(error["状态码"])
                    if error.get("状态码") is not None
                    else None,
                    "parameters": error_ps,
                    "source_refs": [r for p in error_ps for r in p["source_refs"]],
                }
            )
        apis.append(
            {
                "id": aid,
                "declared_id": aid,
                "name": api.get("接口名称") or aid,
                "method": method,
                "address": path,
                "source_layer": layer,
                "parameters": ps,
                "responses": responses,
                "source_refs": refs,
            }
        )
        ranges[aid] = (start, len(facts.document["lines"]))
    artifacts = []
    for layer in ("RR", "SR"):
        rows = [
            {
                "name": owner,
                "interfaces": entries,
                "source_refs": list(
                    {fingerprint(r): r for a in entries for r in a["source_refs"]}.values()
                ),
            }
            for (kind, owner), entries in services.items()
            if kind == layer
        ]
        if rows:
            artifact = facts.artifact(
                "api-map",
                {"services": rows},
                source_layer=layer,
                coverage="complete"
                if not any(
                    p["object"] in {a["id"] for a in apis if a["source_layer"] == layer}
                    for p in pending
                    if "所属服务" in p["reason"]
                )
                else "partial",
                coverage_details={
                    "interface_inventory": "complete",
                    "project_inventory": "file_scope_only",
                },
            )
            artifact["document"] = scoped_api_document(artifact["document"], layer)
            line_numbers = {r["number"] for r in artifact["document"]["lines"]}
            artifact["json_locations"] = [
                location
                for location in artifact["json_locations"]
                if location["line"] in line_numbers
            ]
            artifacts.append(artifact)
        for a in apis:
            if a["source_layer"] == layer:
                artifact = facts.artifact(
                    "api-parameters",
                    {"apis": [a]},
                    source_layer=layer,
                    coverage_details={
                        "request": "declared_fields",
                        "success_response": "declared_fields"
                        if any(r["kind"] == "success" for r in a["responses"])
                        else "not_supplied",
                        "error_response": "declared_fields"
                        if any(r["kind"] == "error" for r in a["responses"])
                        else "not_supplied",
                    },
                )
                lo, hi = ranges[a["id"]]
                artifact["document"]["lines"] = [
                    r for r in artifact["document"]["lines"] if lo <= r["number"] <= hi
                ]
                artifacts.append(artifact)
    return {
        "format": "api_extraction",
        "artifacts": artifacts,
        "pending": pending,
        "counts": {
            "interfaces": len(apis),
            "services": len(services),
            "request_fields": sum(
                sum(p["location"] != "response" for p in a["parameters"]) for a in apis
            ),
            "success_response_fields": sum(
                sum(p["location"] == "response" for p in a["parameters"]) for a in apis
            ),
        },
        "case_scopes": [],
    }


def function_interfaces(value, file_id, name):
    """Project the tree's declared SR interfaces and positive field evidence."""
    from scene_completion.inputs.api_identity import qualified_identity

    facts = Facts(file_id + "-interfaces", name)
    entries = []
    for n, case in enumerate(value["functions"]):
        commands = {}
        for j, command in enumerate(case["rrLayer"].get("commands", [])):
            commands.setdefault(command["apiId"], []).append((j, command))
        for j, details in enumerate(case["srLayer"].get("commands", [])):
            api_id = details["apiId"]
            for source_no, source in commands.get(api_id, []):
                layer = source.get("source_layer")
                if layer is None:
                    marker = re.search(r"(?<!\w)(RR|SR)(?!\w)", str(source.get("source", "")))
                    layer = marker[1] if marker else None
                if layer != "SR":
                    continue
                ident, declared_id = qualified_identity({"id": api_id}, "SR")
                entry = {
                    "case_id": case["ucId"],
                    "case_name": case.get("name") or case["ucId"],
                    "api_id": declared_id,
                    "qualified_id": ident,
                    "name": source.get("name") or api_id,
                    "method": source.get("method"),
                    "address": source.get("path"),
                    "source_layer": layer,
                }
                entry["source_refs"] = facts.add(
                    entry, f"/functions/{n}/rrLayer/commands/{source_no}"
                )
                entry["attributes"] = []
                for k, attr in enumerate(details.get("attributes", [])):
                    field = {
                        key: attr[key]
                        for key in (
                            "name",
                            "type",
                            "tags",
                            "location",
                            "direction",
                            "required",
                            "default",
                        )
                        if key in attr
                    }
                    field["rules"] = [
                        rule["rule"]
                        for rule in attr.get("constraints", [])
                        if isinstance(rule, dict) and isinstance(rule.get("rule"), str)
                    ]
                    field["source_refs"] = facts.add(
                        field, f"/functions/{n}/srLayer/commands/{j}/attributes/{k}"
                    )
                    entry["attributes"].append(field)
                entries.append(entry)
    return {
        "interface_declarations": entries,
        "interface_document": facts.document,
        "interface_locations": facts.locations,
    }


def function_product(value, file_id, name):
    facts = Facts(file_id, name)
    entities = {}
    scopes = []
    interface_attributes = []
    pending = []
    seen = set()
    for n, f in enumerate(value["functions"]):
        cid = f["ucId"]
        label = f.get("name") or cid
        p = "/functions/" + str(n)
        if cid in seen:
            raise ValueError("功能树用例ID重复：" + cid)
        seen.add(cid)
        scopes.append({"case_id": cid, "case_name": label})
        names = {e["name"]: e for e in f["rrLayer"].get("entities", [])}
        for e in f["srLayer"].get("entities", []):
            names.setdefault(e["entity"], {"name": e["entity"]})
        for ename, entry in names.items():
            refs = facts.add(
                {
                    "case_id": cid,
                    "case_name": label,
                    "entity": ename,
                    "name": entry.get("zh") or ename,
                },
                p + "/rrLayer/entities",
            )
            target = entities.setdefault(
                ename,
                {
                    "id": ename,
                    "name": entry.get("zh") or ename,
                    "attributes": [],
                    "business_rules": [],
                    "source_refs": [],
                },
            )
            target["source_refs"] += refs
            for en, detail in enumerate(f["srLayer"].get("entities", [])):
                if detail["entity"] != ename:
                    continue
                for an, a in enumerate(detail.get("attributes", [])):
                    safe = {k: a[k] for k in ("name", "type", "tags") if k in a}
                    safe.update(
                        case_id=cid,
                        entity=ename,
                        rules=[
                            c["rule"]
                            for c in a.get("constraints", [])
                            if isinstance(c, dict) and isinstance(c.get("rule"), str)
                        ],
                    )
                    ref = facts.add(
                        safe, p + "/srLayer/entities/" + str(en) + "/attributes/" + str(an)
                    )
                    tags = a.get("tags", [])
                    dtype = {
                        "int": "integer",
                        "decimal": "number",
                        "object[]": "array",
                        "string[]": "array",
                        "url": "string",
                        "enum": None,
                    }.get(a.get("type"), a.get("type"))
                    target["attributes"].append(
                        {
                            "name": a["name"],
                            "data_type": dtype,
                            "required": True
                            if "必填" in tags
                            else False
                            if "可选" in tags
                            else None,
                            "operation": "any",
                            "case_ids": [cid],
                            "case_names": [label],
                            "constraints": constraints(a.get("constraints", []), a["name"], ref),
                            "source_refs": ref,
                        }
                    )
        commands = {c["apiId"]: c for c in f["rrLayer"].get("commands", [])}
        for cn, c in enumerate(f["srLayer"].get("commands", [])):
            original = commands.get(c["apiId"], {})
            declared = re.search(r"(?<!\w)(RR|SR)(?!\w)", str(original.get("source", "")))
            for an, a in enumerate(c.get("attributes", [])):
                safe = {k: a[k] for k in ("name", "type", "tags") if k in a}
                safe.update(
                    case_id=cid,
                    api_id=c["apiId"],
                    method=original.get("method"),
                    address=original.get("path"),
                    rules=[
                        r["rule"]
                        for r in a.get("constraints", [])
                        if isinstance(r, dict) and isinstance(r.get("rule"), str)
                    ],
                )
                refs = facts.add(
                    safe, p + "/srLayer/commands/" + str(cn) + "/attributes/" + str(an)
                )
                # Do not infer direction from a name such as items[] or from
                # HTTP GET. Later join requires a known field on this exact API.
                interface_attributes.append(
                    {
                        "case_id": cid,
                        "case_name": label,
                        "api_id": c["apiId"],
                        "source_layer": declared[1] if declared else None,
                        "method": original.get("method"),
                        "address": original.get("path"),
                        "attribute": safe,
                        "source_refs": refs,
                    }
                )
    for n, m in enumerate(value.get("missingConstraints", [])):
        refs = facts.add(
            {"missing_constraint": {k: m[k] for k in ("function", "node", "reason") if k in m}},
            "/missingConstraints/" + str(n),
        )
        pending.append(
            {
                "object": str(m.get("node", "未指定属性")),
                "reason": str(m.get("reason", "约束未给出")),
                "source_refs": refs,
            }
        )
    payload = {"entities": list(entities.values()), "pending": pending}
    return {
        "format": "function_tree",
        **function_interfaces(value, file_id, name),
        "artifacts": [
            facts.artifact(
                "business-entities",
                payload,
                coverage_details={
                    "case_scopes": scopes,
                    "attributes": "declared_only",
                    "project_inventory": "partial",
                },
            )
        ],
        "pending": pending,
        "case_scopes": scopes,
        "interface_attributes": interface_attributes,
        "document": deepcopy(facts.document),
        "json_locations": facts.locations,
        "counts": {
            "use_cases": len(scopes),
            "entities": len(entities),
            "scoped_attributes": sum(len(e["attributes"]) for e in entities.values()),
            "interface_attributes": len(interface_attributes),
        },
    }


def convert(value, file_id, name):
    kind = format_of(value)
    if kind == "api_extraction":
        return api_product(value, file_id, name)
    if kind == "function_tree":
        return function_product(value, file_id, name)
    return None


def scoped_entities(value, case_ids):
    """Preserve operation/use-case specificity; never globally union states."""
    out = deepcopy(value)
    scope = set(case_ids)
    for e in out["entities"]:
        e["attributes"] = [
            a
            for a in e["attributes"]
            if not a.get("case_ids") or scope.intersection(a["case_ids"] + a.get("case_names", []))
        ]
    # Entity identity remains usable by CRUD even when its attributes are not
    # declared for this case (or no attribute was provided at all).
    return out


def uncovered_entity_documents(documents, parts):
    """Only skip explicitly covered case sections, never an unprovided scope."""
    from scene_completion.inputs.structure_models import CASE_MARKER, MARKER, model_layer

    covered = {
        x[k]
        for p in parts
        for x in p.get("coverage_details", {}).get("case_scopes", [])
        for k in ("case_id", "case_name")
    }
    if not covered:
        return documents
    out = []
    for doc in documents:
        if model_layer(doc) is None:
            out.append(doc)
            continue
        sections = []
        current = []
        for row in doc["lines"]:
            if row["text"].startswith("## "):
                if current:
                    sections.append(current)
                current = []
            current.append(row)
        if current:
            sections.append(current)
        for section in sections:
            marker = next((r for r in section if r["text"].startswith(CASE_MARKER)), None)
            if not marker:
                continue  # The compiled preamble contains only actors/components, not business attributes.
            case = json.loads(marker["text"][len(CASE_MARKER) : -4])
            if case["id"] in covered or case["name"] in covered:
                continue
            header = [r for r in doc["lines"] if r["text"].startswith(MARKER)]
            out.append({**doc, "lines": header + section})
    return out


def interface_requirements(interaction, parameters, inputs):
    """Join function-tree attributes only to already located fields on the exact API.

    This never guesses whether an unlocated items[] is input or output and never
    transfers an internal constraint to a public request with the same API ID.
    """
    from scene_completion.analysis.interaction_enrichment import resolved_api_id

    api_id = resolved_api_id(interaction, inputs)
    apis = inputs.get("api-parameters", {}).get("apis", [])
    api = next((a for a in apis if a["id"] == api_id), None)
    if not api:
        return parameters
    for item in inputs.get("colleague-interface-attributes", []):
        if (
            item.get("source_layer") != api.get("source_layer")
            or not item.get("address")
            or item["address"] != api.get("address")
            or not item.get("method")
            or item["method"].upper() != (api.get("method") or "").upper()
        ):
            continue
        own = [p for p in parameters if p["name"] == item["attribute"]["name"]]
        if len(own) != 1:
            continue
        locations = {
            p["location"] for p in api["parameters"] if p["name"] == item["attribute"]["name"]
        }
        if len(locations) != 1 or own[0]["location"] not in locations:
            continue
        p = own[0]
        a = item["attribute"]
        dtype = {
            "int": "integer",
            "decimal": "number",
            "object[]": "array",
            "string[]": "array",
            "url": "string",
            "enum": None,
        }.get(a.get("type"), a.get("type"))
        if p["data_type"] is None:
            p["data_type"] = dtype
        tags = a.get("tags", [])
        if "必填" in tags:
            p["required"] = True
        elif p["required"] is None and "可选" in tags:
            p["required"] = False
        extra = constraints(a.get("rules", []), p["name"], item["source_refs"])
        p["constraints"] = list(
            {fingerprint([c["kind"], c["value"]]): c for c in p["constraints"] + extra}.values()
        )
        p["source_refs"] = list(
            {fingerprint(r): r for r in p["source_refs"] + item["source_refs"]}.values()
        )
    return parameters


def business_requirements(interaction, parameters, inputs):
    """Intrinsic entity properties can enrich an already located same-name field.

    Entity mandatory/storage annotations never invent API wire requiredness.
    Distinct business entities or unknown actual CRUD identity remain unresolved.
    """
    rows = [
        r
        for r in inputs.get("business-crud", {}).get("rows", [])
        if r["interaction_id"] in {interaction["id"], interaction.get("parent_id")}
    ]
    if not rows:
        return parameters
    entities = {e["id"]: e for e in inputs.get("business-entities", {}).get("entities", [])}
    rows = [r for r in rows if r.get("entity_id") in entities]
    if not rows:
        return parameters
    for p in parameters:
        hits = {}
        for row in rows:
            for a in entities.get(row["entity_id"], {}).get("attributes", []):
                if a["name"] == p["name"] and a["operation"] in ("any", row["operation"]):
                    hits.setdefault(row["entity_id"], []).append(a)
        if len(hits) != 1:
            continue
        for a in next(iter(hits.values())):
            if p["data_type"] is None:
                p["data_type"] = a["data_type"]
            elif a["data_type"] and a["data_type"] != p["data_type"]:
                p["constraints"].append(
                    {
                        "id": "entity-type-" + fingerprint([p["name"], a["data_type"]])[:20],
                        "kind": "type",
                        "value": a["data_type"],
                        "status": "explicit",
                        "source_refs": a["source_refs"],
                    }
                )
            p["constraints"] = list(
                {
                    fingerprint([c["kind"], c["value"]]): deepcopy(c)
                    for c in p["constraints"] + a["constraints"]
                }.values()
            )
            p["source_refs"] = list(
                {fingerprint(r): r for r in p["source_refs"] + a["source_refs"]}.values()
            )
    return parameters
