"""Export the structured SSD handoff and an auditable field-to-source map."""

import re
import shutil
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from scene_completion.domain.current_scope import COMMAND_PROFILES, STRUCTURED_PROFILES
from scene_completion.domain.ssd.interface_fields import INPUT_FIELD_POLICY
from scene_completion.infrastructure.storage import fingerprint, io_path, logical_path, write_json
from scene_completion.inputs.structured.authoring_cases import is_behavior_evidence
from scene_completion.workflow.ssd.input_conversion.case_builder import _input_root, build_cases
from scene_completion.workflow.ssd.shared import failure_context


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
    result = []
    documents = _documents(bundle)
    for source in _sources(bundle, row):
        if source.get("declared_source"):
            result.append(source["declared_source"])
            continue
        if (
            not source["file"]
            or source["kind"] not in {"origin", "test"}
            or source.get("json_pointer")
        ):
            continue
        origin = source.get("origin")
        origin = origin if isinstance(origin, dict) else {}
        snapshot = documents[source["document_id"]]
        sheet = origin.get("sheet") or snapshot.get("sheet")
        document = snapshot.get("source_path") or (
            source["file"].removesuffix("#" + sheet) if sheet else source["file"]
        )
        if origin.get("cell_range"):
            result.append(
                {
                    "document": document,
                    "sheet": origin["sheet"],
                    "location": origin["declared_line"],
                    "quote": origin["cell_quote"],
                }
            )
        else:
            result.append(
                {k: source[k] for k in ("start_line", "end_line", "quote")}
                | {"document": document}
                | ({"sheet": sheet} if sheet else {})
            )
    return result


def _exception(bundle, row, channel, evidence_files):
    steps = {step["id"]: step for step in bundle["steps"]}
    step = steps.get(row.get("step_id"), {})
    field = next((f for f in step.get("data", []) if f["id"] == row.get("field_id")), {})
    target = row.get("target")
    if row.get("entity_id") and row.get("attribute"):
        target = "entity"
    named = bundle.get("interface_field_policy") == INPUT_FIELD_POLICY
    if field:
        target = "receiver" if named or field.get("location") != "response" else "sender"
    parameter = None
    if field and named:
        parameter = {"command_id": field["command_id"], "name": field["name"]}
    elif field:
        parameter = {
            "name": field["name"],
            "location": field["location"],
            "direction": field.get("direction")
            or (step["direction"] if field["location"] != "storage" else "storage"),
        }
    sources = _sources(bundle, row)
    pending_source = row.get("original") or {}
    if not parameter and named and (declared := pending_source.get("parameter")):
        parameter = {k: declared[k] for k in ("command_id", "name") if declared.get(k)}
    location = failure_context.location(bundle, pending_source) if pending_source else {}
    branch = failure_context.branch_context(pending_source)
    structured_refs = [
        {
            "file": evidence_files[ref["document_id"]],
            "pointer": ref["json_pointer"],
            "original": ref["file"],
        }
        for ref in sources
        if ref["document_id"] in evidence_files and ref.get("json_pointer")
    ]

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
        origin = original.get("origin")
        origin = origin if isinstance(origin, dict) else {}
        anchor = {
            "document_id": document["id"],
            "layer": document["role"],
            **{k: original[k] for k in ("start_line", "end_line", "quote")},
            **(
                {"location": origin["declared_line"], "cell_quote": origin["cell_quote"]}
                if origin.get("cell_range")
                else {}
            ),
        }
    return {
        "id": row["id"],
        "step_id": row.get("step_id"),
        "target": target,
        "condition": row["condition"],
        "expected": row.get("expected") or pending_source.get("expected", ""),
        **{k: v for k, v in location.items() if v},
        **({"evidence_context": branch} if branch else {}),
        **({"structured_source_refs": structured_refs} if structured_refs else {}),
        **(
            {"scenario_kind": pending_source["scenario_type"]}
            if pending_source.get("scenario_type")
            else {}
        ),
        **(
            {"extension_id": pending_source["extension_id"]}
            if pending_source.get("extension_id")
            else {}
        ),
        "status": row["status"],
        **({"needs_semantic": True} if row.get("needs_semantic") else {}),
        "anchor": anchor,
        "source_refs": _originals(bundle, row),
        "origin": {"source": "test_case" if channel == "GT" else "extension_path"},
        **{
            k: row[k]
            for k in (
                "key",
                "entity_id",
                "attribute",
                "reason",
                "extension_id",
                "failure_step_id",
                "failure_step_hint",
                "failure_step_reason",
                "failure_step_pending",
            )
            if row.get(k)
        },
        **({"concern_key": row["key"]} if row.get("key") else {}),
        **({"parameter": parameter} if parameter else {}),
    }


def _main(bundle):
    entity_only = bundle.get("analysis_profile") in STRUCTURED_PROFILES
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
                **(
                    {"call_command_id": step["call_command_id"]}
                    if step.get("call_command_id")
                    else {}
                ),
                **({"validates": step.get("validates", [])} if entity_only else {}),
                "operation": {
                    "name": operation["name"],
                    "crud": operation["kinds"],
                    **({"crud_source": operation["kinds_source"]} if entity_only else {}),
                    **(
                        {"command_id": operation["command_id"]}
                        if operation.get("command_id")
                        else {}
                    ),
                    **{k: operation[k] for k in ("http_method", "http_path") if operation.get(k)},
                },
                "source_refs": _originals(bundle, step),
                **({"description": step["description"]} if step.get("description") else {}),
                **(
                    {"entity_refs": step.get("entity_refs", [])}
                    if entity_only
                    else {
                        "declared_fields": [
                            {
                                **{k: field[k] for k in ("name", "location", "type", "required")},
                                "normalized_constraints": field["constraints"],
                            }
                            for field in step["data"]
                            if not field.get("contract_derived")
                        ]
                    }
                ),
            }
        )
    return {
        "version": "main-success-v2",
        **(
            {"interface_field_policy": INPUT_FIELD_POLICY}
            if bundle.get("interface_field_policy") == INPUT_FIELD_POLICY
            else {}
        ),
        **({"analysis_profile": bundle["analysis_profile"]} if entity_only else {}),
        "case": bundle["case"],
        **({"case_entity": bundle["case_entity"]} if bundle.get("case_entity") else {}),
        **(
            {
                "command_bindings": bundle["command_bindings"],
                "data_obligations": [
                    {
                        "step_id": step["id"],
                        "field_id": field["id"],
                        "command_id": field["command_id"],
                        **({"location": field["location"]} if "location" in field else {}),
                        "name": field["name"],
                    }
                    for step in bundle["steps"]
                    for field in step["data"]
                ],
            }
            if bundle.get("analysis_profile") in COMMAND_PROFILES
            else {}
        ),
        "function_tree": {
            "path": bundle.get("function_tree_path") or "功能树.json",
            "uc_id": bundle.get("function_tree_case_id", bundle["case"]["id"]),
        },
        "documents": [
            {
                "id": doc["id"],
                "path": doc.get("source_path") or doc["name"],
                "name": Path(doc["name"]).name,
                "role": doc["role"],
                **({"sheet": doc["sheet"]} if doc.get("sheet") else {}),
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
                element = {
                    **{k: party[k] for k in ("id", "name", "technology")},
                    "kind": kind,
                    **{k: party[k] for k in ("classification_source", "source_refs") if k in party},
                }
                current = elements.get(party["id"])
                if current and any(
                    current[k] != element[k] for k in ("name", "technology", "kind")
                ):
                    raise ValueError("参与者 ID 尚未唯一：" + party["id"])
                if current and current.get("source_refs"):
                    from scene_completion.domain.ssd.construction import unique

                    element["source_refs"] = unique(
                        [*current["source_refs"], *element.get("source_refs", [])]
                    )
                    element["classification_source"] = current["classification_source"]
                elements[party["id"]] = element
    return {"version": "architecture-elements-v1", "elements": list(elements.values())}


def export_core(directory, output, case_ids=None):
    root, output = _input_root(directory), io_path(output).resolve()
    if output.exists():
        raise ValueError("核心文件请导出到新的目录")
    return write_core(root, output, build_cases(root, case_ids, generate=False))


def write_core(root, output, bundles):
    """Materialize the normalized cases without generating or running model nodes."""
    root, output = io_path(root), io_path(output)
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
    } | (
        {"api_extraction.json"}
        if any(b.get("analysis_profile") not in STRUCTURED_PROFILES for b in bundles)
        else set()
    )
    for name in support:
        if (root / name).is_file():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
    for bundle in bundles:
        case_id = bundle["case"]["id"]
        entity_only = bundle.get("analysis_profile") in STRUCTURED_PROFILES
        folder_name = fingerprint(case_id)[:16]
        if entity_only:
            readable = re.sub(r'[<>:"/\\|?*\s]+', "-", case_id + "-" + bundle["case"]["name"])
            folder_name = readable.strip(".-")[:64] + "-" + folder_name[:8]
        folder = output / "cases" / folder_name
        for doc in bundle["documents"]:
            if doc["role"] not in {"RR", "SR", "test"}:
                continue
            name = doc.get("source_path") or doc["name"]
            source = root / name
            if source.is_file():
                target = output / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        evidence_files = {}
        documents = _documents(bundle)
        for row in bundle["channels"]["E"]["pending"] + bundle["channels"]["E"]["scenarios"]:
            if not entity_only:
                break
            for ref in row.get("source_refs", []):
                did = ref["document_id"]
                doc = documents.get(did)
                if not doc or not ref.get("json_pointer") or did in evidence_files:
                    continue
                if Path(
                    doc["name"]
                ).name.casefold() != "sysoperation.json" and not is_behavior_evidence(doc["name"]):
                    continue
                target = folder / "source-evidence" / (fingerprint(did)[:12] + "-behavior.json")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(doc["content"], encoding="utf-8")
                evidence_files[did] = target.relative_to(output).as_posix()
        write_json(folder / "main-success.json", _main(bundle))
        test_bindings = defaultdict(list)
        for channel, filename in (("E", "existing-exceptions"), ("GT", "test-exceptions")):
            rows = bundle["channels"][channel]
            exceptions = [
                _exception(bundle, row, channel, evidence_files)
                for row in rows["scenarios"] + rows["pending"]
                if not entity_only
                or channel != "GT"
                or row.get("extension_id")
                or (row.get("original") or {}).get("extension_id")
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
                **({k: record[k] for k in ("condition", "expected")} if entity_only else {}),
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
                **(
                    {
                        "interface_fields": {
                            field["id"]: {
                                "field": _sources(bundle, field),
                                "constraints": [
                                    {
                                        "operation": atom.get("operation"),
                                        "source_refs": _sources(bundle, atom),
                                    }
                                    for atom in field["atoms"] + field["unresolved"]
                                ],
                            }
                            for step in bundle["steps"]
                            for field in step["data"]
                        }
                    }
                    if bundle.get("interface_field_policy") == INPUT_FIELD_POLICY
                    else {}
                ),
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
    declarations = {
        doc["path"]: doc for bundle in bundles for doc in bundle.get("source_documents", [])
    }
    for name in declarations:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    manifest = root / "source-documents.json"
    if manifest.is_file():
        shutil.copyfile(manifest, output / manifest.name)
    return {
        "output": str(logical_path(output)),
        "case_ids": [bundle["case"]["id"] for bundle in bundles],
    }
