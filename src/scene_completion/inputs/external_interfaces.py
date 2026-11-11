"""External interface declarations shared by extraction, validation and indexing."""

import json
import re

from scene_completion.inputs.http_interfaces import (
    CALL,
    call_contract_lines,
    clean_path,
    declarations,
    source_ref,
)

REVISION = "external-declarations-v1"
DOCUMENT_ID = re.compile(r"\bAPI[-–—][\w-]+", re.I)
NAMED = re.compile(r"(?:接口名称|API名称|interface\s*name)\s*[:：]\s*(.+)", re.I)
METHOD_LABEL = re.compile(
    r"(?:请求方法|HTTP方法|method)\s*[:：]\s*`?(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b", re.I
)
PATH_LABEL = re.compile(r"(?:请求路径|接口路径|path)\s*[:：]\s*`?(/\S+)", re.I)


def structured_declarations(document, owners):
    """Read adopted JSONL API facts with the explicit service owner and cited lines."""
    if not document["source_id"].startswith("import-"):
        return []
    rows = {row["number"]: row for row in document["lines"]}
    result = []

    def references(value):
        if isinstance(value, dict):
            for ref in value.get("source_refs", []):
                if isinstance(ref, dict) and ref.get("source_id") == document["source_id"]:
                    number = ref.get("line_start")
                    if number in rows:
                        yield number
            for key, child in value.items():
                if key != "source_refs":
                    yield from references(child)
        elif isinstance(value, list):
            for child in value:
                yield from references(child)

    for row in rows.values():
        try:
            service = json.loads(row["text"])
        except ValueError:
            continue
        if not isinstance(service, dict) or not isinstance(service.get("name"), str):
            continue
        if service["name"] not in owners or not isinstance(service.get("interfaces"), list):
            continue
        for api in service["interfaces"]:
            if not isinstance(api, dict) or not isinstance(api.get("name"), str):
                continue
            anchors = set(references({"source_refs": api.get("source_refs", [])}))
            if not anchors:
                continue
            result.append(
                {
                    "receiver": service["name"],
                    "name": api["name"],
                    "id": api.get("declared_id") or api.get("id"),
                    "method": api.get("method"),
                    "path": api.get("address"),
                    "source_refs": [source_ref(document, rows[n]) for n in sorted(anchors)],
                    "lines": sorted({row["number"], *references(api)}),
                }
            )
    return result


def literal_http(text):
    pairs = declarations(text)
    if pairs or not text.lstrip().startswith("|"):
        return pairs
    cells = [cell.strip(" `*") for cell in text.strip().strip("|").split("|")]
    return [
        (method.upper(), path)
        for method, field in zip(cells, cells[1:])
        if re.fullmatch(r"GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS", method, re.I)
        and (path := clean_path(field))
    ]


def inventory(inputs):
    from scene_completion.inputs.api_boundaries import HEADING, partition_documents

    scope = inputs["interface-scope"]
    services = scope["external_services"]
    owners = {s["name"] for s in services}
    docs = inputs.get("RR", []) + inputs.get("SR", [])
    attributed = {}
    partition_documents(docs, services, "external", ownership=attributed)
    result = []
    for doc in docs:
        if doc.get("channel", "normal") != "normal":
            continue
        if doc["source_id"].startswith("import-"):
            result.extend(structured_declarations(doc, owners))
            continue
        rows = doc["lines"]
        for index, row in enumerate(rows):
            owner = attributed.get((doc["source_id"], row["number"]))
            if owner is None:
                continue
            text = row["text"]
            call = CALL.match(text)
            if call and "--" in text.split(":", 1)[0]:
                continue
            literal = literal_http(call[3] if call else text)
            heading = HEADING.match(text)
            title = heading[2] if heading else text
            explicit_name = NAMED.search(title) if not call else None
            identifier = DOCUMENT_ID.search(title) if not call else None
            bold_label = text.lstrip().startswith("**")
            starts_with_identifier = identifier and title.lstrip(" `*").startswith(identifier[0])
            named_contract = explicit_name or starts_with_identifier and (heading or bold_label)
            stop = index + 1
            if heading or named_contract:
                for other in rows[stop:]:
                    nested = HEADING.match(other["text"])
                    if (nested and (not heading or len(nested[1]) <= len(heading[1]))) or (
                        DOCUMENT_ID.search(other["text"])
                        and (nested or other["text"].lstrip().startswith("**"))
                    ):
                        break
                    stop += 1
            block = rows[index:stop]
            refs = [source_ref(doc, row)]
            if not literal and named_contract:
                nested_http = [
                    (r, literal_http(r["text"]))
                    for r in block[1:]
                    if not CALL.match(r["text"])
                    and attributed.get((doc["source_id"], r["number"])) == owner
                ]
                nested_signatures = {pair for _, pairs in nested_http for pair in pairs}
                if len(nested_signatures) == 1:
                    literal = list(nested_signatures)
                    refs.extend(source_ref(doc, r) for r, pairs in nested_http if pairs)
            if not literal and named_contract:
                # Accept explicit labelled request method/path within the same contract.
                methods = [
                    (r, m[1].upper()) for r in block if (m := METHOD_LABEL.search(r["text"]))
                ]
                paths = [
                    (r, clean_path(p[1])) for r in block if (p := PATH_LABEL.search(r["text"]))
                ]
                pairs = (
                    list(dict.fromkeys(v for _, v in methods)),
                    list(dict.fromkeys(v for _, v in paths if v)),
                )
                if len(pairs[0]) <= 1 and len(pairs[1]) <= 1:
                    literal = [(next(iter(pairs[0]), None), next(iter(pairs[1]), None))]
                    refs.extend(source_ref(doc, r) for r, _ in methods + paths if r != row)
            if not literal:
                continue
            if explicit_name:
                name = explicit_name[1].strip(" `*")
            elif identifier:
                name = title[identifier.end() :].strip(" `*：:-") or identifier[0]
            else:
                name = None
            for method, path in literal:
                numbers = {r["number"] for r in block}
                if call and method and path:
                    numbers.update(call_contract_lines(doc, method, path, anchor=row["number"]))
                result.append(
                    {
                        "receiver": owner,
                        "name": name,
                        "id": identifier[0] if identifier else None,
                        "method": method,
                        "path": path,
                        "source_refs": refs,
                        "lines": sorted(numbers),
                    }
                )
    return result


def declaration_key(item):
    method, path = item["method"], item["path"]
    abstract_id = None if method and path else item["id"] or item["name"]
    return item["receiver"], method, path, abstract_id


def verified_anchors(mapping, inputs, *, require_complete=True):
    """Require a cited, owned declaration for every external mapped identity."""
    from scene_completion.inputs.api_identity import identity_parts

    declarations = inventory(inputs)
    mapped = {}
    covered = set()
    for service in mapping["services"]:
        for api in service["interfaces"]:
            signature = (api.get("method"), api.get("address"))
            identity = identity_parts(api["id"])[2]
            matched = [
                item
                for item in declarations
                if item["receiver"] == service["name"]
                and (item["method"], item["path"]) == signature
                and (
                    all(signature)
                    or (
                        bool(item["id"])
                        and item["id"] in {identity, api.get("declared_id")}
                        or bool(item["name"])
                        and item["name"] == api["name"]
                    )
                )
            ]
            if not any(
                ref["source_id"] == anchor["source_id"]
                and ref["line_start"] <= anchor["line_start"] <= ref["line_end"]
                for item in matched
                for anchor in item["source_refs"]
                for ref in api["source_refs"]
            ):
                raise ValueError(
                    f"External API has no cited declaration for owner, method/path or named contract: "
                    f"{service['name']} / {api['id']} / {signature}"
                )
            mapped[api["id"]] = matched
            covered.update(declaration_key(item) for item in matched)
    if require_complete and (missing := {declaration_key(item) for item in declarations} - covered):
        raise ValueError(
            f"External API mapping omitted explicit declarations: {sorted(missing, key=repr)[:8]}"
        )
    return mapped


def index(mapping, inputs, *, require_complete=True):
    """Use exact declaration positions and the contract rows attached to them."""
    mapped = verified_anchors(mapping, inputs, require_complete=require_complete)
    apis = []
    for service in mapping["services"]:
        for api in service["interfaces"]:
            numbers = {}
            for item in mapped[api["id"]]:
                source = item["source_refs"][0]["source_id"]
                numbers.setdefault(source, set()).update(item["lines"])
            spans = []
            for source, lines in sorted(numbers.items()):
                for number in sorted(lines):
                    if (
                        spans
                        and spans[-1]["source_id"] == source
                        and spans[-1]["end"] + 1 == number
                    ):
                        spans[-1]["end"] = number
                    else:
                        spans.append({"source_id": source, "start": number, "end": number})
            apis.append(
                {
                    "id": api["id"],
                    "name": api["name"],
                    "source_ranges": spans,
                    "source_refs": api["source_refs"],
                }
            )
    return {"apis": apis}


def mapping_view(inputs):
    """Retain the declaration and ownership evidence in the compact model input."""
    from scene_completion.inputs.indexed_context import task_document_view
    from scene_completion.inputs.source_documents import documents_in

    result = dict(inputs)
    required = {}
    for item in inventory(inputs):
        for ref in item["source_refs"]:
            required.setdefault(ref["source_id"], set()).update(
                item["lines"] if ref["source_id"].startswith("import-") else [ref["line_start"]]
            )
    for layer in ("RR", "SR"):
        if layer in inputs:
            retained = [
                {
                    **doc,
                    "lines": [
                        r for r in doc["lines"] if r["number"] in required.get(doc["source_id"], ())
                    ],
                }
                for doc in inputs[layer]
            ]
            result[layer] = documents_in(task_document_view(inputs[layer], "api-map") + retained)
    return result
