"""Adapt per-case authoring files to the SysOperation layout the SSD builder reads.

A case folder may hold one ``authoring-case.json`` (or the older
``main-success.json``) written by the customer agent: 1-based step numbers as
``ref``/``step_ref``, an original-line ``anchor`` on every exception, and a
recovered-test ``extension_mapping``. The builder loads one
``SysOperation.json`` per case; this module renders that file in memory so the
literal values stay untouched and only the references are re-pointed.
"""

import json
from copy import deepcopy
from pathlib import Path

CASE_FILE = "authoring-case.json"
LEGACY_MAIN = "main-success.json"
FILES = (CASE_FILE, LEGACY_MAIN, "SysOperation.json")
SIDECARS = (
    "architecture.json",
    "existing-exceptions.json",
    "test-exceptions.json",
    "extension-mapping.json",
    "source-map.json",
    "source-documents.json",
    "accepted-overrides.json",
)


def is_behavior_evidence(path):
    path = Path(path)
    return (
        path.parent.name == "source-evidence"
        and path.name.endswith("-behavior.json")
        and len(path.name.removesuffix("-behavior.json")) == 12
        and all(c in "0123456789abcdef" for c in path.name[:12])
    )


def core_filename(name):
    return name in (CASE_FILE, LEGACY_MAIN, *SIDECARS)


def case_files(directory):
    """Authoring case files in browse/load order, shallowest first."""
    root = Path(directory)
    found = [
        path
        for name in FILES
        for path in root.rglob(name)
        if path.is_file()
        and path.resolve().is_relative_to(root.resolve())
        and not any(part.startswith(".") for part in path.relative_to(root).parts)
    ]
    return sorted(found, key=lambda p: (len(p.relative_to(root).parts), str(p)))


def is_authoring(value):
    if not isinstance(value, dict):
        return False
    if value.get("version") in {"authoring-case-v1", "main-success-v1", "main-success-v2"}:
        return True
    return (
        isinstance(value.get("steps"), list)
        and "case" in value
        and any(name in value for name in ("existing_exceptions", "test_exceptions"))
    )


def step_key(step):
    key = step.get("id") or step.get("ref")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("编写用例步骤缺少稳定 ID")
    return key


def _step_map(document):
    mapping = {}
    steps = document["steps"]
    direct = {step_key(step) for step in steps}
    if len(direct) != len(steps):
        raise ValueError("编写用例步骤 ID 重复")
    for step in steps:
        key = step_key(step)
        for alias in [step.get("ref"), *(step.get("aliases") or [])]:
            if not isinstance(alias, str) or not alias or alias in direct:
                continue
            if alias in mapping and mapping[alias] != key:
                mapping[alias] = None
            else:
                mapping[alias] = key
    return {**mapping, **{key: key for key in direct}}


def _party(value):
    if isinstance(value, str):
        return {"id": value, "name": value}
    return deepcopy(value)


def _operation(value):
    if isinstance(value, str):
        return {"name": value}
    value = value or {}
    return {
        key: value[key]
        for key in ("name", "crud", "crud_source", "http_method", "http_path", "kinds")
        if key in value
    }


def _record(row, mapping):
    record = deepcopy(row)
    ref = row.get("step_ref") or row.get("step_id")
    if isinstance(ref, int):
        ref = f"op-{ref:02d}"
    if ref is not None and not mapping.get(ref):
        record.update(status="pending", reason="步骤无法唯一定位")
        record.setdefault("failure_step_hint", str(ref))
    record["step_ref"] = mapping.get(ref)
    record["condition"] = row.get("guard") or row.get("condition") or ""
    record["expected"] = row.get("expected") or row.get("expected_result") or ""
    return record


def _channel(rows, mapping):
    rows = rows.get("exceptions") if isinstance(rows, dict) else rows
    return [_record(row, mapping) for row in rows or []]


def _mapping(value, mapping):
    result = []
    seen = set()
    for item in (value or {}).get("items", []):
        if item["extension_id"] in seen:
            raise ValueError("扩展映射的 extension_id 重复：" + item["extension_id"])
        seen.add(item["extension_id"])
        bindings = item.get("bindings") or [{}]
        # The parent keeps its source identity and every binding keeps its own mount.
        result.append(
            {
                **item,
                "bindings": [_record({**item, **binding}, mapping) for binding in bindings],
            }
        )
    return {
        "source": (value or {}).get("source"),
        "source_uc_id": (value or {}).get("source_uc_id"),
        "source_available": (value or {}).get("source_available"),
        "items": result,
    }


def read(path, root):
    """Join the split core files using their own folder and the project architecture."""

    def read_json(file):
        return json.loads(file.read_text(encoding="utf-8-sig"))

    value = read_json(path)
    if not is_authoring(value):
        return value
    value = deepcopy(value)
    case_id = case_identity(value)["id"]
    if path.name == LEGACY_MAIN:
        for key in ("existing-exceptions", "test-exceptions", "extension-mapping"):
            file = path.with_name(key + ".json")
            if not file.is_file():
                continue
            part = read_json(file)
            if part.get("case_id") != case_id:
                raise ValueError(file.name + " 的 case_id 与主成功文件不一致")
            channel = {"existing-exceptions": "E", "test-exceptions": "GT"}.get(key)
            if channel and part.get("channel") != channel:
                raise ValueError(file.name + " 的通道不一致")
            value[key.replace("-", "_")] = part
    architecture = root / "architecture.json"
    if architecture.is_file():
        elements = read_json(architecture)["elements"]
        by_id = {element["id"]: element for element in elements}
        if len(by_id) != len(elements):
            raise ValueError("architecture.json 的参与者 ID 重复")
        value["architecture"] = by_id
    return value


def discover(root, identity):
    """Select one execution input per actual use case; retain local conflicts."""
    by_case = {}
    for file in case_files(root):
        try:
            raw = json.loads(file.read_text(encoding="utf-8-sig"))
            case = case_identity(raw) if is_authoring(raw) else identity(file, root, raw)
            error = None
        except (ValueError, UnicodeError, TypeError, KeyError, AttributeError) as exc:
            case = identity(file, root, {})
            error = str(exc)
        by_case.setdefault(case["id"], []).append((file, case, error))
    for group in by_case.values():
        authored = [entry for entry in group if entry[0].name != "SysOperation.json"]
        candidates = authored or group
        file, case, error = candidates[0]
        if len(candidates) > 1:
            error = "同一用例有多份执行输入，请选择：" + "、".join(
                entry[0].relative_to(root).as_posix() for entry in candidates
            )
        yield file, case, error


def sys_operation(document):
    """Render one authoring case file as the SysOperation record the builder reads."""
    case = deepcopy(document.get("case") or {})
    case_id = case.get("id")
    if not case_id:
        raise ValueError("编写用例缺少 case.id")
    mapping = _step_map(document)
    participants = deepcopy(document.get("architecture") or {})
    existing = document.get("existing_exceptions") or {}
    tests = document.get("test_exceptions") or {}
    for rows in (existing.get("exceptions", []), tests.get("exceptions", [])):
        for row in rows:
            party = row.get("participant")
            if isinstance(party, dict) and party.get("id"):
                participants[party["id"]] = deepcopy(party)
    operation = {
        # The main path is explicit; the builder rejects a path without one.
        "scenario_kind": "main",
        "use_case": case["name"],
        "use_case_id": case_id,
        "system_event": [],
        "interaction": [],
        "action": [],
        "system_response": [],
        "Order": [],
    }
    for step in sorted(document["steps"], key=lambda item: item["order"]):
        key = step_key(step)
        sender = _party(step.get("sender", "?"))
        receiver = _party(step.get("receiver", "?"))
        participants.setdefault(sender["id"], sender)
        participants.setdefault(receiver["id"], receiver)
        for party in (sender, receiver):
            participants[party["id"]] = {**party, **participants[party["id"]]}
        node = {
            "id": key,
            "sender": sender["id"],
            "receiver": receiver["id"],
            "content": step.get("operation", {}).get("name")
            if isinstance(step.get("operation"), dict)
            else step.get("operation") or "",
            "operation": _operation(step.get("operation")),
            "source_refs": deepcopy(step.get("source_refs") or []),
            "_pointer": "/steps/" + str(document["steps"].index(step)),
            "aliases": [alias for alias, sid in mapping.items() if sid == key and alias != key],
            "parent_id": mapping.get(step.get("parent_id")),
            "declared_parent": step.get("parent_id"),
            "direction": step.get("direction"),
            "validates": [mapping.get(ref, ref) for ref in step.get("validates", [])],
        }
        if step.get("description"):
            node["description"] = step["description"]
        if step.get("layer"):
            node["source_layer"] = step["layer"]
        if command := step.get("api_ref") or step.get("call_command_id"):
            node["api_id"] = command
        if step.get("entities"):
            node["data_ref"] = deepcopy(step.get("entity_refs")) or [
                {"entity": entity} for entity in step["entities"]
            ]
        declared = [
            field
            for field in step.get("declared_fields") or step.get("data") or []
            if isinstance(field, dict) and field.get("name")
        ]
        if declared:
            fields = []
            for field in declared:
                name = (
                    f"{field['location']}.{field['name']}"
                    if field.get("location")
                    else field["name"]
                )
                facts = {
                    key: field[key]
                    for key in (
                        "type",
                        "required",
                        "constraints",
                        "source",
                        "normalized_constraints",
                    )
                    if field.get(key) is not None
                }
                fields.append({"field": name, "facts": facts})
            node.setdefault("data_ref", []).append({"declared_fields": fields})
        if step.get("direction") == "return":
            group = "system_response"
        elif step.get("kind") == "action":
            group = "action"
            node["executor"] = sender["id"]
        else:
            group = "interaction"
        operation[group].append(node)
        operation["Order"].append({"kind": group, "ref": key})
    return {
        "operations": {"main": operation},
        "participant": participants,
        "existing-exceptions": _channel(existing, mapping),
        "test-exceptions": _channel(tests, mapping),
        "extension-mapping": _mapping(document.get("extension_mapping"), mapping),
        "case": case,
        "resource": document.get("case_entity"),
        "function_tree": deepcopy(document.get("function_tree") or {}),
        "documents": deepcopy(document.get("documents") or []),
        "analysis_profile": document.get("analysis_profile"),
    }


def case_identity(raw):
    """Stable case identity from the authoring file itself.

    A per-case folder name is presentation. The supplied case id and name are
    the identity every exception and test already references.
    """
    case = raw.get("case") or {}
    if not case.get("id"):
        raise ValueError("编写用例缺少 case.id")
    return {"id": case["id"], "name": case.get("name") or case["id"]}


def supplied_exceptions(raw, sources, file, channel):
    """Keep a JSON citation even when the declared original cannot be verified."""
    key = "existing-exceptions" if channel == "E" else "test-exceptions"
    part = file.with_name(key + ".json")
    split = file.name == LEGACY_MAIN and part.is_file()
    name = sources.add(
        part if split else file, "test" if channel == "GT" and split else "intermediate"
    )
    docs = {d["id"]: d for d in raw.get("documents", [])}
    rows = []
    for index, row in enumerate(raw.get(key, [])):
        anchor = row.get("anchor") or {}
        declared = docs.get(anchor.get("document_id"), {})
        document = declared.get("path") or declared.get("name")
        pointer = (
            f"/exceptions/{index}" if split else f"/{key.replace('-', '_')}/exceptions/{index}"
        )
        origin = None
        if anchor:
            origin = {
                "document": document or anchor.get("document_id"),
                "start_line": anchor.get("start_line"),
                "end_line": anchor.get("end_line"),
                "quote": anchor.get("quote"),
            }
        refs = sources.refs(
            {"source_refs": [*(row.get("source_refs") or []), *([origin] if origin else [])]},
            name,
            pointer,
            kind="test" if channel == "GT" else "context",
        )
        for citation in row.get("structured_source_refs") or []:
            name = citation.get("file") if isinstance(citation, dict) else None
            if not isinstance(name, str):
                continue
            path = sources.root / name
            if (
                path.suffix.lower() != ".json"
                or not path.resolve().is_relative_to(sources.root.resolve())
                or not path.is_file()
            ):
                continue
            snapshot = sources.add(path)
            source_pointer = citation.get("pointer")
            if isinstance(source_pointer, str) and source_pointer in sources.spans.get(
                snapshot, {}
            ):
                refs.append(sources.ref(snapshot, source_pointer))
        rows.append({**row, "channel": channel, "source_refs": refs})
    return rows


def load(path):
    """Read one authoring case file, or ``None`` for another JSON shape."""
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return value if is_authoring(value) else None
