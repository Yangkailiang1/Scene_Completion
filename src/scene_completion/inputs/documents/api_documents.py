"""Build interface work items from the complete mapped catalog, without a second LLM catalog."""

import re

from scene_completion.infrastructure.storage import fingerprint


def case_parameters(inputs, views):
    """Retain only evidenced interfaces used by this case; do not guess unknown IDs."""
    from scene_completion.analysis.interactions.interaction_enrichment import resolved_api_id

    rows = views["interactions"]
    context = {
        **inputs,
        "rr-ssd": {"interactions": [i for i in rows if i["layer"] == "RR"]},
        "sr-ssd": {"interactions": [i for i in rows if i["layer"] == "SR"]},
    }
    used = {i.get("associated_api") or resolved_api_id(i, context) for i in rows}
    used.discard(None)
    if not used:
        return {"apis": []}
    return {
        "apis": [
            {k: v for k, v in a.items() if k != "responses"}
            for a in inputs["api-parameters"]["apis"]
            if a["id"] in used
        ]
    }


def index_interfaces(inputs):
    """Locate source ranges for mapped IDs; never invent a second API identity.

    The model/imported mapping owns the raw interface ID. Method/path and
    literal identifiers only locate its evidence; no project URL prefix is
    required, and a declaration alone does not create an index-only API.
    """
    if inputs.get("interface-scope", {}).get("boundary") == "external":
        from scene_completion.inputs.structured.external_interfaces import index

        return index(inputs["api-map"], inputs)
    docs = {d["source_id"]: d for d in inputs.get("RR", []) + inputs.get("SR", [])}
    found = {}
    for service in inputs["api-map"]["services"]:
        for api in service["interfaces"]:
            signature = (api.get("method"), api.get("address"))
            if api["id"] in found:
                if found[api["id"]][0] != signature:
                    raise ValueError("同一接口标识对应不同方法/地址，请确认接口身份")
                continue
            spans = []
            for sid, d in docs.items():
                lines = d["lines"]
                headings = []
                for n, row in enumerate(lines):
                    match = re.match(r"^(#{1,6})\s+(.+)", row["text"])
                    if match:
                        headings.append((n, len(match[1]), match[2]))
                targets = [
                    (r["line_start"], r["line_end"])
                    for r in api["source_refs"]
                    if r["source_id"] == sid
                ]
                tokens = list(
                    dict.fromkeys(
                        x for x in (api["id"], api.get("declared_id"), api.get("address")) if x
                    )
                )
                patterns = [
                    re.compile(
                        re.escape(t)
                        + (r"(?![A-Za-z0-9_/{}-])" if t.startswith("/") else r"(?![A-Za-z0-9_-])")
                    )
                    for t in tokens
                ]
                targets += [
                    (row["number"], row["number"])
                    for row in lines
                    if any(pattern.search(row["text"]) for pattern in patterns)
                ]
                if api.get("method") and api.get("address"):
                    from scene_completion.inputs.structured.http_interfaces import (
                        call_contract_lines,
                    )

                    targets += [
                        (n, n) for n in call_contract_lines(d, api["method"], api["address"])
                    ]
                for start, end in targets:
                    position = next(
                        (n for n, row in enumerate(lines) if row["number"] >= start), None
                    )
                    if position is None:
                        continue
                    # Only expand an interface-specific ancestor, never a whole
                    # shared API chapter/table. Positive projection stays intact.
                    enclosing = []
                    for n, level, title in headings:
                        stop = next(
                            (m for m, source_line, _ in headings if m > n and source_line <= level),
                            len(lines),
                        )
                        if n <= position < stop and any(
                            t in title for t in (api["id"], api["name"]) if t
                        ):
                            enclosing.append((n, stop))
                    if enclosing:
                        lo, hi = max(enclosing, key=lambda span: span[0])
                        start = lines[lo]["number"]
                        end = lines[hi - 1]["number"]
                    # Bold interface labels and peer success-response headings
                    # belong to the same interface until the next API declaration.
                    markers = [
                        n
                        for n, row in enumerate(lines)
                        if re.match(r"^\s*(?:#{1,6}\s*|\*\*)", row["text"])
                        and any(t and t in row["text"] for t in (api["id"], api["name"]))
                    ]
                    prior = [n for n in markers if n <= position]
                    if prior:
                        lo = max(prior)
                        hi = len(lines)
                        for n in range(lo + 1, len(lines)):
                            text = lines[n]["text"]
                            if (
                                re.match(r"^\s*(?:#{1,6}\s*|\*\*)", text)
                                and re.search(
                                    r"API[-–—][A-Za-z0-9]|\b(?:GET|POST|PUT|PATCH|DELETE)\s+/", text
                                )
                                and not any(t and t in text for t in (api["id"], api["address"]))
                            ):
                                hi = n
                                break
                            if re.match(r"^\s*#\s+", text):
                                hi = n
                                break
                        if lo <= position < hi:
                            start = min(start, lines[lo]["number"])
                            end = max(end, lines[hi - 1]["number"])
                    spans.append({"source_id": sid, "start": start, "end": end})
            unique = {fingerprint(s): s for s in spans}
            if not unique:
                raise ValueError("接口没有可定位的正向原文依据：" + api["id"])
            found[api["id"]] = (
                signature,
                {
                    "id": api["id"],
                    "name": api["name"],
                    "source_ranges": list(unique.values()),
                    "source_refs": api["source_refs"],
                },
            )
    return {"apis": [entry for _, entry in found.values()]}


def explicit_http_interfaces(documents):
    """Literal method/path declarations and calls, not inferred endpoint names."""
    found = {}
    from scene_completion.inputs.structured.http_interfaces import declarations

    for d in documents:
        for row in d["lines"]:
            for method, path in declarations(row["text"]):
                found.setdefault(
                    (method, path),
                    {
                        "source_id": d["source_id"],
                        "line_start": row["number"],
                        "line_end": row["number"],
                        "quote": row["text"],
                    },
                )
    return found


def response_heading(text):
    """Only explicit response declarations, not a mention of an error in prose."""
    title = re.sub(r"^\s*(?:#{1,6}\s*|[-*]\s+)?", "", text).replace("**", "").strip(" ：:")
    if re.search(
        r"失败响应|错误响应|异常响应|错误返回|失败返回|error\s*response|failure\s*response",
        title,
        re.I,
    ):
        kind = "error"
    elif re.search(
        r"成功响应|正常响应|成功返回|响应参数|返回参数|响应体|success\s*response|response\s*(?:body|parameters)|^[245]\d\d\b",
        title,
        re.I,
    ):
        kind = "success"
    else:
        return None
    code = re.search(r"(?<!\d)([245]\d\d)(?!\d)", title)
    if code and code[1][0] in "45":
        kind = "error"
    return kind, code[1] if code else None


def response_contract_documents(documents):
    """Separate error response declarations for review; never positive G inputs.

    Retain interface headings and explicit response tables, excluding failure
    triggers/handling prose. Original line identities and quotes are unchanged.
    """
    from scene_completion.inputs.documents.source_documents import current_projection

    out = []
    for d in current_projection(documents):
        rows = []
        error = False
        table = False
        fenced = False
        for row in d["lines"]:
            text = row["text"].strip()
            heading = response_heading(text)
            if heading:
                error = heading[0] == "error"
                table = False
                fenced = False
                if error:
                    rows.append(row)
            elif re.match(r"^(?:#{1,6}\s*|\*\*)", text):
                error = False
                table = False
                if re.search(r"API[-–—][A-Za-z0-9]", text):
                    rows.append(row)
            elif error and text.startswith("```"):
                fenced = not fenced
                rows.append(row)
            elif error and fenced:
                rows.append(row)
            elif error and re.match(r"^[-*]\s+`?[A-Za-z_][A-Za-z0-9_.\[\]-]*`?\s*[:：(（]", text):
                rows.append(row)
            elif error and text.startswith("|"):
                if re.search(r"参数|字段|name|field", text, re.I):
                    table = True
                if table:
                    rows.append(row)
        if any(r["text"].strip().startswith(("|", "```", "- ", "* ")) for r in rows):
            out.append({**d, "channel": "existing", "lines": rows})
    return out


def _table_parameter(headers, cells, row, doc):
    values = dict(zip(headers, cells))

    def get(*keys):
        return next(
            (values[k] for k in keys if values.get(k) not in (None, "", "—", "-", "待确认")), None
        )

    name = get("参数", "参数名", "参数名称", "字段", "字段名", "字段名称", "名称", "name", "field")
    if not name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.\[\]-]*", name):
        return None
    refs = [
        {
            "source_id": doc["source_id"],
            "line_start": row["number"],
            "line_end": row["number"],
            "quote": row["text"],
        }
    ]
    req = get("必填", "是否必填", "必选", "是否必须", "required")
    required = (
        True
        if req and req.lower() in {"是", "必填", "必选", "true", "y", "required"}
        else False
        if req and req.lower() in {"否", "可选", "false", "n", "optional"}
        else None
    )
    default = get("默认值", "默认", "default")
    dtype = get("数据类型", "类型", "type", "Type")
    if default is not None:
        import json

        try:
            default = json.loads(default)
        except (ValueError, TypeError):
            pass
        if isinstance(default, (dict, list)):
            default = None  # schema only allows scalar/flat list
    constraints = []
    for kind, keys in [
        ("length", ("长度", "长度约束")),
        ("minimum", ("最小值", "下限", "minimum")),
        ("maximum", ("最大值", "上限", "maximum")),
        ("format", ("格式", "格式约束")),
        ("enum", ("枚举", "允许值", "enum")),
        ("other", ("约束", "约束条件")),
    ]:
        value = get(*keys)
        if value is None:
            continue
        if kind in {"minimum", "maximum"}:
            try:
                value = float(value) if "." in value else int(value)
            except ValueError:
                pass
        constraints.append(
            {
                "id": "table-" + fingerprint([doc["source_id"], row["number"], name, kind])[:16],
                "kind": kind,
                "value": value,
                "status": "explicit",
                "source_refs": refs,
            }
        )
    return {
        "name": name,
        "location": "response",
        "data_type": dtype,
        "required": required,
        "default": default,
        "constraints": constraints,
        "source_refs": refs,
    }


def _merge_parameter(known, p):
    """Fill missing attributes; keep distinct evidenced constraints and sources."""
    from copy import deepcopy

    if known is None:
        return deepcopy(p)
    out = deepcopy(known)
    for key in ("data_type", "required", "default"):
        if out.get(key) is None:
            out[key] = deepcopy(p.get(key))
    out["constraints"] = list(
        {
            fingerprint([r["kind"], r["value"]]): r for r in p["constraints"] + out["constraints"]
        }.values()
    )
    out["source_refs"] = list(
        {fingerprint(r): r for r in out["source_refs"] + p["source_refs"]}.values()
    )
    return out


def complete_success_responses(value, inputs):
    """Preserve request/success parameters and separate declared response variants.

    Historical API JSON with only parameters remains valid. Error declarations
    are review-only: never inserted into the positive parameter list.
    """
    from copy import deepcopy

    interface = inputs.get("interface")
    if not interface:
        return value
    out = deepcopy(value)
    apis = [a for a in out.get("apis", []) if a["id"] == interface["id"]]
    if len(apis) != 1:
        return out
    api = apis[0]
    if "method" in interface:
        api["method"] = interface["method"]
    if interface.get("source_layer"):
        api.update(
            source_layer=interface["source_layer"],
            declared_id=interface.get("declared_id", interface["id"]),
        )
    parameters = {(p["location"], p["name"]): p for p in api["parameters"]}
    variants = {(r["kind"], r["status_code"]): deepcopy(r) for r in api.get("responses", [])}
    for doc in inputs.get("RR", []) + inputs.get("SR", []) + inputs.get("response-documents", []):
        context = None
        headers = None
        for row in doc["lines"]:
            text = row["text"].strip()
            heading = response_heading(text)
            if heading:
                context = heading
                headers = None
                continue
            if re.match(r"^(?:#{1,6}\s*|\*\*|[-*]\s)", text):
                if (
                    re.search(r"API[-–—][A-Za-z0-9]", text)
                    and interface.get("declared_id", interface["id"]) not in text
                ):
                    context = None
                elif re.search(r"请求|request", text, re.I):
                    context = None
                headers = None
            if not context or not text.startswith("|"):
                continue
            cells = [
                c.strip().replace("`", "").replace("**", "")
                for c in re.split(r"(?<!\\)\|", text.strip("|"))
            ]
            if all(re.fullmatch(r"[:\s-]+", c) for c in cells):
                continue
            if (
                cells
                and cells[0]
                in {
                    "参数",
                    "参数名",
                    "参数名称",
                    "字段",
                    "字段名",
                    "字段名称",
                    "名称",
                    "name",
                    "field",
                }
                and any(
                    c
                    in {
                        "数据类型",
                        "类型",
                        "type",
                        "Type",
                        "必填",
                        "是否必填",
                        "required",
                        "说明",
                        "描述",
                    }
                    for c in cells[1:]
                )
            ):
                headers = cells
                continue
            if not headers or len(headers) != len(cells):
                continue
            p = _table_parameter(headers, cells, row, doc)
            if not p:
                continue
            kind, code = context
            variant = variants.setdefault(
                context, {"kind": kind, "status_code": code, "parameters": [], "source_refs": []}
            )
            by_name = {v["name"]: v for v in variant["parameters"]}
            by_name[p["name"]] = _merge_parameter(by_name.get(p["name"]), p)
            variant["parameters"] = list(by_name.values())
            variant["source_refs"] = list(
                {fingerprint(r): r for r in variant["source_refs"] + p["source_refs"]}.values()
            )
            if kind == "success" and doc.get("channel") != "existing":
                key = (p["location"], p["name"])
                parameters[key] = _merge_parameter(parameters.get(key), p)
    api["parameters"] = list(parameters.values())
    if variants:
        api["responses"] = list(variants.values())
    return out
