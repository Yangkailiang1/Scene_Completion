"""Build SR contracts from the adopted function tree and the actual SSD calls."""

import json
import re

from scene_completion.analysis.interaction_enrichment import response_status_codes
from scene_completion.analysis.validation import validate_result
from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.api_layers import qualify_mapping
from scene_completion.inputs.api_parameters import canonical_contract
from scene_completion.inputs.artifact_adoption import selections
from scene_completion.inputs.colleague_formats import parameter
from scene_completion.inputs.http_interfaces import declarations

_LOCATIONS = {"header", "path", "query", "body", "response"}
_TAGS = {
    "请求头": "header",
    "路径参数": "path",
    "查询参数": "query",
    "请求体": "body",
    "响应参数": "response",
    "成功响应": "response",
    "输出": "response",
}


def _request_matches(api, call):
    declaration = (api["method"], api["address"])
    found = declarations(call["operation"]["name"])
    ident = call.get("api_id")
    declared_ids = {api["api_id"], api["qualified_id"]}
    if ident and ident not in declared_ids:
        return False
    if found and (len(found) != 1 or declaration not in found):
        return False
    return bool(
        ident
        or declaration in found
        or re.search(
            r"(?<![A-Za-z0-9_/-])" + re.escape(api["api_id"]) + r"(?![A-Za-z0-9_/-])",
            call["operation"]["name"],
        )
    )


def _location(field, api, requests, returns):
    name = field["name"]
    prefix, separator, bare = name.partition(".")
    prefix = "header" if prefix == "head" else prefix
    explicit = {_TAGS[tag] for tag in field.get("tags", []) if tag in _TAGS}
    declared = field.get("location")
    if declared in _LOCATIONS:
        explicit.add(declared)
    if prefix in _LOCATIONS and separator and bare:
        explicit.add(prefix)
        name = bare
    direction = field.get("direction")
    if direction in {"response", "output", "return"}:
        explicit.add("response")
    if len(explicit) > 1:
        return name, None
    if explicit:
        location = next(iter(explicit))
        return name, None if direction in {
            "request",
            "input",
        } and location == "response" else location
    observed = {
        p["location"]
        for message in requests + returns
        for p in message["data"]["sequence"]
        if (
            p["name"] == name
            or (p["location"] == "header" and p["name"].casefold() == name.casefold())
        )
        and p["location"] in _LOCATIONS
        and (direction not in {"request", "input"} or message["direction"] == "request")
    }
    if "{" + name + "}" in api["address"]:
        observed.add("path")
    return name, next(iter(observed)) if len(observed) == 1 else None


def _parameter(field, name, location):
    tags = field.get("tags", [])
    dtype = field.get("type")
    dtype = {
        "int": "integer",
        "decimal": "number",
        "object[]": "array",
        "string[]": "array",
        "url": "string",
        "enum": None,
    }.get(dtype, dtype)
    if "必填" in tags and "可选" in tags:
        return None
    required = field.get("required")
    tagged = True if "必填" in tags else False if "可选" in tags else None
    if required is not None and tagged is not None and required != tagged:
        return None
    if required is None:
        required = tagged
    if location == "path" and required is False:
        return None
    rules = []
    default = field.get("default")
    for rule in field["rules"]:
        if match := re.fullmatch(r"默认(?:值)?\s*[:：=]?\s*(.+)", rule.strip()):
            if default is None:
                try:
                    default = json.loads(match[1])
                except ValueError:
                    default = match[1]
            continue
        rules.append(re.sub(r"^枚举\s*(?=\{)", "", rule.strip()))
    result = parameter(
        name, location, field["source_refs"], dtype=dtype, required=required, rules=rules
    )
    result["default"] = default
    return result


def _contract(api, requests, rows, doc, pending):
    ident = api["qualified_id"]
    request_ids = {i["id"] for i in requests}
    returns = [
        i
        for i in rows
        if i["direction"] == "return"
        and i.get("parent_id") in request_ids
        and all(code.startswith("2") for code in response_status_codes(i))
    ]
    returned_fields = {
        p["name"]
        for message in returns
        for p in message["data"]["sequence"]
        if p["location"] == "response"
    }
    fields = []
    for field in api["attributes"]:
        name, location = _location(field, api, requests, returns)
        if (
            location == "response"
            and name not in returned_fields
            and "成功响应" not in field.get("tags", [])
        ):
            location = None
        value = _parameter(field, name, location) if location else None
        if value is None:
            pending.append(f"{ident} · {field['name']} 的字段位置、方向或必填声明待确认")
        else:
            fields.append(value)
    output = [p for p in fields if p["location"] == "response"]
    responses = []
    if output:
        responses.append(
            {
                "kind": "success",
                "status_code": None,
                "parameters": output,
                "source_refs": [ref for p in output for ref in p["source_refs"]],
            }
        )
    else:
        pending.append(ident + " 功能树未提供可定位的成功响应字段")
    pending.append(ident + " 功能树未提供失败响应契约")
    contract = canonical_contract(
        {
            "apis": [
                {
                    "id": ident,
                    "declared_id": api["api_id"],
                    "name": api["name"],
                    "method": api["method"],
                    "address": api["address"],
                    "source_layer": "SR",
                    "bound_interaction_ids": [
                        i["id"]
                        for i in rows
                        if i["id"] in request_ids
                        or (i["direction"] == "return" and i.get("parent_id") in request_ids)
                    ],
                    "parameters": fields,
                    "responses": responses,
                    "source_refs": api["source_refs"],
                }
            ]
        }
    )["apis"][0]
    validate_result("api-parameters", {"apis": [contract]}, {"import-documents": [doc]})
    return contract


def _case_matches(entries, entry):
    group = entry["group"]
    product = entry["row"]["behavior_product"]
    aliases = {*group["rr_ids"], *group["sr_ids"], *product.get("case_ids", [])}
    by_id = [item for item in entries if item[0]["case_id"] in aliases]
    return by_id or [item for item in entries if item[0]["case_name"] == product["case_name"]]


def supplied_interfaces(root, rows, accepted):
    active = {a["file_id"] for a in selections(root, "business-entities", frozen=rows)}
    definitions = [
        (api, product["interface_document"])
        for row in rows
        if row["id"] in active
        for product in [row.get("colleague_product") or {}]
        for api in product.get("interface_declarations", [])
    ]
    return contracts_for_cases(definitions, accepted)


def contracts_for_cases(definitions, accepted):
    candidates, pending = {}, []
    for entry in accepted.values():
        messages = [i for i in entry["fused"]["interactions"] if i["layer"] == "SR"]
        calls = [i for i in messages if i["direction"] == "request" and i["step_kind"] != "action"]
        applicable = _case_matches(definitions, entry)
        matched = {}
        for call in calls:
            hits = [
                (api, doc)
                for api, doc in applicable
                if (api["method"], api["address"])
                in declarations(f"{api['method']} {api['address']}")
                and _request_matches(api, call)
            ]
            if len(hits) != 1:
                if len(hits) > 1 or call.get("api_id"):
                    pending.append(
                        (call.get("api_id") or call["id"]) + " 缺少唯一对应的功能树SR接口"
                    )
                continue
            api, doc = hits[0]
            reference = api["source_refs"][0]
            key = (doc["source_id"], reference["line_start"])
            matched.setdefault(key, []).append(call)
        for api, doc in applicable:
            ident = api["qualified_id"]
            key = (doc["source_id"], api["source_refs"][0]["line_start"])
            requests = matched.get(key, [])
            if not requests:
                pending.append(
                    f"{entry['row']['behavior_product']['case_name']} · {ident} 未在SSD中绑定实际SR请求"
                )
                continue
            owners = {i["receiver"]["name"] for i in requests}
            if len(owners) != 1:
                pending.append(ident + " 对应多个接收方")
                continue
            contract = _contract(api, requests, messages, doc, pending)
            candidates.setdefault(contract["id"], []).append((next(iter(owners)), contract, doc))

    services, index, contracts, documents = {}, [], {}, {}
    for ident, matches in candidates.items():
        owner, contract, doc = matches[0]
        if (
            len(
                {
                    fingerprint(
                        [
                            name,
                            {k: v for k, v in value.items() if k != "bound_interaction_ids"},
                            source["source_id"],
                        ]
                    )
                    for name, value, source in matches
                }
            )
            != 1
        ):
            pending.append(ident + " 在多个用例中有不同的契约或接收方，请查看各用例的接口")
            continue
        contract = {
            **contract,
            "bound_interaction_ids": list(
                dict.fromkeys(i for _, value, _ in matches for i in value["bound_interaction_ids"])
            ),
        }
        api = {
            k: contract[k]
            for k in (
                "id",
                "declared_id",
                "source_layer",
                "name",
                "method",
                "address",
                "source_refs",
            )
        }
        service = services.setdefault(owner, {"name": owner, "interfaces": [], "source_refs": []})
        service["interfaces"].append(api)
        service["source_refs"].extend(api["source_refs"])
        documents[ident] = doc
        contracts[ident] = contract, doc
        index.append(
            {
                **{k: api[k] for k in ("id", "name", "source_layer", "declared_id", "source_refs")},
                "source_ranges": [
                    {"source_id": r["source_id"], "start": r["line_start"], "end": r["line_end"]}
                    for r in api["source_refs"]
                ],
            }
        )
    if not candidates:
        pending.append("当前用例未绑定功能树中的SR接口契约")
    return (
        qualify_mapping({"services": list(services.values())}, "SR"),
        {"apis": index},
        contracts,
        documents,
        list(dict.fromkeys(pending)),
    )
