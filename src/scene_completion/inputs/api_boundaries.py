"""Partition interface ownership independently of RR/SR document provenance."""

import re
from copy import deepcopy

from scene_completion.inputs.http_interfaces import CALL, PARTICIPANT, declarations


def external_services(components):
    return [
        {"name": c["name"], "source_refs": deepcopy(c["source_refs"])}
        for c in components.get("components", [])
        if c["composition_type"].startswith("外部") and "人类" not in c["composition_type"]
    ]


def partition_documents(documents, services, boundary):
    """Remove only explicitly identified external ownership from system inputs.

    Aliases are local to each Mermaid diagram. Whole external API sections
    retain parameter, security and response definitions; a call-only fragment
    never becomes a fabricated full interface contract. Unresolved ownership
    remains in system inputs for modelling/clarification.
    """
    names = {s["name"] for s in services}
    result = []
    for doc in documents:
        aliases = {}
        scopes = []
        owner = None
        selected = []
        for row in doc["lines"]:
            text = row["text"]
            heading = re.match(r"^\s*(#{1,6})\s+(.*)", text)
            if heading:
                level = len(heading[1])
                scopes = [(n, value) for n, value in scopes if n < level]
                title = heading[2].lstrip("`* ")
                explicit = next((name for name in names if title.startswith(name)), None)
                inherited = scopes[-1][1] if scopes else None
                owner = explicit or inherited
                scopes.append((level, owner))
            service_label = re.search(
                r"(?:所属服务|服务名称|service\s*name)\s*[:：|]\s*([^|]+)", text, re.I
            )
            if service_label:
                label = service_label[1].strip().strip('`"* ')
                owner = label if label in names else None
                if scopes:
                    scopes[-1] = (scopes[-1][0], owner)
            if text.strip().startswith("```") or text.strip() == "sequenceDiagram":
                aliases = {}
            participant = PARTICIPANT.match(text)
            if participant:
                aliases[participant[1]] = (participant[2] or participant[1]).strip().strip("\"'")
            call = CALL.match(text)
            actual = aliases.get(call[2], call[2]) if call else owner
            if call and not declarations(call[3]) and aliases.get(call[1], call[1]) in names:
                actual = aliases.get(call[1], call[1])
            note = re.search(r"^\s*Note\s+(?:over|left of|right of)\s+([^:]+):", text, re.I)
            if note:
                parties = [p.strip() for p in note[1].split(",")]
                actual = next(
                    (aliases.get(p, p) for p in parties if aliases.get(p, p) in names), owner
                )
            is_external = actual in names
            context = bool(heading or participant or text.strip().startswith("```")) or (
                text.strip() == "sequenceDiagram"
            )
            # Keep context headers only when a relevant body is found below.
            keep = is_external if boundary == "external" else not is_external
            if context and (declarations(text) or re.search(r"API[-–—][A-Za-z0-9]", text)):
                context = keep
            if keep or context:
                selected.append((row, keep and not context))
        if boundary == "external" and not any(body for _, body in selected):
            continue
        lines = [deepcopy(row) for row, _ in selected]
        if lines:
            result.append({**doc, "lines": lines})
    return result


def scope_inputs(documents, components, layer, boundary):
    services = external_services(components)
    return {
        layer: partition_documents(documents, services, boundary),
        "interface-scope": {"boundary": boundary, "external_services": services},
    }


def has_declarations(documents, *, include_abstract=False):
    return any(
        declarations(row["text"])
        or re.search(r"API[-–—][A-Za-z0-9]", row["text"])
        or (
            include_abstract
            and CALL.match(row["text"])
            and "--" not in row["text"].split(":", 1)[0]
        )
        for d in documents
        for row in d["lines"]
    )


def filter_mapping(value, scope):
    names = {s["name"] for s in scope.get("external_services", [])}
    external = scope["boundary"] == "external"
    return {
        "services": [deepcopy(s) for s in value["services"] if (s["name"] in names) == external]
    }
