"""Forward-only contextual analysis of immutable reference scenario variants."""

import re
from copy import deepcopy

from scene_completion.domain.ssd.construction import add_scenario, ident
from scene_completion.infrastructure.identity import fingerprint

VERSION = "ssd-scenario-analysis-v1"
CONTEXT_FIELDS = (
    "id",
    "kind",
    "direction",
    "sender",
    "receiver",
    "operation",
    "data",
    "api_id",
    "entity_ids",
)


def _positive(value):
    """Drop provenance quotations and non-forward records from the model projection."""
    if isinstance(value, list):
        return [_positive(row) for row in value]
    if isinstance(value, dict):
        return {
            k: _positive(v)
            for k, v in value.items()
            if k
            not in {
                "source_refs",
                "source_chain",
                "documents",
                "channels",
                "decisions",
                "exceptions",
                "abnormal",
                "branches",
                "tests",
                "pending",
                "example_failures",
            }
        }
    return value


def step_context(bundle, step):
    entity_ids = set(step.get("entity_ids", []))
    return {
        "case": {k: bundle["case"][k] for k in ("id", "name") if k in bundle["case"]},
        "step": _positive({k: step.get(k) for k in CONTEXT_FIELDS}),
        "apis": _positive([a for a in bundle.get("apis", []) if a.get("id") == step.get("api_id")]),
        "entities": _positive([e for e in bundle.get("entities", []) if e.get("id") in entity_ids]),
    }


def context_identity(bundle, step):
    return fingerprint([VERSION, step_context(bundle, step)])


def needs_analysis(row):
    return (
        row.get("status") == "active" and row.get("generation_origin") != "deterministic_constraint"
    )


def batches(bundle, limit=32):
    """Batch within one step; every packet carries that use case and exact object."""
    definitions = bundle["registry"]["definitions"]
    concerns = {c["id"]: c for c in bundle["channels"]["G"]["concerns"]}
    for step in bundle["steps"]:
        context = context_identity(bundle, step)
        rows = [
            r
            for r in bundle["channels"]["G"]["scenarios"]
            if r.get("step_id") == step["id"]
            and needs_analysis(r)
            and r.get("generation_origin") != "model_supplement"
            and not (r.get("analysis") and r.get("generation_context") == context)
        ]
        for offset in range(0, len(rows), limit):
            selected = rows[offset : offset + limit]
            ids = {cid for row in selected for cid in row["concern_ids"]}
            scoped = [concerns[cid] for cid in sorted(ids)]
            yield {
                **step_context(bundle, step),
                "concerns": _positive(scoped),
                "definitions": {c["key"]: _positive(definitions[c["key"]]) for c in scoped},
                "templates": [
                    {
                        k: deepcopy(r[k])
                        for k in (
                            "id",
                            "concern_ids",
                            "key",
                            "target",
                            "field_id",
                            "entity_id",
                            "condition",
                            "expected",
                            "template_id",
                            "variant_id",
                            "template_version",
                        )
                        if k in r
                    }
                    for r in selected
                ],
                "all_failure_conditions": [
                    {"concern_id": cid, "condition": r["condition"]}
                    for r in bundle["channels"]["G"]["scenarios"]
                    for cid in r["concern_ids"]
                    if cid in ids
                ],
            }


def _condition(value):
    return re.sub(r"\s+", "", value).casefold()


def _filled(item):
    return any(
        str(item.get(k, "")).strip() for k in ("concern_id", "condition", "expected", "analysis")
    )


def validate_result(payload, inputs):
    payload["supplements"] = [row for row in payload.get("supplements", []) if _filled(row)]
    expected = {r["id"] for r in inputs["templates"]}
    returned = [r["scenario_id"] for r in payload["analyses"]]
    if set(returned) != expected or len(returned) != len(expected):
        raise ValueError("场景分析必须逐项覆盖本批全部固定模板，不能遗漏、重复或新增模板ID")
    if any(not r["analysis"].strip() for r in payload["analyses"]):
        raise ValueError("每个固定场景必须提供非空的业务分析")
    concerns = {r["id"] for r in inputs["concerns"]}
    seen = {(r["concern_id"], _condition(r["condition"])) for r in inputs["all_failure_conditions"]}
    for item in payload["supplements"]:
        if item["concern_id"] not in concerns:
            raise ValueError("补充场景只能引用本步骤已挂载的关注点")
        if any(not item[k].strip() for k in ("condition", "expected", "analysis")):
            raise ValueError("补充场景必须包含失败条件、预期处理和业务分析")
        key = (item["concern_id"], _condition(item["condition"]))
        if key in seen:
            raise ValueError("补充场景不得重复固定模板或其他补充的失败条件")
        seen.add(key)
    return payload


def apply_result(bundle, inputs, payload):
    validate_result(payload, inputs)
    records = bundle["channels"]["G"]
    by_id = {r["id"]: r for r in records["scenarios"]}
    step = next(s for s in bundle["steps"] if s["id"] == inputs["step"]["id"])
    context = context_identity(bundle, step)
    for item in payload["analyses"]:
        by_id[item["scenario_id"]].update(
            analysis=item["analysis"].strip(),
            analysis_origin="model",
            analysis_version=VERSION,
            generation_context=context,
        )
    concerns = {r["id"]: r for r in records["concerns"]}
    for item in payload["supplements"]:
        concern = concerns[item["concern_id"]]
        row = add_scenario(
            records,
            concern,
            item["condition"].strip(),
            item["expected"].strip(),
            deepcopy(concern.get("source_refs", [])),
            identity=ident("G-supplement", concern["id"], _condition(item["condition"])),
        )
        row.update(
            analysis=item["analysis"].strip(),
            generation_origin="model_supplement",
            analysis_origin="model",
            analysis_version=VERSION,
            generation_context=context,
        )


def capture_machine(bundle):
    bundle["machine_g"] = deepcopy(bundle["channels"]["G"])
    refresh_status(bundle)
    return bundle


def refresh_status(bundle):
    steps = {s["id"]: context_identity(bundle, s) for s in bundle["steps"]}
    rows = [r for r in bundle["channels"]["G"]["scenarios"] if needs_analysis(r)]
    pending = [
        r["id"]
        for r in rows
        if not r.get("analysis")
        or (
            r.get("analysis_origin") == "model"
            and r.get("generation_context") != steps.get(r.get("step_id"))
        )
    ]
    bundle["scenario_generation"] = {
        "version": VERSION,
        "required": len(rows),
        "completed": len(rows) - len(pending),
        "pending_ids": pending,
        "complete": not pending,
    }


def regenerate_machine(bundle, previous):
    """Keep only unchanged-step model enrichment when a reviewer edits SSD context."""
    from scene_completion.analysis.ssd.pipeline import generate_g

    output = generate_g(bundle)
    old = previous.get("machine_g", previous["channels"]["G"])
    by_id = {r["id"]: r for r in old["scenarios"]}
    contexts = {s["id"]: context_identity(bundle, s) for s in bundle["steps"]}
    for row in output["scenarios"]:
        source = by_id.get(row["id"], {})
        if source.get("generation_context") == contexts.get(row.get("step_id")):
            for key in ("analysis", "analysis_origin", "analysis_version", "generation_context"):
                if key in source:
                    row[key] = deepcopy(source[key])
    concerns = {r["id"] for r in output["concerns"]}
    for row in old["scenarios"]:
        if row.get("generation_origin") == "model_supplement" and (
            row.get("generation_context") == contexts.get(row.get("step_id"))
            and set(row.get("concern_ids", [])) <= concerns
        ):
            output["scenarios"].append(deepcopy(row))
    return output


def model_packet(inputs):
    """Short per-packet handles prevent transcription errors in opaque stable IDs."""
    projected = deepcopy(inputs)
    mapping = {}
    for n, row in enumerate(projected["templates"], 1):
        handle = f"T{n:02d}"
        mapping[handle] = row["id"]
        row["id"] = handle
    return projected, mapping


def restore_handles(payload, mapping):
    result = deepcopy(payload)
    for row in result["analyses"]:
        if row["scenario_id"] not in mapping:
            raise ValueError("场景分析引用未知模板短编号")
        row["scenario_id"] = mapping[row["scenario_id"]]
    return result
