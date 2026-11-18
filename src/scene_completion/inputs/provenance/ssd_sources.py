"""Literal source and contract adapters for the SSD-centred workflow.

JSON files are data, never instructions. All references address immutable source
content; generated rules carry separate provenance from original requirements.
"""

import json
import re
from copy import deepcopy
from pathlib import Path

from scene_completion.domain.ssd.construction import ident, unique
from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.structured.colleague_formats import constraints, request_parameters


def _pointer(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def json_spans(text):
    """Map JSON Pointers to character offsets without changing source layout."""
    decoder, spans = json.JSONDecoder(), {}

    def space(pos):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        return pos

    def visit(pos, pointer):
        start = pos = space(pos)
        if text[pos] == "{":
            pos = space(pos + 1)
            while text[pos] != "}":
                key, pos = decoder.raw_decode(text, pos)
                pos = space(pos)
                if text[pos] != ":":
                    raise ValueError("Invalid JSON property")
                pos = space(visit(pos + 1, pointer + "/" + _pointer(key)))
                if text[pos] == ",":
                    pos = space(pos + 1)
                else:
                    break
            end = pos + 1
        elif text[pos] == "[":
            pos, index = space(pos + 1), 0
            while text[pos] != "]":
                pos = space(visit(pos, pointer + "/" + str(index)))
                index += 1
                if text[pos] == ",":
                    pos = space(pos + 1)
                else:
                    break
            end = pos + 1
        else:
            _, end = decoder.raw_decode(text, pos)
        spans[pointer] = (start, end)
        return end

    visit(0, "")
    return spans


class Sources:
    def __init__(self, root, origins=None):
        self.root = Path(root)
        self.documents = {}
        self.spans = {}
        self.aliases = {}
        # Original specification documents. Structured inputs cite their own
        # JSON pointers; their ``source`` fields point at these real lines.
        self.origins = list(origins or [])
        for doc in self.origins:
            path = self.root / (doc.get("path") or doc["name"])
            if path.is_file():
                self.add(path, doc["role"])
        for path in sorted(self.root.glob("*.md")):
            role = (
                "RR"
                if "系统需求" in path.name
                else "SR"
                if "功能设计" in path.name
                else "intermediate"
            )
            self.add(path, role)
            if role == "RR":
                self.aliases.setdefault("spec", path.name)
            elif role == "SR":
                self.aliases.setdefault("sr", path.name)

    def add(self, path, role="intermediate"):
        path = Path(path)
        name = str(path.relative_to(self.root))
        if name not in self.documents:
            text = path.read_text(encoding="utf-8-sig")
            self.documents[name] = {
                "id": ident("document", name),
                "name": name,
                "role": role,
                "content": text,
                "hash": fingerprint(text),
            }
            if path.suffix.lower() == ".json":
                self.spans[name] = json_spans(text)
        return name

    def ref(self, name, pointer="", *, kind="context", origin=None):
        doc = self.documents[name]
        content = doc["content"]
        begin, end = self.spans.get(name, {}).get(pointer, (0, len(content)))
        start_line = content.count("\n", 0, begin) + 1
        end_line = content.count("\n", 0, end) + 1
        lines = content.splitlines()
        row = {
            "document_id": doc["id"],
            "start_line": start_line,
            "end_line": end_line,
            "quote": "\n".join(lines[start_line - 1 : end_line]),
            "kind": kind,
            **({"json_pointer": pointer} if name in self.spans else {}),
        }
        traced = self.trace(origin) if origin else None
        if traced:
            row["origin"] = traced
        return row

    def trace(self, origin):
        """Resolve one supplied ``source`` field to a real line of its original."""
        from scene_completion.inputs.provenance import source_origins

        document, quote, declared = source_origins.source_origin(origin)
        return source_origins.origin(
            source_origins.resolve_name(document, self.origins) if document else None,
            quote,
            declared,
        ) or source_origins.untraced("未找到唯一原始文档")

    def traced_ref(self, name, pointer, origin):
        """Pointer reference that opens the original line when it can be found."""
        found = self.trace(origin) if origin else None
        kind = "origin" if (found or {}).get("match") in {"exact", "located"} else "context"
        return self.ref(name, pointer, kind=kind, origin=origin)

    def original(self, refs):
        result = []
        for ref in refs or []:
            traced = self.trace(ref)
            if not traced or traced.get("match") not in {"exact", "located"}:
                continue
            doc = next(
                (d for d in self.origins if (d.get("path") or d["name"]) == traced["document"]),
                None,
            )
            if doc:
                result.append(
                    {
                        "document_id": doc["id"],
                        "start_line": traced["start_line"],
                        "end_line": traced["end_line"],
                        "quote": traced["quote"],
                        "kind": "test" if doc["role"] == "test" else "origin",
                        "origin": traced,
                    }
                )
        return unique(result)

    def test_evidence(self, evidence):
        from scene_completion.inputs.provenance import source_origins
        from scene_completion.inputs.provenance.test_sources import xlsx_documents

        name = source_origins.stem(evidence.get("source_file") or "")
        quote, location = evidence.get("quote"), evidence.get("location")
        if not name or not quote:
            return []
        files = list(self.root.rglob(name))
        if len(files) != 1 or not files[0].is_file():
            return []
        path = files[0]
        if path.suffix.lower() in {".md", ".markdown"}:
            key = self.add(path, "test")
            traced = self.trace({"doc": key, "quote": quote, "line": location})
            if not traced or traced.get("role") != "test" or traced.get("match") == "pending":
                return []
            return [
                {
                    **self.ref(key, kind="test"),
                    "start_line": traced["start_line"],
                    "end_line": traced["end_line"],
                    "quote": traced["quote"],
                    "origin": traced,
                }
            ]
        if path.suffix.lower() != ".xlsx":
            return []
        try:
            sheets = xlsx_documents(
                path.read_bytes(), path.name, path.relative_to(self.root).as_posix()
            )
        except ValueError:
            return []
        found = source_origins.from_cell(location, quote, sheets)
        if not found or source_origins._normalized(quote) not in source_origins._normalized(
            found["quote"]
        ):
            return []
        sheet = next(d for d in sheets if d["name"].split("#")[-1] == found["sheet"])
        key = path.relative_to(self.root).as_posix() + "#" + found["sheet"]
        lines = {row["number"]: row["text"] for row in sheet["lines"]}
        content = "\n".join(lines.get(i, "") for i in range(1, max(lines) + 1))
        doc = self.documents.setdefault(
            key,
            {
                "id": ident("document", key),
                "name": key,
                "role": "test",
                "content": content,
                "hash": fingerprint(content),
            },
        )
        return [
            {
                "document_id": doc["id"],
                "start_line": found["start_line"],
                "end_line": found["end_line"],
                "quote": found["quote"],
                "kind": "test",
                "json_pointer": location,
            }
        ]

    def refs(self, node, name, pointer=""):
        declared = node.get("source_refs") or []
        originals = self.original(declared)
        return unique(
            originals
            + [self.ref(name, pointer, origin=declared[0] if declared and not originals else None)]
        )

    def entity_origins(self, entity, attribute=None):
        result = []
        pattern = re.compile(
            r"^\s*-?\s*"
            + re.escape(entity)
            + (r"\." + re.escape(attribute) + r"(?:[（(：:\s])" if attribute else r"\.")
        )
        for doc in self.documents.values():
            if doc["role"] not in {"RR", "SR"}:
                continue
            for n, line in enumerate(doc["content"].splitlines(), 1):
                if pattern.search(line):
                    result.append(
                        {
                            "document_id": doc["id"],
                            "start_line": n,
                            "end_line": n,
                            "quote": line,
                            "kind": "origin",
                        }
                    )
        return result

    def field_origins(self, api, field, response=False):
        """Locate literal field declarations within the same API's original section."""
        result = []
        aid = api.get("API序号") or api.get("apiId") or api.get("id")
        location, name = field["location"], field["name"]
        for doc in self.documents.values():
            if doc["role"] not in {"RR", "SR"}:
                continue
            lines = doc["content"].splitlines()
            active = False
            for n, line in enumerate(lines, 1):
                if line.startswith("## ") or re.search(r"(?:接口：|接口:)API-", line):
                    active = False
                if aid and aid in line and ("接口" in line or line.startswith("#")):
                    active = True
                if active and re.match(
                    r"^\s*-?\s*" + re.escape(location + "." + name) + r"[（(\s]", line
                ):
                    result.append(
                        {
                            "document_id": doc["id"],
                            "start_line": n,
                            "end_line": n,
                            "quote": line,
                            "kind": "origin",
                        }
                    )
        if response:
            result += self.original(
                [
                    r
                    for r in api.get("成功响应来源", [])
                    if location + "." + name + "（" in r.get("quote", "")
                ]
            )
        return unique(result)


class _Facts:
    def __init__(self, sources, name):
        self.sources, self.name = sources, name

    def add(self, value, pointer):
        return [self.sources.ref(self.name, pointer)]


def api_contracts(sources, tree, tree_path=None):
    """Read both RR and SR declared fields; do not infer a response from requests."""
    contracts = {}
    path = sources.root / "api_extraction.json"
    if path.exists():
        name = sources.add(path)
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        for n, api in enumerate(raw.get("apis", [])):
            aid = api.get("API序号")
            if not aid:
                continue
            fields = []
            for prop, response in [("API请求参数", False), ("API成功响应参数", True)]:
                parsed, _ = request_parameters(
                    api.get(prop, ""),
                    _Facts(sources, name),
                    f"/apis/{n}/{prop}",
                    response=response,
                )
                for field in parsed:
                    refs = unique(
                        sources.field_origins(api, field, response) + field["source_refs"]
                    )
                    field["source_refs"] = refs
                    for constraint in field["constraints"]:
                        constraint["source_refs"] = refs
                    fields.append(field)
            contracts[aid] = {
                "id": aid,
                "method": api.get("方法"),
                "path": api.get("资源路径"),
                **(
                    {"source_layer": api["source_layer"]}
                    if api.get("source_layer") in {"RR", "SR"}
                    else {"source_layer": "SR"}
                    if api.get("SR编号") and not api.get("RR编号")
                    else {}
                ),
                "fields": fields,
                "source_refs": sources.original([api.get("来源", {})])
                + [sources.ref(name, f"/apis/{n}")],
            }
    # The tree supplements structured field constraints. Name-only declarations
    # never overwrite a complete API field or pretend to specify a data type.
    if tree is None:
        return contracts
    name = sources.add(tree_path or sources.root / "功能树.json")
    for fn, function in enumerate(tree.get("functions", [])):
        for layer in ("rrLayer", "srLayer"):
            for cn, command in enumerate(function.get(layer, {}).get("commands", [])):
                aid = command.get("apiId")
                if not aid:
                    continue
                pointer = f"/functions/{fn}/{layer}/commands/{cn}"
                contract = contracts.setdefault(
                    aid,
                    {
                        "id": aid,
                        "method": command.get("method"),
                        "path": command.get("path"),
                        "fields": [],
                        "source_refs": [],
                    },
                )
                sourced = sources.traced_ref(name, pointer, command.get("source"))
                if (
                    command.get("path")
                    and contract.get("path")
                    and command["path"] != contract["path"]
                ):
                    contract["path_conflicts"] = sorted(
                        {contract["path"], command["path"], *contract.get("path_conflicts", [])}
                    )
                    candidates = contract.setdefault("qualified_candidates", [])
                    original_layer = contract.get("source_layer")
                    if original_layer:
                        original_id = original_layer + "::" + aid
                        if original_id not in contracts:
                            contracts[original_id] = {
                                **deepcopy(contract),
                                "id": original_id,
                                "declared_id": aid,
                                "path_conflicts": [],
                                "qualified_candidates": [],
                            }
                        if original_id not in candidates:
                            candidates.append(original_id)
                    original = command.get("source") or {}
                    hint = (original.get("doc") or "").lower() if isinstance(original, dict) else ""
                    declared_layer = {"rrspec": "RR", "srspec": "SR"}.get(hint)
                    if declared_layer and declared_layer != original_layer:
                        qualified = declared_layer + "::" + aid
                        contracts[qualified] = {
                            "id": qualified,
                            "declared_id": aid,
                            "path": command["path"],
                            "method": command.get("method"),
                            "source_layer": declared_layer,
                            "fields": [],
                            "source_refs": [sourced],
                        }
                        if qualified not in candidates:
                            candidates.append(qualified)
                if sourced.get("kind") == "origin":
                    contract["source_refs"] = [
                        row for row in contract["source_refs"] if row.get("kind") != "origin"
                    ]
                contract["source_refs"] = unique(contract["source_refs"] + [sourced])
                for an, attr in enumerate(command.get("attributes", [])):
                    if not isinstance(attr, dict):
                        continue
                    refs = [
                        sources.traced_ref(name, pointer + f"/attributes/{an}", attr.get("source"))
                    ]
                    qualified = re.fullmatch(
                        r"(header|query|path|body|response)\.(.+)", attr["name"]
                    )
                    field_name = qualified[2] if qualified else attr["name"]
                    location = attr.get("location") or (qualified[1] if qualified else None)
                    if location is None and "成功响应" in attr.get("tags", []):
                        location = "response"
                    original = attr.get("source")
                    section = original.get("section", "") if isinstance(original, dict) else ""
                    if location is None:
                        location = next(
                            (
                                kind
                                for word, kind in (
                                    ("路径参数", "path"),
                                    ("查询参数", "query"),
                                    ("请求头", "header"),
                                    ("成功响应", "response"),
                                    ("请求体", "body"),
                                )
                                if word in section
                            ),
                            None,
                        )
                    field = {
                        "name": field_name,
                        "location": location,
                        "data_type": attr.get("type"),
                        "required": True
                        if "必填" in attr.get("tags", [])
                        else False
                        if "可选" in attr.get("tags", [])
                        else None,
                        "constraints": constraints(
                            [
                                re.sub(r"^枚举\s*", "", r.get("rule", ""))
                                for r in attr.get("constraints", [])
                            ],
                            field_name,
                            refs,
                        ),
                        "source_refs": refs,
                    }
                    candidates = [
                        p
                        for p in contract["fields"]
                        if p["name"] == field_name
                        and (
                            p.get("location") == location
                            if location
                            else p.get("location") != "response"
                        )
                    ]
                    previous = candidates[0] if len(candidates) == 1 else None
                    if previous:
                        previous["source_refs"] = unique(previous["source_refs"] + refs)
                        previous["constraints"] = unique(
                            previous["constraints"] + field["constraints"]
                        )
                    else:
                        contract["fields"].append(field)
    return contracts


def entities_for(sources, tree, case_id, case_name, tree_path=None, *, entity_only=False):
    """Entities and constraints of exactly one use case.

    The function tree is already split by use case, so each case carries only
    the entities it declares. Nothing is unioned across cases: a field another
    case happens to constrain is not this case's requirement.

    ``rrLayer`` names participating entities but declares no attributes, so the
    attribute definitions come from ``srLayer`` alone.
    """
    if tree is None:
        return []
    name = sources.add(tree_path or sources.root / "功能树.json")
    functions = tree.get("functions", [])
    exact = [f for f in functions if (f.get("functionId") or f.get("ucId")) == case_id]
    if entity_only and len(exact or [f for f in functions if f.get("name") == case_name]) != 1:
        return []
    for fn, function in enumerate(functions):
        if entity_only and exact and function is not exact[0]:
            continue
        identity = function.get("functionId") or function.get("ucId")
        if identity != case_id and function.get("name") != case_name:
            continue
        declared = {}
        for layer in ("srLayer",) if entity_only else ("rrLayer", "srLayer"):
            for entity_index, entity in enumerate(function.get(layer, {}).get("entities", [])):
                eid = entity.get("entity") or entity.get("name")
                if not eid:
                    continue
                pointer = f"/functions/{fn}/{layer}/entities/{entity_index}"
                refs = [
                    sources.traced_ref(
                        name,
                        f"/functions/{fn}/{layer}/entities/{entity_index}",
                        entity.get("source"),
                    )
                ]
                declared.setdefault(eid, []).append(
                    {
                        "entity": entity,
                        "attributes": entity.get("attributes") or [],
                        "refs": refs,
                        "pointer": pointer,
                    }
                )
        result = {}
        for eid, rows in declared.items():
            refs = unique([r for row in rows for r in row["refs"]])
            entry = result.setdefault(
                eid, {"id": eid, "name": eid, "attributes": [], "source_refs": refs}
            )
            for row in rows:
                for an, attr in enumerate(row["attributes"]):
                    attr_refs = unique(
                        sources.entity_origins(eid, attr["name"])
                        + [
                            sources.traced_ref(
                                name,
                                row["pointer"] + f"/attributes/{an}",
                                attr.get("source") or row["entity"].get("source"),
                            )
                        ]
                    )
                    from scene_completion.analysis.concerns.constraint_atoms import (
                        normalize_rules,
                    )

                    normalized = normalize_rules(
                        attr.get("constraints", []),
                        attr["name"],
                        attr_refs,
                        tags=attr.get("tags") or [],
                        data_type=attr.get("type"),
                        entity_only=entity_only,
                    )
                    entry["attributes"].append(
                        {
                            **deepcopy(attr),
                            "source_refs": attr_refs,
                            "constraints": constraints(
                                [
                                    re.sub(r"^枚举\s*", "", r.get("rule", ""))
                                    for r in attr.get("constraints", [])
                                ],
                                attr["name"],
                                attr_refs,
                            ),
                            "atoms": normalized["items"],
                            "payload_fields": normalized["payload"],
                            "unresolved": normalized["unresolved"],
                        }
                    )
        return list(result.values())
    return []
