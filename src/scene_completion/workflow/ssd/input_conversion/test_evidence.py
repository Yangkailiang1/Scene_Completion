"""Read recovered tests and extension mappings into GT."""

import json
import re

from scene_completion.domain.ssd.construction import ident, unique
from scene_completion.domain.ssd.interface_fields import INPUT_FIELD_POLICY, legacy_name
from scene_completion.workflow.ssd.input_conversion.evidence_records import (
    _provided,
    recognize_records,
)


def test_channel(bundle, sources, *, supplied=(), mapping=None, mapping_source=None, test_peers=()):
    from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, STRUCTURED_PROFILES
    from scene_completion.domain.ssd.construction import channel, pending
    from scene_completion.inputs.structured.case_names import candidates as case_candidates

    entity_only = bundle.get("analysis_profile") in STRUCTURED_PROFILES
    named = bundle.get("interface_field_policy") == INPUT_FIELD_POLICY

    def same_binding(key, existing, proposed):
        if not existing or existing == proposed:
            return True
        if key != "parameter" or not named or not proposed:
            return False
        if (
            existing.get("command_id")
            and proposed.get("command_id")
            and existing["command_id"] != proposed["command_id"]
        ):
            return False
        return legacy_name(existing.get("name")) == legacy_name(proposed.get("name"))

    supplied_records = [_provided(bundle, row, "GT") for row in supplied]
    mapped = (mapping or {}).get("items", [])
    requested_path = (mapping or {}).get("source") or "recovered_usecases.json"
    path = (sources.root / requested_path).resolve()
    if not path.is_relative_to(sources.root.resolve()):
        raise ValueError("测试来源超出输入目录")
    if not path.exists() and not supplied and not mapped:
        result = channel()
        result["pending"].append(
            pending(
                ident("GT-missing", bundle["case"]["id"]), "未提供测试来源", needs_semantic=False
            )
        )
        bundle["gt_source_available"] = False
        return result
    name, case, prefix = None, {}, ""
    if path.exists():
        name = sources.add(path, "test")
        bundle["test_source_path"] = path.relative_to(sources.root).as_posix()
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, list):
            cases = value
        else:
            key = next((k for k in ("usecases", "use_cases", "cases") if k in value), "usecases")
            cases, prefix = value.get(key, []), "/" + key
        source_id = (mapping or {}).get("source_uc_id") or bundle["case"]["id"]
        conflicting_cases = []
        if bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE:
            source_uc_id = (mapping or {}).get("source_uc_id")
            found = case_candidates(
                cases, bundle["case"]["name"], bundle.get("case_entity"), explicit_id=source_uc_id
            )
            if not found and not source_uc_id:
                found = case_candidates(
                    cases,
                    bundle["case"]["name"],
                    bundle.get("case_entity"),
                    allow_numbered_prefix=True,
                )
                if len(found) == 1:
                    for peer in test_peers:
                        peer_matches = case_candidates(
                            cases,
                            peer["name"],
                            peer["entity"],
                            explicit_id=peer["source_uc_id"],
                            allow_numbered_prefix=True,
                        )
                        if len(peer_matches) == 1 and peer_matches[0][0] == found[0][0]:
                            conflicting_cases.append(peer["id"])
        else:
            found = [(i, row) for i, row in enumerate(cases) if row.get("id") == source_id]
            if not found and not (mapping or {}).get("source_uc_id"):
                found = [
                    (i, row)
                    for i, row in enumerate(cases)
                    if row.get("name") == bundle["case"]["name"]
                ]
        if len(found) == 1 and not conflicting_cases:
            index, case = found[0]
            prefix += f"/{index}"
        elif not supplied and not mapped:
            result = channel()
            reason = (
                "同一测试用例被多个用例认领，请使用显式映射"
                if conflicting_cases
                else "测试用例无法唯一对应"
            )
            result["pending"].append(
                pending(
                    ident("GT-case", bundle["case"]["id"]),
                    reason,
                    [sources.ref(name)],
                    reason=reason,
                    candidates=[row.get("id") for _, row in found],
                    **(
                        {"conflicting_case_ids": sorted(conflicting_cases)}
                        if conflicting_cases
                        else {}
                    ),
                )
            )
            bundle["gt_source_available"] = False
            return result

    records = []
    mapped_ids = {row["extension_id"] for row in mapped}
    supplied_by_extension = {}
    for row in supplied_records:
        extension = row.get("extension_id")
        if extension in mapped_ids:
            supplied_by_extension.setdefault(extension, []).append(row)
        else:
            records.append(row)
    extensions = case.get("extensions", [])
    indexed = {extension.get("id"): (i, extension) for i, extension in enumerate(extensions)}
    locations = {}
    for position, item in enumerate(case.get("evidence_locations", [])):
        locations.setdefault(item.get("id"), []).append((position, item))

    def refs_for(extension, index):
        if name is None or index is None:
            return []
        pointer = f"{prefix}/extensions/{index}"
        refs = [sources.ref(name, pointer, kind="test")]
        for evidence_index, evidence in enumerate(extension.get("evidence") or []):
            if not isinstance(evidence, str):
                continue
            label = re.split(r"[:：]", evidence, maxsplit=1)[0].strip()
            linked = locations.get(label, [])
            metadata = {"evidence_index": evidence_index}
            if linked or re.fullmatch(r"EV[-@][\w@.-]+", label):
                metadata["evidence_id"] = label
            excerpt = sources.ref(name, f"{pointer}/evidence/{evidence_index}", kind="test")
            if len(linked) == 1:
                position, location = linked[0]
                actual = sources.test_evidence(location)
                refs.extend(actual)
                declared = location.get("quote")
                if isinstance(declared, str) and declared.strip():
                    citation = sources.ref(
                        name,
                        f"{prefix}/evidence_locations/{position}/quote",
                        kind="test",
                        origin=None if actual else location,
                    )
                    if citation.get("origin"):
                        excerpt["origin"] = citation["origin"]
                    refs.append({**citation, **metadata, "evidence_quote": declared})
                else:
                    excerpt = sources.ref(
                        name, f"{pointer}/evidence/{evidence_index}", kind="test", origin=location
                    )
            else:
                excerpt["origin"] = {
                    "match": "pending",
                    "reason": "未提供可唯一核验的原始测试证据位置",
                }
            refs.append({**excerpt, **metadata})
        return unique(refs)

    for mount_index, mount in enumerate(mapped):
        eid = mount["extension_id"]
        index, extension = indexed.get(eid, (None, {}))
        for binding in mount["bindings"]:
            row = {**extension, **binding}
            if entity_only and binding.get("kind") == "pending":
                row = {**binding, **extension}
            condition = (
                binding.get("condition")
                or extension.get("condition")
                or mount.get("condition")
                or ""
            )
            expected = (
                binding.get("expected")
                or extension.get("expected_result")
                or mount.get("expected")
                or ""
            )
            fields = (
                "step_ref",
                "target",
                "entity_id",
                "attribute",
                "field_name",
                "parameter",
                "concern_key",
            )
            provided = supplied_by_extension.get(eid, [])
            equivalent = [
                item
                for item in provided
                if all(same_binding(key, item.get(key), binding.get(key)) for key in fields)
                and item["condition"] == condition
                and item["expected"] == expected
            ]
            kind = row.get("kind") or "pending"
            reason = row.get("reason")
            if provided and not equivalent and kind == "exception":
                kind, reason = "pending", "测试异常与扩展挂载不一致"
            if kind == "exception" and not (binding.get("step_ref") and binding.get("concern_key")):
                kind, reason = "pending", reason or "测试扩展缺少确定挂载"
            rid = ident(
                "GT-scenario", bundle["case"]["id"], eid, *[row.get(k) for k in fields], condition
            )
            if len(equivalent) == 1:
                rid = equivalent[0]["id"]
            mapping_refs = []
            if mapping_source:
                mapping_path, mapping_prefix = mapping_source
                mapping_name = sources.add(
                    mapping_path, "test" if mapping_prefix == "" else "intermediate"
                )
                mapping_refs = [
                    sources.ref(mapping_name, f"{mapping_prefix}/items/{mount_index}", kind="test")
                ]
            records.append(
                {
                    **row,
                    "id": rid,
                    "original_id": eid,
                    "extension_id": eid,
                    "condition": condition,
                    "expected": expected,
                    "scenario_type": kind,
                    "reason": reason,
                    "source_refs": unique(
                        refs_for(extension, index)
                        + mapping_refs
                        + [r for item in equivalent for r in item["source_refs"]]
                    ),
                    "raw": extension,
                }
            )
    for index, extension in enumerate(extensions):
        eid = extension.get("id")
        if eid in mapped_ids or any(row.get("extension_id") == eid for row in supplied_records):
            continue
        note = str(extension.get("note", ""))
        kind = extension.get("scenario_type") or (
            "alternative" if re.search(r"成功备选|正常备选", note) else "exception"
        )
        records.append(
            {
                "id": ident("GT-scenario", bundle["case"]["id"], eid or index),
                "original_id": eid,
                "extension_id": eid,
                "condition": extension.get("condition") or "",
                "expected": extension.get("expected_result") or "",
                "source_refs": refs_for(extension, index),
                "scenario_type": kind,
                "raw": extension,
            }
        )
    bundle["gt_source_available"] = bool(
        case or ((mapping or {}).get("source_available") is not False and (supplied or mapped))
    )
    bundle["test_source_case_id"] = case.get("id") or (mapping or {}).get("source_uc_id")
    bundle["test_source_path"] = path.relative_to(sources.root).as_posix() if name else None
    result = recognize_records(bundle, records, "GT")
    pending_by_id = {item["id"]: item for item in result["pending"]}
    excluded = {item["id"] for item in result.get("project_records", [])}
    bundle["test_import_records"] = [
        {
            **{
                k: row.get(k)
                for k in (
                    "id",
                    "original_id",
                    "scenario_type",
                    "step_ref",
                    "reason",
                    "source_refs",
                    "condition",
                    "expected",
                )
            },
            **({"scenario_type": "out_of_scope"} if row["id"] in excluded else {}),
            **(
                {"needs_semantic": True}
                if pending_by_id.get(row["id"], {}).get("needs_semantic")
                else {}
            ),
        }
        for row in records
    ]
    return result
