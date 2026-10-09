"""Source-only classification audit: keep checker behavior and IDs frozen."""
from pathlib import Path

from .concerns import ACTIVE_CONCERN_KEYS
from .semantic_backend import collect_packets, prepare_packets, read_json
from .sources import fingerprint, use_case_sections, validate_refs


def taxonomy_packets(checker, index, directory, role="checker"):
    from .three_roles import taxonomy
    if role not in {"checker", "generator"}:
        raise ValueError("unknown classification role")
    if not checker.get("complete") or (role == "checker" and checker.get("source_hash") != fingerprint(index)):
        raise ValueError("taxonomy audit requires a complete checker bound to these sources")
    if role == "checker" and any(d.get("role") != "requirement" for d in index["documents"]):
        raise ValueError("taxonomy audit reads requirements only")
    def selected(s):
        return s["scenario_type"] == "requirement_exception" or (role == "generator"
            and s.get("generation_status") == "constraint_instantiation")
    payloads = []
    for uc in sorted({s["use_case_id"] for s in checker["scenarios"]
                      if selected(s)}):
        scenes = [{k: s[k] for k in ("scenario_id", "name", "trigger", "scenario_steps",
                                    "expected_result", "source_refs")}
                  for s in checker["scenarios"] if s["use_case_id"] == uc and
                  selected(s)]
        sections = []
        for region in use_case_sections(index, uc):
            doc = next(d for d in index["documents"] if d["document"] == region["document"])
            lines = doc["text"].splitlines()
            sections.append({**region, "numbered_text": "\n".join(
                f"{i}: {lines[i-1]}" for i in range(region["line_start"], region["line_end"]+1))})
        context = [{"document": d["document"], "numbered_text": "\n".join(
            f"{i}: {line}" for i, line in enumerate(d["text"].splitlines()[:45], 1))}
                   for d in index["documents"]]
        payloads.append({"use_case_id": uc, "scenarios": scenes, "sections": sections,
                         "requirement_context": context, "taxonomy": taxonomy()})
    return prepare_packets(directory, "checker-taxonomy" if role == "checker" else "generator-taxonomy", payloads, [
        ("Independently classify EVERY frozen requirement exception using the supplied taxonomy and original requirement evidence. No generated scenarios, design or prior labels are supplied." if role == "checker" else
         "Classify every supplied explicit branch and source constraint against the original requirement/design and taxonomy. No checker, tests, matching or prior labels are supplied. This ONLY assigns labels, never applicability or behavior."),
        "Do not change, split, merge, add or remove scenes. Return each supplied scenario_id exactly once. Keep behavior and the denominator frozen.",
        "Multiple concern keys are allowed only when each definition directly expresses the actual failure mechanism; general topic associations are insufficient.",
        "Business-rule violations can be expressed by business_constraint even if the response is manual review. A specific numeric boundary can also have api.data.range.",
        "External-service concerns require an evidenced external participant/boundary, not merely calling another named service. An internal service dependency can use service.dependency.availability.",
        "Use empty concern_keys only if no active definition expresses the condition; explain a taxonomy gap rather than inventing a category.",
        ("Cite exact assigned requirement sections. Include a brief classification reason grounded in the trigger and the selected definitions." if role == "checker" else
         "Cite exact assigned requirement/design sections. Include a brief classification reason grounded in the trigger and the selected definitions."),
    ], {"items": [{"scenario_id": "each frozen CHK-ID", "concern_keys": ["active keys"],
                   "reason": "source-grounded classification reason",
                   "source_refs": [{"document": "requirement filename", "line_start": 1, "line_end": 2}]}]})


def taxonomy_validator(index):
    def validate(packet, result):
        expected = {s["scenario_id"] for s in packet["input"]["scenarios"]}
        items = result.get("items")
        if not isinstance(items, list) or len(items) != len(expected):
            raise ValueError("taxonomy audit omitted frozen scenes")
        rows, seen = [], set()
        for row in items:
            if not isinstance(row, dict):
                raise ValueError("taxonomy audit items must be objects")
            sid, keys = row.get("scenario_id"), row.get("concern_keys")
            if sid not in expected or sid in seen:
                raise ValueError("taxonomy audit has unknown/duplicate scene ID")
            if (not isinstance(keys, list) or len(keys) != len(set(keys)) or
                    any(k not in ACTIVE_CONCERN_KEYS for k in keys)):
                raise ValueError("taxonomy audit has invalid concern keys")
            if not isinstance(row.get("reason"), str) or not row["reason"].strip():
                raise ValueError("taxonomy audit needs a classification reason")
            allowed = list(packet["input"]["sections"])
            # Actor/system boundary context is explicitly supplied alongside
            # the UC. Cite only that provided context, never arbitrary chapters.
            for region in packet["input"].get("requirement_context", []):
                lines = region["numbered_text"].splitlines()
                if lines:
                    allowed.append({"document": region["document"],
                                    "line_start": int(lines[0].partition(":")[0]),
                                    "line_end": int(lines[-1].partition(":")[0])})
            refs = validate_refs(row.get("source_refs"), index, allowed)
            rows.append({"scenario_id": sid, "concern_keys": sorted(keys),
                         "reason": row["reason"], "source_refs": refs})
            seen.add(sid)
        return rows
    return validate


def apply_taxonomy_audit(checker, index, directory, role="checker"):
    root = Path(directory)
    expected = taxonomy_packets(checker, index, root / "_expected", role)
    if read_json(root / "manifest.json")["input_hash"] != expected["input_hash"]:
        raise ValueError("taxonomy audit is bound to stale checker behavior or sources")
    from .taxonomy_audit import audited_taxonomy_validator
    rows, status = collect_packets(root, audited_taxonomy_validator(index))
    if not status["complete"]:
        return {**checker, "complete": False, "taxonomy_audit": {"batch_status": status}}
    by_id = {r["scenario_id"]: r for r in rows}
    scenes, changes = [], []
    for scene in checker["scenarios"]:
        updated = dict(scene)
        if scene["scenario_id"] in by_id:
            decision = by_id[scene["scenario_id"]]
            old, new = scene["concern_keys"], decision["concern_keys"]
            updated["concern_keys"] = new
            updated["classification_evidence"] = decision
            if set(old) != set(new):
                changes.append({"scenario_id": scene["scenario_id"], "old_keys": old,
                                "new_keys": new, "reason": decision["reason"],
                                "source_refs": decision["source_refs"]})
        scenes.append(updated)
    return {**checker, "scenarios": scenes, "taxonomy_audit": {
        "version": "requirement-classification-v2" if role == "checker" else "generator-classification-v1", "behavior_unchanged": True,
        "batch_status": status, "changes": changes, "exception_count": len(rows)}}
