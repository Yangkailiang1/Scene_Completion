from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint


def stable(prefix, value):
    return prefix + "-" + fingerprint(value)[:20]


def resource_service_name(name):
    return name + "资源服务"


def interactions(inputs):
    return [
        i for layer in ("rr-ssd", "sr-ssd") for i in inputs.get(layer, {}).get("interactions", [])
    ]


def resolved_api_id(i, inputs):
    import re

    from scene_completion.inputs.api_layers import candidates_for_layer
    from scene_completion.inputs.http_interfaces import declarations

    apis = inputs.get("api-parameters", inputs.get("normal-constraints", {})).get("apis", [])
    if i["direction"] == "return" and i.get("parent_id"):
        request = next(
            (
                x
                for x in interactions(inputs)
                if x["id"] == i["parent_id"]
                and x["direction"] == "request"
                and x["case_id"] == i["case_id"]
            ),
            None,
        )
        if request and not i.get("api_id"):
            linked = resolved_api_id(request, inputs)
            if linked:
                return linked
    api_id = i.get("associated_api") or i.get("api_id")

    def normalize(x):
        return re.sub(r"\s+", "", str(x)).replace("–", "-").replace("—", "-").casefold()

    eligible = apis if api_id and "::" in api_id else candidates_for_layer(apis, i.get("layer"))
    exact = [
        a["id"]
        for a in eligible
        if api_id
        and normalize(a.get("declared_id", a["id"])) == normalize(api_id)
        or api_id
        and normalize(a["id"]) == normalize(api_id)
    ]
    if len(set(exact)) == 1:
        return exact[0]
    calls = declarations(i["operation"]["name"])
    explicit_call = calls[0] if len(calls) == 1 else None
    found = {
        a["id"]
        for a in apis
        if explicit_call
        and a.get("method")
        and a["method"].upper() == explicit_call[0]
        and a.get("address") == explicit_call[1]
    }
    for service in inputs.get("api-map", {}).get("services", []):
        for interface in service["interfaces"]:
            by_call = (
                explicit_call
                and interface.get("method")
                and interface["method"].upper() == explicit_call[0]
                and interface.get("address") == explicit_call[1]
            )
            by_name = (
                service["name"] == i["receiver"]["name"]
                and interface["name"] == i["operation"]["name"]
                and interface.get("source_layer") in (None, i.get("layer"))
            )
            if not (by_call or by_name):
                continue
            targets = [a for a in apis if a["id"] == interface["id"]]
            if not targets:
                targets = [
                    a
                    for a in apis
                    if a.get("source_layer") == interface.get("source_layer")
                    and a.get("address") == interface.get("address")
                    and a.get("address")
                ]
            found.update(a["id"] for a in targets)
    if len(found) == 1:
        return next(iter(found))
    # A literal interface ID in the operation is scoped by its document layer.
    mentioned = [
        a["id"]
        for a in eligible
        if re.match(r"API[-_]", a.get("declared_id", a["id"]), re.I)
        and re.search(
            r"(?<![A-Za-z0-9_/-])"
            + re.escape(a.get("declared_id", a["id"]))
            + r"(?![A-Za-z0-9_-])",
            i["operation"]["name"],
        )
    ]
    return mentioned[0] if len(set(mentioned)) == 1 else None


def parameters_for(i, inputs):
    is_return = i["direction"] == "return"

    def valid(p):
        return p["location"] == "response" if is_return else p["location"] != "response"

    def actual_valid(p):
        return (
            p["location"] in {"response", "business"} if is_return else p["location"] != "response"
        )

    params = [deepcopy(p) for p in i["data"]["sequence"] if actual_valid(p)]
    api_id = resolved_api_id(i, inputs)
    if api_id:
        apis = [a for a in inputs.get("api-parameters", {}).get("apis", []) if a["id"] == api_id]
        if len(apis) > 1:
            raise ValueError("duplicate API identity")
        if apis:
            # Use the evidenced union, not a requirements-consistency check.
            # API-only and SSD-only fields/constraints both remain available.
            # 'business' is a compact SSD placeholder, not a competing wire
            # location. Resolve it only when this exact API declares one field
            # of that name in the current direction.
            candidates = {}
            for declared in apis[0]["parameters"]:
                if valid(declared):
                    candidates.setdefault(declared["name"], set()).add(declared["location"])
            for actual in params:
                locations = candidates.get(actual["name"], set())
                if actual["location"] == "business" and len(locations) == 1:
                    actual["location"] = next(iter(locations))
            by_name = {(p["location"], p["name"]): p for p in params}
            for p in apis[0]["parameters"]:
                if not valid(p):
                    continue
                p = deepcopy(p)
                actual = by_name.get((p["location"], p["name"]))
                if actual:
                    if p["data_type"] is None:
                        p["data_type"] = actual["data_type"]
                    elif actual["data_type"] is not None and p["data_type"] != actual["data_type"]:
                        p["constraints"].append(
                            {
                                "id": stable(
                                    "source-type", [p["location"], p["name"], actual["data_type"]]
                                ),
                                "kind": "type",
                                "value": actual["data_type"],
                                "status": "explicit",
                                "source_refs": deepcopy(actual["source_refs"]),
                            }
                        )
                    p["required"] = (
                        True
                        if p["required"] is True or actual["required"] is True
                        else p["required"]
                        if p["required"] is not None
                        else actual["required"]
                    )
                    if p["default"] is None:
                        p["default"] = deepcopy(actual["default"])
                    merged = {}
                    for r in p["constraints"] + actual["constraints"]:
                        key = fingerprint([r["kind"], r["value"]])
                        if key not in merged:
                            merged[key] = deepcopy(r)
                        else:
                            row = merged[key]
                            row["source_refs"] = list(
                                {
                                    fingerprint(x): x for x in row["source_refs"] + r["source_refs"]
                                }.values()
                            )
                            if r["status"] == "explicit":
                                row["status"] = "explicit"
                    p["constraints"] = list(merged.values())
                    p["source_refs"] = list(
                        {
                            fingerprint(r): r for r in p["source_refs"] + actual["source_refs"]
                        }.values()
                    )
                by_name[(p["location"], p["name"])] = p
            params = list(by_name.values())
    from scene_completion.inputs.colleague_formats import (
        business_requirements,
        interface_requirements,
    )

    return business_requirements(i, interface_requirements(i, params, inputs), inputs)


def requirement_sources(i, inputs):
    """Display-only provenance; differing requirements are not new faults."""
    groups = {}

    def add(p, origin):
        if i["direction"] == "return":
            if p["location"] not in ({"response", "business"} if origin == "SSD" else {"response"}):
                return
        elif p["location"] == "response":
            return
        groups.setdefault((p["location"], p["name"]), []).append(
            {
                "origin": origin,
                **{
                    k: deepcopy(p[k])
                    for k in ("data_type", "required", "default", "constraints", "source_refs")
                },
            }
        )

    api_id = resolved_api_id(i, inputs)
    declarations = [
        p
        for a in inputs.get("api-parameters", {}).get("apis", [])
        if a["id"] == api_id
        for p in a["parameters"]
        if (p["location"] == "response") == (i["direction"] == "return")
    ]
    for p in i["data"]["sequence"]:
        p = deepcopy(p)
        locations = {d["location"] for d in declarations if d["name"] == p["name"]}
        if p["location"] == "business" and len(locations) == 1:
            p["location"] = next(iter(locations))
        add(p, "SSD")
    for a in inputs.get("api-parameters", {}).get("apis", []):
        if a["id"] == api_id:
            for p in a["parameters"]:
                add(p, "API")
    return [
        {"name": name, "location": location, "sources": rows}
        for (location, name), rows in groups.items()
    ]


def bind_resource_services(inputs):
    """Canonical SR view retains physical objects and logical-only mappings."""
    inputs = deepcopy(inputs)
    if "components" not in inputs or "sr-ssd" not in inputs:
        return inputs
    components = inputs["components"]["components"]
    meta = resource_metadata(inputs["components"])
    by_physical = {c["id"]: c for c in components}
    by_name = {by_physical[s["physical_resource_id"]]["name"]: s for s in meta["resource_services"]}
    for i in inputs["sr-ssd"]["interactions"]:
        for side in ("sender", "receiver"):
            p = i[side]
            if p["name"] in by_name:
                p["name"] = by_name[p["name"]]["name"]
                p["position"] = "内部服务（SR逻辑资源服务）"
    return inputs


def capability_union(inputs):
    """Summarize evidenced capabilities; never feed these back into SSD/G."""
    objects = {}

    def add(name, op, refs):
        if not name or not op:
            return
        c = canonical_name(name, inputs["components"]["components"])
        name = c["name"] if c else name
        by_op = objects.setdefault(name, {})
        by_op.setdefault(op, []).extend(refs)

    for i in inputs["rr-ssd"]["interactions"]:
        if i["direction"] == "request":
            add(i["receiver"]["name"], i["operation"]["name"], i["operation"]["source_refs"])
            for op in i["operation"]["sequence"] + i["operation"]["optional"]:
                add(i["receiver"]["name"], op, i["operation"]["source_refs"])
    for item in inputs["test-operations"]["objects"]:
        for op in item["supported_operations"]:
            add(item["name"], op["name"], op["source_refs"])
    return {
        "objects": [
            {
                "name": name,
                "supported_operations": [
                    {"name": op, "source_refs": list({fingerprint(r): r for r in refs}.values())}
                    for op, refs in sorted(ops.items())
                ],
            }
            for name, ops in sorted(objects.items())
        ]
    }


def resource_metadata(payload):
    services = []
    mappings = []
    for c in payload["components"]:
        if c["composition_type"] not in {"内部数据库", "外部数据库"}:
            continue
        sid = stable("resource-service", c["id"])
        services.append(
            {
                "node_id": sid,
                "name": resource_service_name(c["name"]),
                "kind": "internal_service",
                "service_role": "resource_service",
                "physical_resource_id": c["id"],
                "logical_only": True,
                "resource_origin": "internal"
                if c["composition_type"] == "内部数据库"
                else "external",
                "source_refs": c["source_refs"],
            }
        )
        mappings.append(
            {
                "physical_resource_id": c["id"],
                "logical_service_id": sid,
                "source_refs": c["source_refs"],
            }
        )
    return {"resource_services": services, "resource_mappings": mappings}


def canonical_name(name, components, aliases=()):
    def normalize(s):
        return "".join(s.casefold().split())

    rows = [c for c in components if normalize(c["name"]) == normalize(name)]
    rows += [
        c for a in aliases if a["name"] == name for c in components if a["component_id"] == c["id"]
    ]
    unique = {c["id"]: c for c in rows}
    return next(iter(unique.values())) if len(unique) == 1 else None


def enrich(inputs, alignment):
    """Bindings/capabilities enrich views without creating or changing actual operations."""
    value = bind_resource_services(inputs)
    components = value["components"]["components"]
    services = resource_metadata(value["components"])["resource_services"]
    capabilities = value["object-operations"]["objects"]
    pending = []
    views = []
    for i in interactions(value):
        i = deepcopy(i)
        for side in ("sender", "receiver"):
            party = i[side]
            c = canonical_name(party["name"], components, alignment["aliases"])
            logical = next((s for s in services if s["name"] == party["name"]), None)
            party["component_id"] = (
                c["id"] if c else (logical["physical_resource_id"] if logical else None)
            )
            if c:
                party.update(name=c["name"], position=c["composition_type"])
            party["resource_service"] = logical
            party["supported_operations"] = (
                [
                    op
                    for row in capabilities
                    if canonical_name(row["name"], components, alignment["aliases"]) == c
                    and c is not None
                    or row["name"] == party["name"]
                    for op in row["supported_operations"]
                ]
                if side == "receiver"
                else []
            )
            party["concerns"] = []
            if not party["component_id"]:
                pending.append(
                    {
                        "interaction_id": i["id"],
                        "reason": side + "在系统组成中的位置待确认",
                        "source_refs": party["source_refs"],
                    }
                )
        # SR services expose evidenced API operations in addition to the RR
        # capability table; these never replace the actual operation.
        if i["layer"] == "SR":
            for service in value["api-map"]["services"]:
                if service["name"] == i["receiver"]["name"]:
                    i["receiver"]["supported_operations"] += [
                        {"name": a["name"], "source_refs": a["source_refs"]}
                        for a in service["interfaces"]
                    ]
        i["parameter_requirement_sources"] = requirement_sources(i, value)
        from scene_completion.analysis.data_requirements import positive_parameters

        i["data"]["sequence"] = positive_parameters(i, value)
        i["associated_api"] = resolved_api_id(i, value)
        if i["api_id"] and not i["associated_api"]:
            pending.append(
                {
                    "interaction_id": i["id"],
                    "reason": "API标识未能唯一关联已验证接口表；不以全量接口表兜底，相关属性待确认",
                    "source_refs": i["source_refs"],
                }
            )
        i["data"]["concerns"] = []
        if not i["receiver"]["supported_operations"] or i["operation"]["name"] not in {
            o["name"] for o in i["receiver"]["supported_operations"]
        }:
            pending.append(
                {
                    "interaction_id": i["id"],
                    "reason": "本次操作未在接收方能力表中得到对应，需核对；不得据此改写操作",
                    "source_refs": i["operation"]["source_refs"],
                }
            )
        from scene_completion.domain.interaction_types import classify

        i["classification"] = classify(i, interactions(value))
        views.append(i)
    for rr in value["rr-ssd"]["interactions"]:
        if not any(
            source_line["rr_id"] == rr["id"] and source_line["status"] == "confirmed"
            for source_line in alignment["links"]
        ):
            pending.append(
                {
                    "interaction_id": rr["id"],
                    "reason": "RR步骤—SR展开对应待确认",
                    "source_refs": rr["source_refs"],
                }
            )
    return {
        "interactions": views,
        "rr_sr_links": alignment["links"],
        "pending": pending,
        "resource_mappings": resource_metadata(value["components"])["resource_mappings"],
    }


def with_concerns(enriched, matches):
    view = deepcopy(enriched)
    for i in view["interactions"]:
        for m in matches["matches"]:
            if m["interaction_id"] == i["id"]:
                target = i["data"] if m["target"] == "data" else i[m["target"]]
                target.setdefault("concerns", []).append(m)
    return view


def actual_context(enriched):
    """G cannot see unrelated supported capabilities or test-operation evidence."""
    v = deepcopy(enriched)
    for i in v["interactions"]:
        for side in ("sender", "receiver"):
            i[side]["supported_operations"] = [
                op for op in i[side]["supported_operations"] if op["name"] == i["operation"]["name"]
            ]
    return v


def basic_views(enriched):
    """Expose the canonical four-tuples without enrichment-only machine fields."""
    from scene_completion.domain.contracts import INTERACTION, PARTY

    result = {"rr-ssd": {"interactions": []}, "sr-ssd": {"interactions": []}}
    for i in enriched["interactions"]:
        b = {k: deepcopy(i[k]) for k in INTERACTION["properties"]}
        for side in ("sender", "receiver"):
            b[side] = {k: deepcopy(i[side][k]) for k in PARTY["properties"]}
        b["data"] = {"sequence": deepcopy(i["data"]["sequence"])}
        result["rr-ssd" if i["layer"] == "RR" else "sr-ssd"]["interactions"].append(b)
    return result


def display_parameters(enriched, inputs):
    """Refresh display attributes from passed API facts, without changing scores.

    Saved SSD messages intentionally contain compact names/locations only.
    Formal semantic analysis still uses the versioned interaction-enrich task.
    """
    out = deepcopy(enriched)
    rows = out.get("interactions", [])
    context = {
        **inputs,
        "rr-ssd": {"interactions": [i for i in rows if i.get("layer") == "RR"]},
        "sr-ssd": {"interactions": [i for i in rows if i.get("layer") == "SR"]},
    }
    for i in rows:
        if (
            not {
                "direction",
                "layer",
                "case_id",
                "api_id",
                "sender",
                "receiver",
                "operation",
                "data",
            }
            <= i.keys()
        ):
            continue
        i["parameter_requirement_sources"] = requirement_sources(i, context)
        i["data"]["sequence"] = parameters_for(i, context)
        i["associated_api"] = resolved_api_id(i, context)
        i["parameter_display_status"] = "linked" if i["associated_api"] else "unresolved"
    out["parameter_display_note"] = (
        "数据属性按当前已通过的接口产物关联展示；历史识别结果和指标未改写。属性变化后的分析需定向重跑交互补全及下游。"
    )
    return out
