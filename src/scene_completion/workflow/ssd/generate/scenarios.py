"""Forward-only contextual analysis of immutable reference scenario variants."""

import re
from copy import deepcopy

from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, ENTITY_PROFILE
from scene_completion.domain.ssd import concern_policy
from scene_completion.domain.ssd.construction import add_scenario, ident
from scene_completion.domain.ssd.llm_responses import KEY as LLM_RESPONSE_KEY
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
    entity_only = bundle.get("analysis_profile") == ENTITY_PROFILE
    if entity_only:
        entity_ids.update(
            unit["entity"]
            for unit in bundle.get("field_anchors", {}).get("units", [])
            if unit["step_id"] == step["id"]
        )
    return {
        "case": {k: bundle["case"][k] for k in ("id", "name") if k in bundle["case"]},
        "step": _positive(
            {
                k: step.get(k)
                for k in CONTEXT_FIELDS
                if not entity_only or k not in {"data", "api_id"}
            }
        ),
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
                **(
                    {"scenario_policy": bundle["scenario_policy"]}
                    if concern_policy.applies(bundle)
                    else {}
                ),
                "concerns": _positive(scoped),
                **(
                    {
                        "idempotency_evidence": {
                            c["id"]: [
                                ref["origin"]["quote"]
                                for ref in c.get("source_refs", [])
                                if (ref.get("origin") or {}).get("match") in {"exact", "located"}
                                and ref["origin"].get("quote")
                            ]
                            for c in scoped
                            if c["key"].endswith(".idempotency")
                        }
                    }
                    if bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE
                    else {}
                ),
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
                            "attribute",
                            "condition",
                            "expected",
                            "applicable_operations",
                            "template_id",
                            "variant_id",
                            "template_version",
                            "resource_reference",
                            "resource_failure",
                            "failure_variants",
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
    concerns = {r["id"]: r for r in inputs["concerns"]}
    seen = {(r["concern_id"], _condition(r["condition"])) for r in inputs["all_failure_conditions"]}
    for item in payload["supplements"]:
        if item["concern_id"] not in concerns:
            raise ValueError("补充场景只能引用本步骤已挂载的关注点")
        if concerns[item["concern_id"]].get("key") == LLM_RESPONSE_KEY:
            raise ValueError("外部大模型响应解析场景只使用按响应契约选定的固定模板")
        if concern_policy.applies(inputs) and concern_policy.fixed_only(
            concerns[item["concern_id"]]["key"]
        ):
            raise ValueError("合并后的认证、数据库特殊字符及并发场景只填写固定场景分析")
        if concerns[item["concern_id"]].get("input_group"):
            raise ValueError("数据类补充须先确认具体字段及约束，再生成场景")
        if concerns[item["concern_id"]].get("path_input"):
            raise ValueError("路径参数只填写按接口模板生成的固定场景分析")
        if concerns[item["concern_id"]].get("rule_id", "").startswith("crud-resource-v1:"):
            raise ValueError("CRUD 资源检查只对按路径与约束确定的失败条件填写分析")
        if any(not item[k].strip() for k in ("condition", "expected", "analysis")):
            raise ValueError("补充场景必须包含失败条件、预期处理和业务分析")
        key = (item["concern_id"], _condition(item["condition"]))
        if key in seen:
            raise ValueError("补充场景不得重复固定模板或其他补充的失败条件")
        seen.add(key)
    return payload


def _replay_variant(text):
    """Distinguish specifically declared replay conditions from generic repeats."""
    rules = {
        "changed_payload": r"参数.{0,8}(?:不同|修改|变化)|不同(?:的)?(?:参数|请求体)|different payload",
        "in_flight": r"执行中|处理完成前|尚未完成|in.flight",
        "key_expiry": r"幂等键.{0,8}(?:过期|失效)|expired.{0,12}key",
    }
    return next((key for key, pattern in rules.items() if re.search(pattern, text, re.I)), None)


def _idempotency_supplement(inputs, concern, item, scenarios):
    allowed = inputs.get("idempotency_evidence", {})
    if concern["id"] not in allowed:
        return True
    quote = item.get("source_quote", "").strip()
    variant = _replay_variant(item["condition"])
    supported = (
        variant
        and quote
        and _replay_variant(quote) == variant
        and any(quote in evidence for evidence in allowed[concern["id"]])
    )
    existing = [row for row in scenarios if concern["id"] in row["concern_ids"]]
    if supported and not any(_replay_variant(row["condition"]) == variant for row in existing):
        return True
    # Keep an alternative explanation with the existing failure, without adding a scored row.
    target = next(
        (row for row in existing if _replay_variant(row["condition"]) == variant),
        next((row for row in existing if row.get("variant_id") == "repeated_effect"), None),
    )
    if target:
        target["analysis"] = "\n".join(
            dict.fromkeys(
                text for text in (target.get("analysis"), item["analysis"].strip()) if text
            )
        )
    return False


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
        if not _idempotency_supplement(inputs, concern, item, records["scenarios"]):
            continue
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
    from scene_completion.workflow.ssd.generate.fixed import generate_g

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
