"""Literal HTTP declarations in prose, tables and Mermaid; preserve source text."""

import re
from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint

METHOD = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+", re.I)
BREAK = re.compile(r"<\s*br\s*/?\s*>|&lt;\s*br\s*/?\s*&gt;|\\n", re.I)
PARTICIPANT = re.compile(r"^\s*(?:participant|actor)\s+([\w.-]+)(?:\s+as\s+(.+?))?\s*$", re.I)
CALL = re.compile(r"^\s*([\w.-]+?)\s*-{1,2}>>?\s*[+-]?([\w.-]+)\s*:\s*(.*)$")


def literal_call_requirements(refs):
    """A literal HTTP declaration may also explicitly require authentication.

    Retain the sentence and its protocol/algorithm spelling. This does not
    infer header names, credentials, failure responses or absent parameters.
    Generic mentions such as '本次携带Token' are not interface requirements.
    """
    out = []
    for ref in refs:
        text = ref["quote"]
        if not declarations(text) or not re.search(
            r"需要|必须|要求|采用|使用|requires?", text, re.I
        ):
            continue
        if re.search(r"签名|signature|signing", text, re.I):
            kind = "signature"
        elif re.search(r"认证|鉴权|authentication", text, re.I):
            kind = "authentication"
        elif re.search(r"授权|authorization", text, re.I):
            kind = "authorization"
        else:
            continue
        out.append({"kind": kind, "requirement": text, "source_refs": [deepcopy(ref)]})
    return out


def mapping_declarations(documents):
    """Literal calls, with Mermaid receiver aliases and exact local evidence.

    RR/SR describe document provenance, not whether the receiver is internal.
    Only an explicit arrow supplies ownership; prose without a receiver stays
    in the inventory for the model, rather than acquiring an invented service.
    """
    found = []
    for document in documents:
        aliases = {}
        mermaid = False
        for row in document["lines"]:
            text = row["text"]
            if text.strip().startswith("```"):
                mermaid = "mermaid" in text.lower() if not mermaid else False
                aliases = {}
            if text.strip() == "sequenceDiagram":
                mermaid = True
                aliases = {}
            participant = PARTICIPANT.match(text) if mermaid else None
            if participant:
                aliases[participant[1]] = (
                    (participant[2] or participant[1]).strip().strip("\"'"),
                    row,
                )
            call = CALL.match(text) if mermaid else None
            receiver = call[2] if call else None
            owner, definition = aliases.get(receiver, (receiver, None))
            for method, path in declarations(call[3] if call else text):
                refs = [source_ref(document, row)]
                if definition is not None and definition != row:
                    refs.append(source_ref(document, definition))
                found.append(
                    {
                        "method": method,
                        "path": path,
                        "receiver": owner,
                        "receiver_alias": receiver,
                        "source_refs": refs,
                    }
                )
    return found


def source_ref(document, row):
    return {
        "source_id": document["source_id"],
        "line_start": row["number"],
        "line_end": row["number"],
        "quote": row["text"],
    }


def call_contract_lines(document, method, path):
    """Include the literal return and peer notes of an evidenced HTTP call.

    Index work only: the model still interprets fields and constraints. A new
    request between these peers ends the span, and other peers never supply
    response fields. Missing responses remain missing.
    """
    rows = document["lines"]
    selected = set()
    for n, row in enumerate(rows):
        call = CALL.match(row["text"])
        if not call or (method, path) not in declarations(call[3]):
            continue
        sender, receiver = call[1], call[2]
        for other in rows[n + 1 :]:
            text = other["text"]
            if text.strip().startswith("```"):
                break
            message = CALL.match(text)
            if (
                message
                and declarations(message[3])
                and {message[1], message[2]} == {sender, receiver}
            ):
                break
            if (
                message
                and (message[1], message[2]) == (receiver, sender)
                and not declarations(message[3])
            ):
                selected.add(other["number"])
            note = re.search(r"^\s*Note\s+(?:over|left of|right of)\s+([^:]+):", text, re.I)
            if note and set(p.strip() for p in note[1].split(",")) <= {sender, receiver}:
                selected.add(other["number"])
    return sorted(selected)


def complete_explicit_calls(value, documents):
    """Recover omitted literal calls without inferring paths or parameters.

    This is the same inventory used in the prompt. It adds a call only when
    the source explicitly names its receiver; unresolved ownership still goes
    through the original validator and bounded semantic repair.
    """
    out = normalize_mapping(value)
    notes = []
    used = {a["id"] for s in out["services"] for a in s["interfaces"]}
    for call in mapping_declarations(documents):
        if not call["receiver"]:
            continue
        names = {call["receiver"], call["receiver_alias"]}
        service = next((s for s in out["services"] if s["name"] in names), None)
        if service is not None and any(
            (a.get("method", "") or "").upper() == call["method"]
            and a.get("address") == call["path"]
            for a in service["interfaces"]
        ):
            continue
        # An existing mapping may use a document's other full service name.
        # Do not relocate it or create a competing ownership claim here.
        if any(
            (a.get("method", "") or "").upper() == call["method"]
            and a.get("address") == call["path"]
            for s in out["services"]
            for a in s["interfaces"]
        ):
            continue
        if service is None:
            service = {
                "name": call["receiver"],
                "interfaces": [],
                "source_refs": deepcopy(call["source_refs"]),
            }
            out["services"].append(service)
        signature = [call["receiver"], call["method"], call["path"]]
        local_id = "local-http-" + fingerprint(signature)[:16]
        if local_id in used:
            raise ValueError("local interface ID conflicts with an existing mapping")
        used.add(local_id)
        service["interfaces"].append(
            {
                "id": local_id,
                "name": call["method"] + " " + call["path"],
                "method": call["method"],
                "address": call["path"],
                "source_refs": deepcopy(call["source_refs"]),
                **(
                    {"interface_constraints": requirements}
                    if (requirements := literal_call_requirements(call["source_refs"]))
                    else {}
                ),
            }
        )
        notes.append(
            {
                "interface_id": local_id,
                "action": "restore explicit Mermaid method/path and literal receiver",
                "source_refs": deepcopy(call["source_refs"]),
            }
        )
    return out, notes


def clean_path(value):
    text = BREAK.split(str(value), maxsplit=1)[0].strip().strip("`\"'")
    if text.startswith("http://") or text.startswith("https://"):
        from urllib.parse import urlsplit

        text = urlsplit(text).path
    # Stop at presentation boundaries, never synthesize missing braces.
    path = re.split(r'[\s`"\'，。；,;|()（）<>]', text, maxsplit=1)[0].split("?", 1)[0]
    if not path.startswith("/") or not path or path.count("{") != path.count("}"):
        return None
    return path


def declarations(text):
    out = []
    for match in METHOD.finditer(text):
        if re.search(r"不是|不要|禁止", text[max(0, match.start() - 12) : match.start()]):
            continue
        path = clean_path(text[match.end() :])
        if path:
            out.append((match[1].upper(), path))
    return out


def normalize_mapping(value):
    out = deepcopy(value)
    for service in out.get("services", []):
        for api in service.get("interfaces", []):
            address = api.get("address")
            if not address:
                continue
            pure = clean_path(address)
            refs = api.get("source_refs", [])
            # Only presentation cleanup supported by this interface's own quote.
            if (
                pure
                and pure != address
                and any(
                    (
                        not api.get("method")
                        or (api["method"].upper(), pure) in declarations(r["quote"])
                    )
                    and pure in r["quote"]
                    for r in refs
                )
            ):
                api["address"] = pure
    return out
