"""Task-specific model views; retained artifacts keep the full validated contract."""

import re
from copy import deepcopy


def ssd_context(inputs):
    """Select only identities mentioned/evidenced in this paired use case and ancestors.

    This tool does not discover new actors or infer calls. Unresolved identities
    remain a model clarification rather than falling back to the global graph.
    """
    docs = inputs["RR"] + inputs["SR"]
    text = "\n".join(r["text"] for d in docs for r in d["lines"])
    ranges = {d["source_id"]: {r["number"] for r in d["lines"]} for d in docs}
    components = inputs["components"]["components"]
    selected = set()
    for c in components:
        if c["composition_type"] == "用例":
            continue
        name = c["name"]
        table = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*表", name)
        pattern = (
            r"(?<![A-Za-z0-9_])" + re.escape(table[1]) + r"\s*表"
            if table
            else r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])"
            if name.isascii()
            else re.escape(name)
        )
        if re.search(pattern, text, re.I) or any(
            set(range(r["line_start"], r["line_end"] + 1)) & ranges.get(r["source_id"], set())
            for r in c["source_refs"]
        ):
            selected.add(c["id"])
    while True:
        parents = {c["parent_id"] for c in components if c["id"] in selected and c.get("parent_id")}
        if parents <= selected:
            break
        selected.update(parents)
    if not selected:
        from scene_completion.workflow_core import TaskBlocked

        raise TaskBlocked(
            "awaiting_context",
            {
                "reason": "当前用例无法与系统组成身份对应，请确认名称/组成，不回退全量组成图",
                "case": inputs["case-group"]["id"],
            },
        )
    return {
        **deepcopy(inputs),
        "components": {
            "components": [deepcopy(c) for c in components if c["id"] in selected],
            "relations": [
                deepcopy(r)
                for r in inputs["components"].get("relations", [])
                if {r["from_id"], r["to_id"]} <= selected
            ],
        },
    }


def generation_matches(inputs):
    from scene_completion.analysis.concerns.concern_hierarchy import match_is_applicable
    from scene_completion.analysis.interactions.interaction_enrichment import interactions

    by_id = {i["id"]: i for i in interactions(inputs)}
    mechanical = {"service.base.availability", "service.query_retrieval.resource_existence"}
    from scene_completion.analysis.concerns.normal_rules import rule_matches

    indexed = {(r["interaction_id"], r["object"], r["concern_key"]) for r in rule_matches(inputs)}
    return [
        deepcopy(m)
        for m in inputs["concern-match"]["matches"]
        if (m["interaction_id"], m["object"], m["concern_key"]) not in indexed
        and m["interaction_id"] in by_id
        and match_is_applicable(m, by_id[m["interaction_id"]], inputs)
        and m.get("concrete_rule")
        and not m["concern_key"].startswith("api.data.")
        and m["concern_key"] not in mechanical
        and not m.get("policy_id")
    ]


def semantic_view(task, inputs):
    if task == "business-crud":
        from scene_completion.analysis.interactions.crud_review import context

        return context(inputs)
    if task == "test-operation-project":
        from scene_completion.inputs.provenance.test_sources import records

        out = deepcopy(inputs)
        for doc in out["test-operation-source"]:
            parsed = records([doc])
            if any(r.get("source_format") == "recovered_usecase" for r in parsed):
                # Recovery notes contain failure triggers and expected responses.
                # Only explicit success context/capability titles reach this tool.
                normal = [r for r in parsed if r["scenario_type"] == "normal"]
                allowed = {n for r in normal for n in [r["row"], *r.get("context_rows", [])]}
                doc["lines"] = [r for r in doc["lines"] if r["number"] in allowed]
        return out
    if task in {"existing-concerns", "test-concerns"}:
        return inverse_concern_context(inputs)
    if task == "test-supplement":
        out = deepcopy(inputs)
        out["normal-constraints"] = {"apis": []}  # typed contract mutations are tools
        out["normal-rules"]["rules"] = [
            r for r in out["normal-rules"]["rules"] if not r["concern_key"].startswith("api.data.")
        ]
        out["normal-rules"]["pending"] = []
        out["fused-ssd"] = {
            "interactions": [
                {
                    k: deepcopy(i[k])
                    for k in (
                        "id",
                        "case_id",
                        "direction",
                        "parent_id",
                        "sender",
                        "receiver",
                        "operation",
                    )
                }
                for i in out["fused-ssd"]["interactions"]
            ]
        }
        for i in out["fused-ssd"]["interactions"]:
            i["sender"] = {k: i["sender"][k] for k in ("name", "position")}
            i["receiver"] = {k: i["receiver"][k] for k in ("name", "position")}
            i["operation"] = {k: i["operation"][k] for k in ("name", "kinds")}
        keys = {r["concern_key"] for r in out["normal-rules"]["rules"]}
        out["registry"] = {
            "version": out["registry"]["version"],
            "definitions": {
                k: {f: v[f] for f in ("label", "description")}
                for k, v in out["registry"]["definitions"].items()
                if k in keys
            },
        }
        return out
    if task == "semantic-compare":
        # Classify the concrete failure first. Concern labels and documented
        # recovery are retained in artifacts and compared separately by tools.
        fields = {
            "id",
            "case_id",
            "interaction_id",
            "object",
            "operation",
            "cause",
            "conditions",
            "field",
            "scope",
            "data_location",
        }
        return {
            **deepcopy(inputs),
            **{
                k: [{f: deepcopy(v) for f, v in s.items() if f in fields} for s in inputs[k]]
                for k in ("left", "right")
            },
        }
    """Remove duplicate views and derived display metadata, never source facts."""
    out = deepcopy(inputs)
    relevant = {
        "existing-concerns",
        "test-concerns",
        "normal-rules",
        "concern-match",
        "exception-generate",
        "existing-bind",
        "existing-extract",
        "test-ground-truth",
    }
    if task not in relevant:
        return out
    from scene_completion.analysis.matching.inverse_alignment import canonical_fused

    if "fused-ssd" in out:
        # Inverse binding accepts only canonical interaction IDs, not aliases.
        out["fused-ssd"] = canonical_fused(out["fused-ssd"], inputs)
        if task in {"existing-concerns", "test-concerns"}:
            from scene_completion.analysis.matching.concern_alignment import interaction_rows

            out["fused-ssd"]["interactions"] = interaction_rows(inputs)
        out["fused-ssd"].pop("aliases", None)
        out["fused-ssd"].pop("source_views", None)
        if task == "normal-rules":
            out["fused-ssd"]["interactions"] = [
                {
                    k: i[k]
                    for k in (
                        "id",
                        "direction",
                        "step_kind",
                        "validates",
                        "sender",
                        "receiver",
                        "operation",
                        "data",
                        "source_refs",
                    )
                    if k in i
                }
                for i in out["fused-ssd"]["interactions"]
            ]
    if "enriched-interactions" in out:
        rows = out.pop("enriched-interactions")["interactions"]
        messages = []
        for i in rows:
            v = {
                k: deepcopy(i[k])
                for k in (
                    "id",
                    "case_id",
                    "sequence",
                    "parent_id",
                    "layer",
                    "sender",
                    "receiver",
                    "operation",
                    "data",
                    "direction",
                    "api_id",
                    "source_refs",
                )
            }
            v["associated_api"] = i.get("associated_api")
            v["classification"] = i.get("classification")
            # Capability unions and repeated resolved concerns are display data;
            # the actual operation is already explicit in each message.
            for role in ("sender", "receiver"):
                v[role] = {k: v[role][k] for k in ("name", "position", "source_refs")}
                resource = i[role].get("resource_service")
                if resource:
                    v[role]["resource_service"] = resource
            v["data"] = {"sequence": v["data"]["sequence"]}
            messages.append(v)
        out["interactions"] = messages
        # Explicit field attributes occur once on each actual interaction.
        for key in (
            "rr-ssd",
            "sr-ssd",
            "api-map",
            "api-parameters",
            "object-operations",
            "components",
        ):
            out.pop(key, None)
    if task == "concern-match":
        from scene_completion.analysis.evaluation.recognition_coverage import field_reviews

        out["required_field_reviews"] = field_reviews(inputs)
        from scene_completion.analysis.matching.concern_alignment import index_elements

        out["four_element_index"] = index_elements(inputs)
        out["recognition_instruction"] = (
            "逐项审阅已声明字段约束并独立提交识别；该清单不是G。matches中的数据关注点"
            "必须target=data，object为具体字段名并填写data_location，不能统称Product等实体。"
            "请求和返回分别处理；不得把明确类型、必填或数值约束说成未知。"
            "身份/权限项须提交明示activation_evidence，或说明确实缺少哪些前提。"
        )
    if task == "exception-generate" and "concern-match" in out:
        # The full review matrix includes inherited, pending and inapplicable
        # rows for every interaction. Generation receives only semantic checks
        # with an actual rule; mechanical candidates are supplied once by tools.
        keys = {
            "interaction_id",
            "target",
            "object",
            "concern_key",
            "basis",
            "concrete_rule",
            "source_refs",
            "activation_evidence",
            "scope",
            "data_location",
        }
        matches = [{k: v for k, v in m.items() if k in keys} for m in generation_matches(inputs)]
        out["concern-match"] = {"matches": matches}
    if "registry" in out:
        out["registry"]["definitions"] = {
            key: {
                k: v
                for k, v in row.items()
                if k
                in {
                    "label",
                    "description",
                    "guard",
                    "kind",
                    "operation_kinds",
                    "technology",
                    "parents",
                }
            }
            for key, row in out["registry"]["definitions"].items()
            if row.get("enabled", True)
        }
        if task == "concern-match" and inputs.get("recognition_scope") == "data":
            out["registry"]["definitions"] = {
                k: d for k, d in out["registry"]["definitions"].items() if k.startswith("api.data.")
            }
    if task in {"existing-concerns", "test-concerns"}:
        from scene_completion.analysis.matching.concern_alignment import index_elements

        out["four_element_index"] = index_elements(inputs)
    if task in {"existing-extract", "test-ground-truth", "existing-concerns", "test-concerns"}:
        # Original branches/test rows are retained; no duplicate composition or
        # full API table. normal-constraints is already scoped to this use case.
        out.pop("components", None)
        out.pop("api-map", None)
        if "normal-rules" in out and task in {"existing-extract", "existing-concerns"}:
            out.pop("existing-documents", None)
    if task in {
        "existing-bind",
        "existing-extract",
        "test-ground-truth",
        "existing-concerns",
        "test-concerns",
    }:
        # Inverse tasks receive positive facts, never the positive generator's
        # derived negative candidates through a shared-rule side channel.
        for rule in out.get("normal-rules", {}).get("rules", []):
            rule.pop("violation", None)
        if task == "existing-bind":
            out.pop("normal-rules", None)
            out["fused-ssd"]["interactions"] = [
                {
                    k: i[k]
                    for k in (
                        "id",
                        "layer",
                        "api_id",
                        "parent_id",
                        "direction",
                        "sender",
                        "receiver",
                        "operation",
                        "data",
                    )
                }
                for i in out["fused-ssd"]["interactions"]
            ]
        if task in {"existing-extract", "existing-concerns"} and "bindings" in out:
            ids = {
                b["interaction_id"]
                for b in out["bindings"]["bindings"]
                if b["status"] == "confirmed"
            }
            # The validated ID is authoritative. Historical reasoning may
            # describe a propagation step before tool normalization; retain
            # it in the artifact, not as a contradictory modelling directive.
            out["bindings"] = {
                "bindings": [
                    {k: b[k] for k in ("branch_id", "interaction_id", "status")}
                    for b in out["bindings"]["bindings"]
                ]
            }
            if ids:
                out["fused-ssd"]["interactions"] = [
                    i for i in out["fused-ssd"]["interactions"] if i["id"] in ids
                ]
                out["normal-rules"]["rules"] = [
                    r
                    for r in out.get("normal-rules", {}).get("rules", [])
                    if r["interaction_id"] in ids
                ]
                fields = {
                    p["name"]
                    for i in out["fused-ssd"]["interactions"]
                    for p in i["data"]["sequence"]
                }
                out["normal-constraints"] = {
                    "apis": [
                        {**a, "parameters": [p for p in a["parameters"] if p["name"] in fields]}
                        for a in out.get("normal-constraints", {}).get("apis", [])
                        if any(p["name"] in fields for p in a["parameters"])
                    ]
                }
        if task in {"test-ground-truth", "test-concerns"}:
            from scene_completion.inputs.provenance.test_sources import records_for_inputs

            tests = records_for_inputs(out)
            text = " ".join(r["触发条件"] + " " + r["测试名称"] for r in tests)
            if any(r.get("source_format") == "recovered_usecase" for r in tests):
                out["test_record_index"] = [
                    {k: r[k] for k in ("id", "scenario_type", "关联需求", "row")} for r in tests
                ]
            # Keep an identity/operation index for every call. Detailed normal
            # rules/attributes are scoped to literal tested fields/services;
            # no candidate interaction disappears, and no G/E is consulted.
            selected = {
                i["id"]
                for i in out.get("fused-ssd", {}).get("interactions", [])
                if i["receiver"]["name"] in text
                or i["sender"]["name"] in text
                or any(p["name"] in text for p in i["data"]["sequence"])
            }
            if "identified-concerns" in out:
                selected = {
                    m["interaction_id"]
                    for m in out["identified-concerns"]["matches"]
                    if m.get("status") == "applicable"
                }
            if selected or "identified-concerns" in out:
                for i in out["fused-ssd"]["interactions"]:
                    if i["id"] not in selected:
                        i["data"] = {"sequence": []}
                out["normal-rules"]["rules"] = [
                    r
                    for r in out.get("normal-rules", {}).get("rules", [])
                    if r["interaction_id"] in selected
                ]
                fields = {
                    p["name"]
                    for i in out["fused-ssd"]["interactions"]
                    if i["id"] in selected
                    for p in i["data"]["sequence"]
                }
                out["normal-constraints"] = {
                    "apis": [
                        {**a, "parameters": [p for p in a["parameters"] if p["name"] in fields]}
                        for a in out.get("normal-constraints", {}).get("apis", [])
                        if any(p["name"] in fields for p in a["parameters"])
                    ]
                }
        for i in out.get("fused-ssd", {}).get("interactions", []):
            for side in ("sender", "receiver"):
                i[side] = {k: i[side][k] for k in ("name", "position")}
            i["operation"] = {k: i["operation"][k] for k in ("name", "kinds", "sequence")}
            i["data"] = {
                "sequence": [{k: p[k] for k in ("name", "location")} for p in i["data"]["sequence"]]
            }
        if "registry" in out:
            text = str(out.get("fused-ssd", {}))
            techs = ({"database"} if "数据库" in text else set()) | (
                {"llm"}
                if any(k in text.lower() for k in ("llm", "大语言", "large language"))
                else set()
            )
            out["registry"]["definitions"] = {
                k: v
                for k, v in out["registry"]["definitions"].items()
                if not v.get("technology") or v["technology"] in techs
            }
    if task in {"existing-extract", "test-ground-truth"} and "identified-concerns" in inputs:
        from scene_completion.analysis.scenarios.refinement_context import narrow

        out = narrow(out, inputs)

    if "identified-concerns" in out:
        # Recognition prose is saved for review, not a second source of facts.
        # The selected element/category and its evidence already scope the
        # next stage. Rewording its explanation must not retrigger a paid call.
        out["identified-concerns"] = {
            "matches": [
                {
                    k: m[k]
                    for k in (
                        "binding_ref",
                        "interaction_id",
                        "target",
                        "object",
                        "concern_key",
                        "data_location",
                        "operation_index",
                        "source_refs",
                    )
                    if k in m
                }
                for m in out["identified-concerns"]["matches"]
                if m.get("status", "applicable") == "applicable"
            ],
            "pending": out["identified-concerns"].get("pending", []),
        }
    return out


def inverse_concern_context(inputs):
    """Recognize before refinement using an identity index, not all case rules.

    Every possible call identity remains selectable. Detailed field constraints
    are carried only for literal source fields or a confirmed broad E branch.
    A test is never narrowed using G/E or previous semantic pair decisions.
    """
    from scene_completion.analysis.matching.inverse_alignment import canonical_fused

    out = deepcopy(inputs)
    docs = out.get("test-documents", out.get("existing-documents", []))
    text = " ".join(r["text"] for d in docs for r in d["lines"])
    if "test-documents" in out:
        from scene_completion.inputs.provenance.test_sources import records_for_inputs

        tests = records_for_inputs(out)
        if tests:
            text = " ".join(
                r["测试名称"] + " " + r["触发条件"] + " " + r["预期结果"] for r in tests
            )
    branches = out.get("branches", {}).get("branches", [])
    bound = {
        b["interaction_id"]
        for b in out.get("bindings", {}).get("bindings", [])
        if b["status"] == "confirmed"
    }
    from scene_completion.analysis.matching.inverse_alignment import broad_input_branch

    broad = any(broad_input_branch(b["description"]) for b in branches)
    rows = canonical_fused(out["fused-ssd"], inputs)["interactions"]
    if bound:
        # A branch may name a local validation action. Keep the actual calls
        # delivering data to that executor visible; otherwise the model sees
        # only an action without fields and cannot identify its input/return.
        executors = {
            (i["case_id"], i["receiver"]["name"])
            for i in rows
            if i["id"] in bound
            and i.get("step_kind") == "action"
            and i["sender"]["name"] == i["receiver"]["name"]
            and re.search(r"校验|验证|validate|check", i["operation"]["name"], re.I)
        }
        rows = [
            i
            for i in rows
            if i["id"] in bound
            or (
                (i["case_id"], i["receiver"]["name"]) in executors
                and i.get("step_kind") != "action"
                and i["sender"]["name"] != i["receiver"]["name"]
            )
        ]
    # Explicit source identifiers establish relevance. Generic actor/system
    # names shared by every message do not select every local business rule.
    fields = {p["name"] for i in rows for p in i["data"]["sequence"] if p["name"] in text}
    fields |= {
        p["name"]
        for a in out["normal-constraints"]["apis"]
        for p in a["parameters"]
        if p["name"] in text
    }
    selected = [
        r
        for r in out.get("normal-rules", {}).get("rules", [])
        if (not bound or r["interaction_id"] in bound)
        and (
            set(r["fields"]) & fields
            or r.get("owner_service", "")
            and r["owner_service"] in text
            or bound
        )
    ]
    out["normal-rules"] = {
        "rules": [
            {
                k: r[k]
                for k in (
                    "id",
                    "interaction_id",
                    "owner_service",
                    "concern_key",
                    "condition",
                    "fields",
                    "source_refs",
                )
                if k in r
            }
            for r in selected
        ]
    }
    out["normal-constraints"] = {
        "apis": [
            {
                k: a[k]
                for k in ("id", "name", "address", "source_layer", "declared_id", "method")
                if k in a
            }
            | {
                "parameters": [
                    {k: p[k] for k in ("name", "location", "required", "data_type", "constraints")}
                    for p in a["parameters"]
                    if p["name"] in fields or broad
                ]
            }
            for a in out["normal-constraints"]["apis"]
            if broad or any(p["name"] in fields for p in a["parameters"])
        ]
    }
    from scene_completion.analysis.interactions.interaction_enrichment import (
        parameters_for,
        resolved_api_id,
    )

    material = {
        **inputs,
        "api-parameters": inputs["normal-constraints"],
        "rr-ssd": {"interactions": [i for i in rows if i["layer"] == "RR"]},
        "sr-ssd": {"interactions": [i for i in rows if i["layer"] == "SR"]},
    }
    used = {resolved_api_id(i, material) for i in rows}
    used.discard(None)
    out["normal-constraints"]["apis"] = [
        a for a in out["normal-constraints"]["apis"] if a["id"] in used
    ]
    out["interface_ownership"] = [
        {
            "interaction_id": i["id"],
            "model_layer": i["layer"],
            "api_id": resolved_api_id(i, material),
            "caller": i["sender"]["name"],
            "callee": i["receiver"]["name"],
            "local_checks": i["operation"]["sequence"],
        }
        for i in rows
    ]
    for i in rows:
        i["data"]["sequence"] = parameters_for(i, material)
    out["fused-ssd"] = {
        "interactions": [
            {
                k: i[k]
                for k in (
                    "id",
                    "layer",
                    "api_id",
                    "parent_id",
                    "direction",
                    "sender",
                    "receiver",
                    "operation",
                    "data",
                )
            }
            for i in rows
        ]
    }
    for i in out["fused-ssd"]["interactions"]:
        for side in ("sender", "receiver"):
            i[side] = {k: i[side][k] for k in ("name", "position")}
        i["operation"] = {k: i["operation"][k] for k in ("name", "kinds", "sequence")}
        i["data"] = {
            "sequence": [
                {k: p[k] for k in ("name", "location")}
                for p in i["data"]["sequence"]
                if broad or p["name"] in fields
            ]
        }
    if "registry" in out:
        out["registry"] = {
            "version": out["registry"]["version"],
            "definitions": {
                k: {f: v[f] for f in ("label", "description", "layer")}
                for k, v in out["registry"]["definitions"].items()
                if v.get("enabled", True) and v.get("kind") == "check"
            },
        }
    if branches:
        out.pop("existing-documents", None)
    return out
