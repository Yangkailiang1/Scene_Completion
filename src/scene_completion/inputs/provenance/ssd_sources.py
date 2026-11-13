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
    def __init__(self, root):
        self.root = Path(root)
        self.documents = {}
        self.spans = {}
        self.aliases = {}
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

    def ref(self, name, pointer="", *, kind="context"):
        doc = self.documents[name]
        content = doc["content"]
        begin, end = self.spans.get(name, {}).get(pointer, (0, len(content)))
        start_line = content.count("\n", 0, begin) + 1
        end_line = content.count("\n", 0, end) + 1
        lines = content.splitlines()
        return {
            "document_id": doc["id"],
            "start_line": start_line,
            "end_line": end_line,
            "quote": "\n".join(lines[start_line - 1 : end_line]),
            "kind": kind,
            **({"json_pointer": pointer} if name in self.spans else {}),
        }

    def original(self, refs):
        result = []
        for ref in refs or []:
            name = ref.get("document") or ref.get("file") or ref.get("name")
            name = self.aliases.get(name, name)
            if name not in self.documents:
                continue
            doc = self.documents[name]
            start = ref.get("start_line") or ref.get("line_start") or ref.get("line")
            end = ref.get("end_line") or ref.get("line_end") or start
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            lines = doc["content"].splitlines()
            if not 1 <= start <= end <= len(lines):
                continue
            result.append(
                {
                    "document_id": doc["id"],
                    "start_line": start,
                    "end_line": end,
                    "quote": "\n".join(lines[start - 1 : end]),
                    "kind": "test" if doc["role"] == "test" else "origin",
                }
            )
        return unique(result)

    def refs(self, node, name, pointer=""):
        return unique(self.original(node.get("source_refs", [])) + [self.ref(name, pointer)])

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


def api_contracts(sources, tree):
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
                "fields": fields,
                "source_refs": sources.original([api.get("来源", {})])
                + [sources.ref(name, f"/apis/{n}")],
            }
    # The tree supplements structured field constraints. Name-only declarations
    # never overwrite a complete API field or pretend to specify a data type.
    if tree is None:
        return contracts
    name = sources.add(sources.root / "功能树.json")
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
                contract["source_refs"] = unique(
                    contract["source_refs"] + [sources.ref(name, pointer)]
                )
                for an, attr in enumerate(command.get("attributes", [])):
                    if not isinstance(attr, dict):
                        continue
                    refs = [sources.ref(name, pointer + f"/attributes/{an}")]
                    qualified = re.fullmatch(
                        r"(header|query|path|body|response)\.(.+)", attr["name"]
                    )
                    field_name = qualified[2] if qualified else attr["name"]
                    location = attr.get("location") or (qualified[1] if qualified else None)
                    if location is None and "成功响应" in attr.get("tags", []):
                        location = "response"
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


def entities_for(sources, tree, case_id, case_name):
    result = {}
    if tree is None:
        return []
    name = sources.add(sources.root / "功能树.json")
    for fn, function in enumerate(tree.get("functions", [])):
        if function.get("ucId") != case_id and function.get("name") != case_name:
            continue
        for layer in ("rrLayer", "srLayer"):
            for en, entity in enumerate(function.get(layer, {}).get("entities", [])):
                eid = entity.get("entity") or entity.get("name")
                if not eid:
                    continue
                pointer = f"/functions/{fn}/{layer}/entities/{en}"
                refs = unique(sources.entity_origins(eid) + [sources.ref(name, pointer)])
                row = result.setdefault(
                    eid, {"id": eid, "name": eid, "attributes": [], "source_refs": []}
                )
                row["source_refs"] = unique(row["source_refs"] + refs)
                for an, attr in enumerate(entity.get("attributes", [])):
                    refs = unique(
                        sources.entity_origins(eid, attr["name"])
                        + [sources.ref(name, pointer + f"/attributes/{an}")]
                    )
                    row["attributes"].append(
                        {
                            **deepcopy(attr),
                            "source_refs": refs,
                            "constraints": constraints(
                                [
                                    re.sub(r"^枚举\s*", "", r.get("rule", ""))
                                    for r in attr.get("constraints", [])
                                ],
                                attr["name"],
                                refs,
                            ),
                        }
                    )
    return list(result.values())
