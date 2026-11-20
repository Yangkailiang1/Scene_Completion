"""Read source requirement branches and map original exceptions into E."""

import json
import re
from copy import deepcopy

from scene_completion.domain.ssd.construction import ident, unique
from scene_completion.workflow.ssd.input_conversion.evidence_records import (
    _classification,
    _locate,
    _provided,
    recognize_records,
)


def existing_channel(bundle, case_dir, sources, supplied=(), raw=None):
    from scene_completion.inputs.structured.ordered_behaviors import scenario_kind

    records = [_provided(bundle, row, "E") for row in supplied]
    candidates = []
    from scene_completion.domain.current_scope import STRUCTURED_PROFILES

    entity_only = bundle.get("analysis_profile") in STRUCTURED_PROFILES
    for layer in () if entity_only else ("IR", "SR"):
        for path in sorted((case_dir / "behaviour" / layer).glob("*.json")):
            branch = json.loads(path.read_text(encoding="utf-8-sig"))
            candidates.append((layer, path, "", branch))
    for key, branch in (raw or {}).get("operations", {}).items():
        pointer = "/operations/" + key.replace("~", "~0").replace("/", "~1")
        layer = "IR" if str(branch.get("source_layer") or "").upper() in {"IR", "RR"} else "SR"
        candidates.append((layer, case_dir / "SysOperation.json", pointer, branch))

    for layer, path, pointer, branch in candidates:
        kind = scenario_kind(branch)
        if (
            kind == "main"
            or not branch.get("guard")
            or (not entity_only and kind in {"normal", "alternative", "optional"})
        ):
            continue
        responses = [
            n.get("message")
            for n in branch.get("system_response", []) + branch.get("interaction", [])
            if n.get("message")
            and (n in branch.get("system_response", []) or n.get("direction") == "return")
        ]
        outcome = responses or [n["content"] for n in branch.get("action", []) if n.get("content")]
        expected = "；".join(dict.fromkeys(outcome))
        if (
            not entity_only
            and isinstance(branch.get("resume_at_main"), dict)
            and not any(
                re.search(r"HTTP\s*[45]\d{2}|返回\s*[A-Z]+_[A-Z_]+|拒绝|失败", value)
                for value in outcome
            )
        ):
            continue
        original_id = branch.get("ID") or path.stem
        records.append(
            {
                "id": ident("E-scenario", bundle["case"]["id"], layer, original_id),
                "original_id": original_id,
                "condition": branch["guard"],
                "expected": expected,
                "source_refs": sources.refs(branch, sources.add(path), pointer),
                "layer": "RR" if layer == "IR" else "SR",
                "scenario_type": kind or "exception",
                "failure_step_id": branch.get("failure_step_id")
                or (None if entity_only else (branch.get("extend_at_main") or {}).get("after")),
                "failure_step_hint": branch.get("failure_step_hint"),
                "raw": branch,
            }
        )

    def normalize(value):
        return re.sub(r"\s+", "", value or "")

    if entity_only:
        return recognize_records(bundle, records, "E")

    merged = {}
    for record in records:
        raw = record["raw"]
        code = re.search(r"_SC_EX_(.+)$", record["original_id"] or "")
        anchor = record.get("step_ref") or (raw.get("extend_at_main") or {}).get("after")
        expected = record.get("expected") or ""
        responses = [
            line for line in expected.split("；") if re.match(r"返回\s*HTTP\s*[45]\d{2}", line)
        ]
        terminal = "；".join(responses) if code and responses else expected
        error = re.search(
            r"\b(?:ORDER_|PRODUCT_|NAME_|DATABASE_|INVALID_|AUTH_|STATE_)[A-Z_]+", terminal
        )
        certain = code or (error and anchor)
        key = (
            code[1] if code else (error[0] if certain else ""),
            normalize(record["condition"]),
            (error[0] if error and anchor and not code else normalize(terminal)),
            "" if code else str(anchor or ""),
            record.get("target"),
            record.get("entity_id"),
            record.get("attribute"),
        )
        previous = merged.get(key)
        if previous is None:
            merged[key] = record
            continue

        # Prefer a separately authored SR branch over a fused copy that has lost
        # its local branch markers or explicit step citations.
        def score(item):
            return (
                item.get("layer") == "SR",
                any(
                    not (ref.get("json_pointer") or "").startswith("/operations/")
                    for ref in item["source_refs"]
                ),
                bool(
                    _locate(
                        bundle, item, _classification(item["condition"], item.get("expected", ""))
                    )
                ),
            )

        primary = deepcopy(record if score(record) > score(previous) else previous)
        primary["source_refs"] = unique(previous["source_refs"] + record["source_refs"])
        merged[key] = primary

    def occurrence(record):
        after = (record["raw"].get("extend_at_main") or {}).get("after")
        return (
            after,
            normalize(record["condition"]),
            record.get("target"),
            record.get("entity_id"),
            record.get("attribute"),
        )

    concrete = {}
    for record in merged.values():
        anchor = occurrence(record)
        if anchor[0] and record.get("expected"):
            concrete.setdefault(anchor, []).append(record)
    retained = []
    for record in merged.values():
        # Attach a partial branch only when its explicit occurrence and condition
        # uniquely identify an outcome supplied by another layer.
        complete = concrete.get(occurrence(record), [])
        if not record.get("expected") and len(complete) == 1:
            complete[0]["source_refs"] = unique(complete[0]["source_refs"] + record["source_refs"])
            continue
        retained.append(record)
    return recognize_records(bundle, retained, "E")
