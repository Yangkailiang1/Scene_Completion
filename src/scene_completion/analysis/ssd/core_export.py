"""Export the structured SSD handoff and an auditable field-to-source map."""

import shutil
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from scene_completion.analysis.ssd.pipeline import _input_root, build_cases
from scene_completion.infrastructure.storage import fingerprint, write_json


def _documents(bundle):
    return {document["id"]: document for document in bundle["documents"]}


def _sources(bundle, row):
    documents = _documents(bundle)
    return [
        {
            **ref,
            "file": documents.get(ref["document_id"], {}).get("name"),
        }
        for ref in row.get("source_refs", [])
    ]


def _originals(bundle, row):
    return [
        {
            "document": source["file"],
            "start_line": source["start_line"],
            "end_line": source["end_line"],
            "quote": source["quote"],
        }
        for source in _sources(bundle, row)
        if source["file"]
        and source["kind"] in {"origin", "test"}
        and not source.get("json_pointer")
    ]


def _exception(bundle, row, channel):
    steps = {step["id"]: step for step in bundle["steps"]}
    step = steps.get(row.get("step_id"), {})
    field = next((f for f in step.get("data", []) if f["id"] == row.get("field_id")), {})
    target = row.get("target")
    if row.get("entity_id") and row.get("attribute"):
        target = "entity"
    if field:
        target = "sender" if field["location"] == "response" else "receiver"
    sources = _sources(bundle, row)
    original = next(
        (
            s
            for s in sources
            if s["file"] and s["kind"] in {"origin", "test"} and not s.get("json_pointer")
        ),
        None,
    )
    anchor = None
    if original:
        document = _documents(bundle)[original["document_id"]]
        anchor = {
            "document_id": document["id"],
            "layer": document["role"],
            **{k: original[k] for k in ("start_line", "end_line", "quote")},
        }
    return {
        "id": row["id"],
        "step_id": row.get("step_id"),
        "target": target,
        "condition": row["condition"],
        "expected": row.get("expected", ""),
        "status": row["status"],
        **({"needs_semantic": True} if row.get("needs_semantic") else {}),
        "anchor": anchor,
        "source_refs": _originals(bundle, row),
        "origin": {"source": "test_case" if channel == "GT" else "extension_path"},
        **{
            k: row[k]
            for k in ("key", "entity_id", "attribute", "reason", "extension_id", "failure_step_id")
            if row.get(k)
        },
        **({"concern_key": row["key"]} if row.get("key") else {}),
        **(
            {
                "parameter": {
                    "name": field["name"],
                    "location": field["location"],
                    "direction": step["direction"] if field["location"] != "storage" else "storage",
                }
            }
            if field
            else {}
        ),
    }


def _main(bundle):
    steps = []
    for step in bundle["steps"]:
        operation = step["operation"]
        steps.append(
            {
                **{
                    k: step[k]
                    for k in ("id", "order", "direction", "kind", "aliases", "layer", "parent_id")
                },
                "sender": step["sender"]["id"],
                "receiver": step["receiver"]["id"],
                "entities": step["entity_ids"],
                "api_ref": step["api_id"],
                "operation": {
                    "name": operation["name"],
                    "crud": operation["kinds"],
                    **{k: operation[k] for k in ("http_method", "http_path") if operation.get(k)},
                },
                "source_refs": _originals(bundle, step),
                **({"description": step["description"]} if step.get("description") else {}),
                "declared_fields": [
                    {
                        **{k: field[k] for k in ("name", "location", "type", "required")},
                        "normalized_constraints": field["constraints"],
                    }
                    for field in step["data"]
                    if not field.get("contract_derived")
                ],
            }
        )
    return {
        "version": "main-success-v2",
        "case": bundle["case"],
        "function_tree": {
            "path": bundle.get("function_tree_path") or "功能树.json",
            "uc_id": bundle.get("function_tree_case_id", bundle["case"]["id"]),
        },
        "documents": [
            {
                "id": doc["id"],
                "path": doc["name"],
                "name": Path(doc["name"]).name,
                "role": doc["role"],
            }
            for doc in bundle["documents"]
            if doc["role"] in {"RR", "SR", "test"}
        ],
        "steps": steps,
    }


def _architecture(bundles):
    elements = {}
    for bundle in bundles:
        for step in bundle["steps"]:
            for party in (step["sender"], step["receiver"]):
                kind = (
                    "external_actor"
                    if party["type"] == "human"
                    else "external_service"
                    if party["external"]
                    else "internal_service"
                )
                element = {**{k: party[k] for k in ("id", "name", "technology")}, "kind": kind}
                if party["id"] in elements and elements[party["id"]] != element:
                    raise ValueError("参与者 ID 尚未唯一：" + party["id"])
                elements[party["id"]] = element
    return {"version": "architecture-elements-v1", "elements": list(elements.values())}


def export_core(directory, output, case_ids=None):
    root, output = _input_root(directory), Path(output).resolve()
    if output.exists():
        raise ValueError("核心文件请导出到新的目录")
    return write_core(root, output, build_cases(root, case_ids, generate=False))


def write_core(root, output, bundles):
    """Materialize the normalized cases without generating or running model nodes."""
    root, output = Path(root), Path(output)
    variants = defaultdict(set)
    for bundle in bundles:
        for step in bundle["steps"]:
            for role in ("sender", "receiver"):
                party = step[role]
                variants[party["id"]].add(
                    (party["name"], party["type"], party["technology"], party["external"])
                )
    if any(len(choices) > 1 for choices in variants.values()):
        bundles = deepcopy(bundles)
        for bundle in bundles:
            for step in bundle["steps"]:
                for role in ("sender", "receiver"):
                    party = step[role]
                    if len(variants[party["id"]]) > 1:
                        party["id"] = bundle["case"]["id"] + "::" + party["id"]
    architecture = _architecture(bundles)
    support = {
        name
        for bundle in bundles
        for name in (bundle.get("function_tree_path"), bundle.get("test_source_path"))
        if name
    } | {"api_extraction.json"}
    for name in support:
        if (root / name).is_file():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
    for bundle in bundles:
        case_id = bundle["case"]["id"]
        folder = output / "cases" / fingerprint(case_id)[:16]
        for doc in bundle["documents"]:
            if doc["role"] not in {"RR", "SR", "test"}:
                continue
            name = doc["name"].split("#", 1)[0]
            source = root / name
            if source.is_file():
                target = output / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        write_json(folder / "main-success.json", _main(bundle))
        test_bindings = defaultdict(list)
        for channel, filename in (("E", "existing-exceptions"), ("GT", "test-exceptions")):
            rows = bundle["channels"][channel]
            exceptions = [
                _exception(bundle, row, channel) for row in rows["scenarios"] + rows["pending"]
            ]
            for item in exceptions:
                if not item.get("extension_id") and channel == "GT":
                    original = next(
                        (
                            r.get("original_id")
                            for r in bundle.get("test_import_records", [])
                            if r["id"] == item["id"]
                        ),
                        None,
                    )
                    if original:
                        item["extension_id"] = original
                if channel == "GT" and item.get("extension_id") and item["status"] == "active":
                    test_bindings[item["extension_id"]].append(item)
            write_json(
                folder / (filename + ".json"),
                {
                    "version": "exception-list-v2",
                    "case_id": case_id,
                    "channel": channel,
                    "exceptions": exceptions,
                },
            )
        items = {}
        for record in bundle.get("test_import_records", []):
            eid = record.get("original_id")
            if not eid:
                continue
            kind = record["scenario_type"]
            bindings = test_bindings[eid]
            items[eid] = {
                "extension_id": eid,
                "kind": "exception"
                if bindings
                else "normal"
                if kind in {"normal", "alternative", "optional"}
                else "out_of_scope"
                if kind == "out_of_scope"
                else "pending",
                "reason": record.get("reason"),
                **({"needs_semantic": True} if record.get("needs_semantic") else {}),
                "bindings": bindings,
            }
        write_json(
            folder / "extension-mapping.json",
            {
                "version": "extension-mapping-v2",
                "case_id": case_id,
                "source": bundle.get("test_source_path") or "recovered_usecases.json",
                "source_uc_id": bundle.get("test_source_case_id"),
                "source_available": bundle.get("gt_source_available"),
                "items": list(items.values()),
            },
        )
        write_json(
            folder / "source-map.json",
            {
                "case_id": case_id,
                "steps": {step["id"]: _sources(bundle, step) for step in bundle["steps"]},
                **{
                    channel: {
                        row["id"]: _sources(bundle, row)
                        for kind in ("concerns", "scenarios", "pending")
                        for row in bundle["channels"][channel][kind]
                    }
                    for channel in ("E", "GT")
                },
            },
        )
    write_json(output / "architecture.json", architecture)
    return {"output": str(output), "case_ids": [bundle["case"]["id"] for bundle in bundles]}
