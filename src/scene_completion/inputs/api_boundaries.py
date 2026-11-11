"""Partition interface ownership independently of RR/SR document provenance."""

import re
from copy import deepcopy

from scene_completion.inputs.http_interfaces import CALL, PARTICIPANT, declarations

HEADING = re.compile(r"^\s*(#{1,6})\s+(.*)")
SERVICE_LABEL = re.compile(r"(?:所属服务|服务名称|service\s*name)\s*[:：|]\s*([^|]+)", re.I)


def service_label(text):
    if text.lstrip().startswith("|") and len(text.strip().strip("|").split("|")) != 2:
        return None
    match = SERVICE_LABEL.search(text)
    return match[1].strip().strip('`"* ') if match else None


def external_services(components):
    return [
        {"name": c["name"], "source_refs": deepcopy(c["source_refs"])}
        for c in components.get("components", [])
        if c["composition_type"].startswith("外部") and "人类" not in c["composition_type"]
    ]


def partition_documents(documents, services, boundary, *, ownership=None):
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
        owner_column = None
        selected = []
        rows = doc["lines"]
        for index, row in enumerate(rows):
            text = row["text"]
            heading = re.match(r"^\s*(#{1,6})\s+(.*)", text)
            if heading:
                level = len(heading[1])
                scopes = [(n, value) for n, value in scopes if n < level]
                title = heading[2].lstrip("`* ")
                explicit = next(
                    (
                        name
                        for name in sorted(names)
                        if re.match(re.escape(name) + r"(?![A-Za-z0-9_.-])", title)
                    ),
                    None,
                )
                if explicit is None:
                    # A section may declare its owner on a metadata row after
                    # the interface heading, before its request/response subsections.
                    for following in rows[index + 1 :]:
                        if HEADING.match(following["text"]) or following[
                            "text"
                        ].lstrip().startswith("```"):
                            break
                        label = service_label(following["text"])
                        if label:
                            explicit = label
                            break
                        if following["text"].strip() and not following["text"].lstrip().startswith(
                            "|"
                        ):
                            break
                inherited = scopes[-1][1] if scopes else None
                owner = (explicit if explicit in names else None) if explicit else inherited
                scopes.append((level, owner))
            label = service_label(text)
            if label:
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
            header = None
            if text.lstrip().startswith("|"):
                cells = [c.strip(" `*") for c in text.strip().strip("|").split("|")]
                header = (
                    next(
                        (
                            n
                            for n, c in enumerate(cells)
                            if c.casefold() in {"所属服务", "服务名称", "service", "service name"}
                        ),
                        None,
                    )
                    if len(cells) >= 3
                    else None
                )
                if header is not None:
                    owner_column = header
                elif owner_column is not None and len(cells) > owner_column:
                    actual = cells[owner_column]
            else:
                owner_column = None
            is_external = actual in names
            if ownership is not None and is_external:
                ownership[(doc["source_id"], row["number"])] = actual
            context = bool(heading or participant or text.strip().startswith("```")) or (
                text.strip() == "sequenceDiagram"
            )
            # Keep context headers only when a relevant body is found below.
            keep = is_external if boundary == "external" else not is_external
            if context and (declarations(text) or re.search(r"API[-–—][A-Za-z0-9]", text)):
                context = keep
            if keep or context or header is not None:
                selected.append((row, keep and (not context or bool(heading))))
        if doc["source_id"].startswith("import-"):
            from scene_completion.inputs.external_interfaces import structured_declarations

            imported = structured_declarations(doc, names)
            numbers = {n for item in imported for n in item["lines"]}
            present = {row["number"] for row, _ in selected}
            if boundary == "external":
                selected.extend((row, True) for row in rows if row["number"] in numbers - present)
                selected.sort(key=lambda entry: entry[0]["number"])
            else:
                selected = [(row, body) for row, body in selected if row["number"] not in numbers]
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
