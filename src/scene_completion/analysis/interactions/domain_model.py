"""V5 business/data identities and evidence-preserving derived views.

This module only joins independently extracted facts. It never turns a CRUD
edge, matching name, or registry definition into an exception by itself.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from html import escape

from scene_completion.infrastructure.storage import fingerprint


def source_chunks(documents, *, max_chars=10000):
    """Split at Markdown headings with a hard bound, retaining original lines."""
    chunks = []
    for document in documents:
        rows = []
        size = 0

        def flush():
            nonlocal rows, size
            if rows:
                chunks.append({**document, "lines": rows})
                rows = []
                size = 0

        for row in document["lines"]:
            line = row["text"]
            if rows and line.lstrip().startswith("#") and size > max_chars // 3:
                flush()
            if rows and size + len(line) > max_chars:
                flush()
            # A single long source line remains intact; splitting it would
            # invalidate the original line reference. The caller can block an
            # over-budget request rather than silently truncate evidence.
            rows.append(row)
            size += len(line) + 1
        flush()
    return chunks


def merge_entities(parts):
    entities = {}
    pending = []
    for part in parts:
        pending.extend(part.get("pending", []))
        for entity in part.get("entities", []):
            key = entity["id"]
            if key not in entities:
                entities[key] = deepcopy(entity)
                continue
            current = entities[key]
            if current["name"] != entity["name"]:
                pending.append(
                    {
                        "reason": "同一业务实体ID对应不同名称",
                        "object": key,
                        "source_refs": entity["source_refs"],
                    }
                )
                continue
            refs = {fingerprint(r): r for r in current["source_refs"] + entity["source_refs"]}
            current["source_refs"] = list(refs.values())

            def attr_key(a):
                return (
                    a["name"],
                    a.get("operation", ""),
                    tuple(sorted(a.get("case_ids", []))),
                    tuple(sorted(a.get("case_names", []))),
                )

            attributes = {attr_key(a): a for a in current["attributes"]}
            for attribute in entity["attributes"]:
                akey = attr_key(attribute)
                if akey not in attributes:
                    attributes[akey] = deepcopy(attribute)
                    continue
                old = attributes[akey]
                for prop in ("data_type", "required"):
                    if old[prop] is None:
                        old[prop] = attribute[prop]
                    elif attribute[prop] is not None and old[prop] != attribute[prop]:
                        pending.append(
                            {
                                "reason": f"{prop}有多个来源值，需确认适用范围",
                                "object": f"{key}.{attribute['name']}",
                                "source_refs": attribute["source_refs"],
                            }
                        )
                old["constraints"] = list(
                    {
                        fingerprint(c): c for c in old["constraints"] + attribute["constraints"]
                    }.values()
                )
                old["source_refs"] = list(
                    {
                        fingerprint(r): r for r in old["source_refs"] + attribute["source_refs"]
                    }.values()
                )
            current["attributes"] = list(attributes.values())
            rules = {r["id"]: r for r in current["business_rules"]}
            for rule in entity["business_rules"]:
                if rule["id"] in rules and fingerprint(rules[rule["id"]]) != fingerprint(rule):
                    pending.append(
                        {
                            "reason": "同一业务规则ID存在冲突",
                            "object": rule["id"],
                            "source_refs": rule["source_refs"],
                        }
                    )
                else:
                    rules[rule["id"]] = rule
            current["business_rules"] = list(rules.values())
    return {"entities": list(entities.values()), "pending": pending}


def merge_rows(parts, list_keys):
    """Join independently validated slices without changing their evidence."""
    result = {key: [] for key in list_keys}
    result["pending"] = []
    for part in parts:
        result["pending"].extend(part.get("pending", []))
        for key in list_keys:
            result[key].extend(deepcopy(part.get(key, [])))
    for key in list_keys:
        rows = {}
        for row in result[key]:
            identity = row.get("id") or fingerprint(
                {k: v for k, v in row.items() if k != "source_refs"}
            )
            if identity in rows and fingerprint(rows[identity]) != fingerprint(row):
                result["pending"].append(
                    {
                        "object": identity,
                        "reason": "不同片段对同一记录给出不同内容，保留首个版本待确认",
                        "source_refs": row.get("source_refs", []),
                    }
                )
            else:
                rows[identity] = row
        result[key] = list(rows.values())
    return result


def dependency_context(documents, dependency, entities, *, max_chars=11000):
    """Retrieve only evidence near the two use cases and business entities."""
    names = {dependency["from_case_id"], dependency["to_case_id"]}
    by_id = {e["id"]: e["name"] for e in entities}
    names.update(by_id.get(dependency[k], "") for k in ("from_entity_id", "to_entity_id"))
    names = {name.casefold() for name in names if len(name) >= 2}
    selected = []
    for doc in documents:
        lines = doc["lines"]
        hit = set()
        for n, row in enumerate(lines):
            if any(name in row["text"].casefold() for name in names):
                hit.update(range(max(0, n - 2), min(len(lines), n + 4)))
        rows = [lines[n] for n in sorted(hit)]
        if rows:
            for chunk in source_chunks([{**doc, "lines": rows}], max_chars=max_chars):
                selected.append(chunk)
    return selected


def existing_branch_context(documents, branches, dependency, entities):
    """Return cited exception lines only; never pass positive prose as E input."""
    relevant = {dependency["from_case_id"], dependency["to_case_id"]}
    relevant.update(
        e["name"]
        for e in entities
        if e["id"] in {dependency["from_entity_id"], dependency["to_entity_id"]}
    )
    relevant = {value.casefold() for value in relevant if value}
    spans = defaultdict(set)
    for branch in branches:
        description = " ".join(
            str(branch.get(key, ""))
            for key in ("case_hint", "description", "operation_hint", "party_hint")
        ).casefold()
        if not any(value in description for value in relevant):
            continue
        for ref in branch["source_refs"]:
            spans[ref["source_id"]].update(range(ref["line_start"], ref["line_end"] + 1))
    selected = []
    for doc in documents:
        rows = [row for row in doc["lines"] if row["number"] in spans[doc["source_id"]]]
        if rows:
            selected.extend(source_chunks([{**doc, "lines": rows}], max_chars=7000))
    return selected


def crud_for_case(case_id, interactions, entities, declared=None):
    """Validate/normalize model-labelled business effects, not HTTP verbs."""
    declared = declared or []
    by_interaction = {i["id"]: i for i in interactions}
    by_entity = {e["id"]: e for e in entities}
    rows = []
    pending = []
    for row in declared:
        if (
            row["interaction_id"] not in by_interaction
            or row["entity_id"] not in by_entity
            or row["case_id"] != case_id
        ):
            pending.append(
                {
                    "reason": "CRUD对应的交互、用例或业务实体无法确认",
                    "object": row.get("entity_id", ""),
                    "source_refs": row["source_refs"],
                }
            )
            continue
        rows.append(row)
    rows = list(
        {
            (r["case_id"], r["interaction_id"], r["entity_id"], r["operation"]): r for r in rows
        }.values()
    )
    return {"rows": rows, "pending": pending}


def exact_field_map(api_parameters, entities, crud_rows, case_aliases=None):
    """Only same-name fields in the actual operation's business entity scope."""
    scopes = defaultdict(set)
    for row in crud_rows:
        scopes[row["api_id"]].add(row["entity_id"]) if row.get("api_id") else None
    entities_by_id = {e["id"]: e for e in entities}
    case_aliases = case_aliases or {}
    mappings = []
    pending = []
    for api in api_parameters.get("apis", []):
        ids = scopes.get(api["id"], set())
        if not ids:
            continue
        for parameter in api["parameters"]:
            matches = []
            for eid in ids:
                entity = entities_by_id.get(eid)
                if entity:
                    matches.extend(
                        (eid, a)
                        for a in entity["attributes"]
                        if a["name"] == parameter["name"]
                        and (
                            not a.get("case_ids")
                            or any(
                                set(a["case_ids"] + a.get("case_names", []))
                                & set(case_aliases.get(r["case_id"], [r["case_id"]]))
                                for r in crud_rows
                                if r["entity_id"] == eid and r.get("api_id") == api["id"]
                            )
                        )
                        and (
                            a["operation"] == "any"
                            or any(
                                r["entity_id"] == eid
                                and r["api_id"] == api["id"]
                                and r["operation"] == a["operation"]
                                for r in crud_rows
                            )
                        )
                    )
            # Multiple operation-scoped descriptions of one attribute are one
            # identity, but different business entities remain ambiguous.
            matches = list({(eid, a["name"]): (eid, a) for eid, a in matches}.values())
            if len(matches) == 1:
                eid, attribute = matches[0]
                mappings.append(
                    {
                        "api_id": api["id"],
                        "direction": "return" if parameter["location"] == "response" else "request",
                        "location": parameter["location"],
                        "field_path": parameter["name"],
                        "entity_id": eid,
                        "attribute": attribute["name"],
                        "basis": "same_name_in_actual_business_entity_scope",
                        "source_refs": list(
                            {
                                fingerprint(r): r
                                for r in parameter["source_refs"] + attribute["source_refs"]
                            }.values()
                        ),
                    }
                )
            elif len(matches) > 1:
                pending.append(
                    {
                        "reason": "同名业务属性有多个候选，不能自动对应",
                        "object": api["id"] + ":" + parameter["name"],
                        "source_refs": parameter["source_refs"],
                    }
                )
    return {"mappings": mappings, "pending": pending}


def dependency_svg(rows, title):
    """Editable-source-independent SVG overview; full facts stay in JSON/MD."""
    width = 1120
    line = 74
    height = max(160, 90 + line * len(rows))
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fbff"/>',
        f'<text x="24" y="42" fill="#153b62" font-family="Arial,sans-serif" font-size="25" font-weight="bold">{escape(title)}</text>',
    ]
    for n, row in enumerate(rows):
        y = 78 + n * line
        left = escape(
            str(
                row.get("from_case_id")
                or row.get("producer_service")
                or row.get("from_entity_id")
                or ""
            )
        )
        right = escape(
            str(
                row.get("to_case_id")
                or row.get("consumer_service")
                or row.get("to_entity_id")
                or ""
            )
        )
        kind = escape(str(row.get("dependency_type") or row.get("relation") or "依赖"))
        out.extend(
            [
                f'<rect x="24" y="{y}" width="340" height="48" rx="9" fill="#e8f1ff" stroke="#6594ce"/>',
                f'<rect x="756" y="{y}" width="340" height="48" rx="9" fill="#e8f1ff" stroke="#6594ce"/>',
                f'<text x="39" y="{y + 30}" fill="#153b62" font-family="Arial,sans-serif" font-size="17">{left}</text>',
                f'<text x="771" y="{y + 30}" fill="#153b62" font-family="Arial,sans-serif" font-size="17">{right}</text>',
                f'<path d="M 364 {y + 24} L 750 {y + 24}" stroke="#497fbd" stroke-width="2" marker-end="url(#arrow)"/>',
                f'<text x="475" y="{y + 16}" fill="#345879" font-family="Arial,sans-serif" font-size="15">{kind}</text>',
            ]
        )
    out.insert(
        2,
        '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9 Z" fill="#497fbd"/></marker></defs>',
    )
    out.append("</svg>")
    return "".join(out)
