"""Case Pipeline for the current workflow."""

from copy import deepcopy

from scene_completion.analysis.exception_comparison import missing_report
from scene_completion.analysis.interaction_enrichment import (
    actual_context,
    basic_views,
    bind_resource_services,
    capability_union,
    with_concerns,
)
from scene_completion.domain.concern_registry import active_registry_identity, default_registry
from scene_completion.domain.contracts import registry
from scene_completion.infrastructure.storage import write_json
from scene_completion.inputs.source_documents import normal_projection
from scene_completion.workflow.global_pipeline import _schedule_global_analysis
from scene_completion.workflow.support import analysis_settings, canonical_enrich


def _build_cases(
    ex,
    rr,
    sr,
    tests,
    catalogue,
    groups,
    extraction_truth,
    adjudications,
    test_catalogue=None,
    test_alignment=None,
    ar=None,
):
    from scene_completion.analysis.use_cases import select_documents
    from scene_completion.inputs.api_documents import case_parameters
    from scene_completion.inputs.source_documents import case_projection

    cases = [g["id"] for g in groups if g["status"] == "confirmed"]
    extraction_jobs = [("shared", t, t) for t in ("components", "api-map", "api-parameters")]
    for cid in cases:

        def key(t):
            return cid + ":" + t

        # Translate scheduler keys to task contract names only within this case.
        def add(
            task,
            deps=(),
            static=None,
            build=None,
            transform=None,
            cid=cid,
            partition=False,
            stage=None,
        ):
            def local(t):
                return (
                    t
                    if t in {"components", "api-map", "api-parameters", "business-entities"}
                    else cid + ":" + t
                )

            def construct(d):
                values = {t: d[local(t)] for t in deps}
                return build(values) if build else deepcopy(static or {})

            if partition and ex.config.get("partition_tasks", True):
                ex.partitioned(
                    cid + ":" + task, task, tuple(local(t) for t in deps), construct, cid
                )
            else:
                ex.add(
                    cid + ":" + task,
                    stage or task,
                    tuple(local(t) for t in deps),
                    static=static,
                    build=construct,
                    transform=transform,
                    case=cid,
                )

        group = next(g for g in groups if g["id"] == cid)
        from scene_completion.inputs.colleague_formats import scoped_entities

        entity_scope = (
            group["rr_ids"]
            + group["sr_ids"]
            + [
                c["name"]
                for layer in ("RR", "SR")
                for c in catalogue[layer]
                if c["id"] in group["rr_ids"] + group["sr_ids"]
            ]
        )
        active_tree_ids = {
            p["file_id"]
            for p in __import__(
                "scene_completion.inputs.artifact_imports", fromlist=["selections"]
            ).selections(ex.root.parent, "business-entities", frozen=ex.import_snapshot)
        }
        imported_interface_attributes = [
            a
            for row in ex.import_snapshot
            if row["id"] in active_tree_ids
            for a in row.get("colleague_product", {}).get("interface_attributes", [])
            if a["case_id"] in entity_scope or a["case_name"] in entity_scope
        ]
        scoped_rr = select_documents(
            rr, [c for c in catalogue["RR"] if c["id"] in group["rr_ids"]], catalogue["RR"]
        )
        scoped_sr = select_documents(
            sr, [c for c in catalogue["SR"] if c["id"] in group["sr_ids"]], catalogue["SR"]
        )
        base_existing = scoped_rr + scoped_sr
        from scene_completion.inputs.behavior_imports import materials as behavior_materials

        behavior = behavior_materials(ex.import_snapshot, entity_scope)
        scoped_rr += behavior["RR"]
        scoped_sr += behavior["SR"]
        scoped_ar = []
        if ar:
            from scene_completion.inputs.source_documents import case_projection

            all_case_ids = list(dict.fromkeys(x for g in groups for x in g["rr_ids"] + g["sr_ids"]))
            for source_id in group["rr_ids"] + group["sr_ids"]:
                scoped_ar.extend(case_projection(ar, source_id, all_case_ids))
            scoped_ar = list({d["source_id"]: d for d in scoped_ar}.values())
        test_ids = list(dict.fromkeys(x for g in groups for x in g["rr_ids"] + g["sr_ids"]))
        scoped_test = []
        for tid in group["rr_ids"] + group["sr_ids"]:
            scoped_test += case_projection(tests, tid, test_ids)
        if test_catalogue is not None:
            from scene_completion.analysis.test_alignment import scoped_tests

            scoped_test, case_test_catalogue = scoped_tests(
                test_catalogue, test_alignment, tests, cid
            )
        merged_test = {}
        for document in scoped_test:
            part = merged_test.setdefault(document["source_id"], {**document, "lines": []})
            rows = {r["number"]: r for r in part["lines"]}
            for row in document["lines"]:
                if row["number"] in rows and rows[row["number"]]["text"] != row["text"]:
                    raise ValueError("conflicting source text for the same test line")
                rows[row["number"]] = row
            part["lines"] = [rows[n] for n in sorted(rows)]
        scoped_test = list(merged_test.values())
        from scene_completion.inputs.test_sources import exception_documents, records

        if test_catalogue is not None:
            from scene_completion.analysis.test_alignment import as_records

            test_records = as_records(case_test_catalogue, scoped_test)
            abnormal_catalogue = {
                **case_test_catalogue,
                "tests": [
                    t for t in case_test_catalogue["tests"] if t["scenario_type"] == "exception"
                ],
            }
            abnormal_test = scoped_test if abnormal_catalogue["tests"] else []
            test_input = {"test-inventory": abnormal_catalogue}
        else:
            test_records = records(scoped_test)
            abnormal_test = exception_documents(scoped_test)
            test_input = {}
        write_json(
            ex.root / "test_catalogues" / (cid + ".json"),
            {
                "records": test_records,
                "policy": "exception-only",
                "version": "exception-test-sources-v1",
            },
        )
        existing_docs = list(
            {doc["source_id"]: doc for doc in base_existing + behavior["existing"]}.values()
        )
        add(
            "existing-branches-source",
            static={"existing-documents": existing_docs},
            stage="existing-branches",
        )
        from scene_completion.workflow.task_context import ssd_context

        add(
            "ssd-context",
            ("components",),
            static={
                "RR": normal_projection(scoped_rr),
                "SR": normal_projection(scoped_sr),
                "case-group": group,
            },
            build=lambda d, rr=normal_projection(scoped_rr), sr=normal_projection(scoped_sr), g=group: {
                "RR": rr,
                "SR": sr,
                "components": d["components"],
                "case-group": g,
            },
            transform=ssd_context,
        )
        add(
            "fused-ssd-source",
            ("ssd-context",),
            build=lambda d: d["ssd-context"],
            stage="fused-ssd",
        )
        from scene_completion.analysis.atomic_steps import apply_plan, compact

        add(
            "interaction-normalize",
            ("fused-ssd-source", "ssd-context"),
            build=lambda d: {
                "candidate": compact(d["fused-ssd-source"]),
                "normal-documents": d["ssd-context"]["RR"] + d["ssd-context"]["SR"],
                "components": d["ssd-context"]["components"],
                "case-group": d["ssd-context"]["case-group"],
            },
        )
        add(
            "fused-ssd",
            ("fused-ssd-source", "interaction-normalize", "ssd-context"),
            build=lambda d: {
                **d["ssd-context"],
                "raw": d["fused-ssd-source"],
                "plan": d["interaction-normalize"],
            },
            transform=lambda d: apply_plan(d["raw"], d["plan"], d["case-group"]["id"]),
        )

        from scene_completion.analysis.exception_scopes import (
            interaction_branches,
            records_from_tests,
        )

        scope_catalogue = [{"id": g["id"], "aliases": g["rr_ids"] + g["sr_ids"]} for g in groups]
        add(
            "existing-scope",
            ("existing-branches-source", "business-entities"),
            build=lambda d, cat=scope_catalogue: {
                "channel": "existing",
                "source-records": d["existing-branches-source"]["branches"],
                "case-catalogue": cat,
                "entity-index": {
                    "entities": [
                        {"id": e["id"], "name": e["name"]}
                        for e in d["business-entities"]["entities"]
                    ]
                },
            },
            stage="exception-scope",
        )
        add(
            "test-scope",
            ("business-entities",),
            static={"source-records": records_from_tests(test_records)},
            build=lambda d, records=records_from_tests(test_records), cat=scope_catalogue: {
                "channel": "test",
                "source-records": records,
                "case-catalogue": cat,
                "entity-index": {
                    "entities": [
                        {"id": e["id"], "name": e["name"]}
                        for e in d["business-entities"]["entities"]
                    ]
                },
            },
            stage="exception-scope",
        )
        add(
            "existing-branches",
            ("existing-branches-source", "existing-scope"),
            build=lambda d, docs=existing_docs: {**d, "existing-documents": docs},
            transform=lambda d: interaction_branches(
                d["existing-branches-source"], d["existing-scope"]
            ),
        )

        def crud_input(
            d,
            rr_docs=normal_projection(scoped_rr),
            sr_docs=normal_projection(scoped_sr),
            ar_docs=normal_projection(scoped_ar),
            entity_scope=entity_scope,
        ):
            return {
                "normal-documents": rr_docs + sr_docs + ar_docs,
                "business-entities": scoped_entities(d["business-entities"], entity_scope),
                "fused-ssd": d["fused-ssd"],
            }

        add("business-crud", ("business-entities", "fused-ssd"), build=crud_input)
        for layer in ("RR", "SR"):
            add(
                layer.lower() + "-ssd",
                ("fused-ssd",),
                build=lambda d: d,
                transform=lambda d, source_line=layer: {
                    "interactions": [
                        i for i in d["fused-ssd"]["interactions"] if i["layer"] == source_line
                    ]
                },
            )
        add(
            "test-operation-project",
            static={"test-operation-source": scoped_test},
            transform=(lambda d: {"objects": []}) if not scoped_test else None,
        )
        add(
            "object-operations",
            ("components", "rr-ssd", "test-operation-project"),
            build=lambda d: {
                "components": d["components"],
                "rr-ssd": d["rr-ssd"],
                "test-operations": d["test-operation-project"],
            },
            transform=capability_union,
        )
        add(
            "interaction-align",
            ("components", "rr-ssd", "sr-ssd", "fused-ssd"),
            build=lambda d: d,
            transform=lambda d: {"aliases": [], "links": d["fused-ssd"]["rr_sr_links"]},
        )
        positive = normal_projection(scoped_rr) + normal_projection(scoped_sr)

        def data_dependency_input(d, docs=positive + normal_projection(scoped_ar)):
            return {
                "normal-documents": docs,
                "components": d["components"],
                "api-map": d["api-map"],
                "api-parameters": case_parameters(d, d["fused-ssd"]),
                "fused-ssd": d["fused-ssd"],
            }

        add(
            "data-dependencies",
            ("components", "api-map", "api-parameters", "fused-ssd"),
            build=data_dependency_input,
        )
        from scene_completion.inputs.api_layers import qualify_fused_calls

        add(
            "normal-rules",
            ("fused-ssd", "api-map", "api-parameters"),
            build=lambda d, positive=positive: {
                "normal-documents": positive,
                "fused-ssd": qualify_fused_calls(d["fused-ssd"], d),
                **(
                    {"registry": registry()}
                    if active_registry_identity(registry())
                    != active_registry_identity(default_registry())
                    else {}
                ),
            },
            partition=True,
        )
        normal = (
            "components",
            "rr-ssd",
            "sr-ssd",
            "api-map",
            "api-parameters",
            "object-operations",
            "normal-rules",
        )

        def enrich_input(d, scope=entity_scope, attributes=imported_interface_attributes):
            return {
                **d,
                "business-entities": scoped_entities(d["business-entities"], scope),
                "colleague-interface-attributes": attributes,
            }

        add(
            "interaction-enrich",
            normal + ("interaction-align", "business-crud", "business-entities"),
            build=enrich_input,
            transform=lambda d: canonical_enrich(d),
        )
        positive = normal_projection(scoped_rr) + normal_projection(scoped_sr)

        def concern_input(d, positive=positive, scope=entity_scope):
            v = {k: d[k] for k in normal}
            v = bind_resource_services(v)
            v.update(basic_views(d["interaction-enrich"]))
            v["api-parameters"] = case_parameters(v, d["interaction-enrich"])
            return {
                **v,
                "enriched-interactions": d["interaction-enrich"],
                "normal-documents": positive,
                "registry": registry(),
                "business-crud": d["business-crud"],
                "business-entities": scoped_entities(d["business-entities"], scope),
            }

        add(
            "concern-match",
            normal + ("interaction-enrich", "business-crud", "business-entities"),
            static={"normal-documents": positive},
            build=concern_input,
            partition=True,
        )
        add(
            "enriched-view",
            ("interaction-enrich", "concern-match"),
            build=lambda d: d,
            transform=lambda d: with_concerns(d["interaction-enrich"], d["concern-match"]),
        )

        def generation_input(d):
            v = bind_resource_services({k: d[k] for k in normal if k != "object-operations"})
            v.update(basic_views(d["enriched-view"]))
            v["api-parameters"] = case_parameters(v, d["enriched-view"])
            return {
                **v,
                "enriched-interactions": actual_context(d["enriched-view"]),
                "concern-match": d["concern-match"],
                "registry": registry(),
            }

        if ex.config.get("scenario_patterns", False):
            from scene_completion.analysis.scenario_patterns import applicability, generated

            add(
                "pattern-applicability",
                tuple(k for k in normal if k != "object-operations")
                + ("enriched-view", "concern-match"),
                build=lambda d: {
                    "positive": generation_input(d),
                    "settings": analysis_settings(ex.pattern_settings),
                },
                transform=lambda d: applicability(d["positive"], d["settings"]),
            )
            add(
                "exception-generate",
                ("pattern-applicability",),
                build=lambda d: d,
                transform=lambda d: generated(d["pattern-applicability"]),
            )
        else:
            add(
                "exception-generate",
                tuple(k for k in normal if k != "object-operations")
                + ("enriched-view", "concern-match"),
                build=generation_input,
                partition=True,
            )

        add(
            "existing-bind",
            ("existing-branches", "fused-ssd", "normal-rules"),
            build=lambda d, g=group: {
                "branches": d["existing-branches"],
                "fused-ssd": d["fused-ssd"],
                "case-group": g,
                "registry": registry(),
                "normal-rules": d["normal-rules"],
            },
            partition=True,
        )
        add(
            "existing-concerns",
            (
                "existing-branches",
                "existing-bind",
                "fused-ssd",
                "api-parameters",
                "api-map",
                "normal-rules",
            ),
            build=lambda d, docs=scoped_rr + scoped_sr: {
                "existing-documents": docs,
                "registry": registry(),
                "branches": d["existing-branches"],
                "bindings": d["existing-bind"],
                "fused-ssd": d["fused-ssd"],
                "normal-constraints": case_parameters(d, d["fused-ssd"]),
                "normal-rules": d["normal-rules"],
            },
            partition=True,
        )
        from scene_completion.analysis.concern_alignment import attach_report, bind_scenarios
        from scene_completion.analysis.concern_alignment import compare as compare_concerns

        add(
            "concern-compare",
            ("concern-match", "existing-concerns"),
            build=lambda d: d,
            transform=lambda d: compare_concerns(d["concern-match"], d["existing-concerns"]),
        )
        add(
            "existing-extract",
            (
                "existing-branches",
                "existing-bind",
                "fused-ssd",
                "api-parameters",
                "api-map",
                "normal-rules",
                "existing-concerns",
            ),
            build=lambda d, docs=scoped_rr + scoped_sr: {
                "existing-documents": docs,
                "registry": registry(),
                "branches": d["existing-branches"],
                "bindings": d["existing-bind"],
                "fused-ssd": d["fused-ssd"],
                "normal-constraints": case_parameters(d, d["fused-ssd"]),
                "normal-rules": d["normal-rules"],
                "identified-concerns": d["existing-concerns"],
            },
            partition=True,
        )
        add(
            "gap-compare",
            ("exception-generate", "existing-extract"),
            build=lambda d: {
                "left": d["exception-generate"]["scenarios"],
                "right": d["existing-extract"]["scenarios"],
                "purpose": "G_E",
            },
        )
        add(
            "missing-report",
            (
                "exception-generate",
                "existing-extract",
                "gap-compare",
                "enriched-view",
                "concern-match",
                "existing-branches",
                "existing-bind",
                "normal-rules",
                "concern-compare",
            ),
            build=lambda d: d,
            transform=lambda d: {
                **missing_report(
                    d["exception-generate"]["scenarios"],
                    d["existing-extract"]["scenarios"],
                    d["gap-compare"]["decisions"],
                ),
                "interactions": d["enriched-view"],
                "concerns": d["concern-match"]["matches"],
                "concern_level": d["concern-compare"],
                "original_branches": [
                    b
                    for b in d["existing-branches"]["branches"]
                    if b["id"]
                    in {
                        v["branch_id"]
                        for v in d["existing-bind"]["bindings"]
                        if v["status"] != "not_this_case"
                    }
                ],
                "inverse_bindings": d["existing-bind"]["bindings"],
                "pending": d["normal-rules"]["pending"]
                + d["enriched-view"]["pending"]
                + d["concern-match"]["pending"]
                + d["exception-generate"]["pending"]
                + [
                    {
                        "interaction_id": b.get("interaction_id") or ("unbound:" + b["branch_id"]),
                        "reason": b["basis"],
                        "source_refs": b["source_refs"],
                    }
                    for b in d["existing-bind"]["bindings"]
                    if b["status"] == "pending"
                ],
            },
        )
        if ex.config.get("scenario_patterns", False):
            from scene_completion.analysis.recommendation import rank

            add(
                "gap-recommend",
                ("missing-report", "pattern-applicability"),
                build=lambda d, cid=cid: {
                    **d,
                    "settings": ex.pattern_settings,
                    "history": ex.recommendation_history,
                    "case_id": cid,
                    "run_id": ex.session_id,
                },
                transform=lambda d, cid=cid: rank(
                    d["missing-report"]["M"],
                    d["pattern-applicability"],
                    d["settings"],
                    d["history"],
                    case_id=d["case_id"],
                    run_id=d["run_id"],
                ),
            )
        add(
            "test-concerns",
            ("api-parameters", "api-map", "fused-ssd", "normal-rules", "test-scope"),
            build=lambda d, tt=abnormal_test, ti=test_input: {
                "test-documents": tt,
                "scope_units": [u for u in d["test-scope"]["units"] if u["scope"] == "interaction"],
                **ti,
                "normal-constraints": case_parameters(d, d["fused-ssd"]),
                "fused-ssd": d["fused-ssd"],
                "registry": registry(),
                "normal-rules": d["normal-rules"],
            },
            transform=(lambda d: {"matches": [], "pending": []}) if not abnormal_test else None,
            partition=bool(abnormal_test),
        )
        add(
            "test-ground-truth",
            (
                "api-parameters",
                "api-map",
                "fused-ssd",
                "normal-rules",
                "test-concerns",
                "test-scope",
            ),
            static={"tests": abnormal_test},
            build=lambda d, tt=abnormal_test, ti=test_input: {
                "test-documents": tt,
                "scope_units": [u for u in d["test-scope"]["units"] if u["scope"] == "interaction"],
                **ti,
                "normal-constraints": case_parameters(d, d["fused-ssd"]),
                "fused-ssd": d["fused-ssd"],
                "registry": registry(),
                "normal-rules": d["normal-rules"],
                "identified-concerns": d["test-concerns"],
            },
            transform=(lambda d: {"scenarios": [], "pending": []}) if not abnormal_test else None,
            partition=bool(abnormal_test),
        )
        for task, target in [("GT_G", "exception-generate"), ("GT_E", "existing-extract")]:
            # internal semantic comparison, not the public missing-report task
            a, b = "test-ground-truth", target
            ex.add(
                key(task),
                "semantic-compare",
                (key(a), key(b)),
                build=lambda d, a=key(a), b=key(b), task=task: {
                    "left": d[a]["scenarios"],
                    "right": d[b]["scenarios"],
                    "purpose": task,
                },
                case=cid,
            )
        if ex.config.get("supplement_tests", False):
            from scene_completion.analysis.test_supplement import (
                combine_truth,
                dedup_candidates,
                deduplicate_truth,
                positive_inputs,
                to_truth,
            )

            add(
                "test-supplement",
                ("fused-ssd", "api-parameters", "normal-rules"),
                build=lambda d, cat=test_records: positive_inputs(
                    d["fused-ssd"],
                    case_parameters(d, d["fused-ssd"]),
                    d["normal-rules"],
                    cat,
                    registry(),
                ),
                partition=True,
            )
            from scene_completion.analysis.concern_alignment import supplemental_concerns

            add(
                "test-additional-concerns",
                ("test-supplement", "fused-ssd", "api-parameters", "api-map"),
                build=lambda d: d,
                transform=lambda d: supplemental_concerns(
                    d["test-supplement"], d["fused-ssd"], case_parameters(d, d["fused-ssd"])
                ),
            )
            add(
                "test-additional-truth",
                (
                    "test-supplement",
                    "fused-ssd",
                    "test-additional-concerns",
                    "api-parameters",
                    "api-map",
                ),
                build=lambda d: d,
                transform=lambda d: bind_scenarios(
                    to_truth(d["test-supplement"], {"fused-ssd": d["fused-ssd"]}),
                    {
                        "fused-ssd": d["fused-ssd"],
                        "normal-constraints": case_parameters(d, d["fused-ssd"]),
                    },
                    d["test-additional-concerns"],
                    gate=True,
                ),
            )
            ex.add(
                key("GT_self"),
                "semantic-compare",
                (key("test-additional-truth"),),
                build=lambda d, a=key("test-additional-truth"): {
                    "left": dedup_candidates(d[a]),
                    "right": dedup_candidates(d[a]),
                    "purpose": "GT_self",
                },
                case=cid,
            )
            add(
                "test-additional-dedup",
                ("test-additional-truth", "GT_self"),
                build=lambda d: d,
                transform=lambda d: deduplicate_truth(
                    d["test-additional-truth"], d["GT_self"]["decisions"]
                ),
            )
            ex.add(
                key("GT_dedup"),
                "semantic-compare",
                (key("test-additional-dedup"), key("test-ground-truth")),
                build=lambda d, a=key("test-additional-dedup"), b=key("test-ground-truth"): {
                    "left": d[a]["scenarios"],
                    "right": d[b]["scenarios"],
                    "purpose": "GT_dedup",
                },
                case=cid,
            )
            add(
                "test-expanded",
                ("test-ground-truth", "test-additional-dedup", "GT_dedup"),
                build=lambda d: d,
                transform=lambda d: combine_truth(
                    d["test-ground-truth"], d["test-additional-dedup"], d["GT_dedup"]["decisions"]
                ),
            )
            for task, target in [
                ("GT_expanded_G", "exception-generate"),
                ("GT_expanded_E", "existing-extract"),
            ]:
                ex.add(
                    key(task),
                    "semantic-compare",
                    (key("test-expanded"), key(target)),
                    build=lambda d, a=key("test-expanded"), b=key(target), target=target: {
                        "left": d[a]["scenarios"],
                        "right": d[b]["scenarios"],
                        "purpose": "GT_G" if target == "exception-generate" else "GT_E",
                    },
                    case=cid,
                )
        concern_extra = (
            ("test-additional-concerns",) if ex.config.get("supplement_tests", False) else ()
        )

        def concern_evaluation(d):
            original = compare_concerns(
                d["concern-match"], d["existing-concerns"], d["test-concerns"]
            )
            expanded = {
                **d["test-concerns"],
                "matches": d["test-concerns"]["matches"]
                + d.get("test-additional-concerns", {}).get("matches", []),
            }
            value = (
                compare_concerns(d["concern-match"], d["existing-concerns"], expanded)
                if "test-additional-concerns" in d
                else original
            )
            return {**value, "original_evaluation": original}

        add(
            "concern-evaluation",
            ("concern-match", "existing-concerns", "test-concerns") + concern_extra,
            build=lambda d: d,
            transform=concern_evaluation,
        )
        if scoped_test or ex.config.get("supplement_tests", False):
            extra = (
                ("test-expanded", "GT_expanded_G", "GT_expanded_E")
                if ex.config.get("supplement_tests", False)
                else ()
            )
            from scene_completion.analysis.test_supplement import evaluate_test_sets

            if ex.config.get("scenario_patterns", False):
                extra = extra + ("gap-recommend",)
                from scene_completion.analysis.recommendation import (
                    evaluate as evaluate_recommendation,
                )

                base_evaluate = evaluate_test_sets

                def evaluate_test_sets(d):
                    report = base_evaluate(d)
                    report = evaluate_recommendation(report, d["gap-recommend"])
                    if "original_evaluation" in report:
                        report["original_evaluation"] = evaluate_recommendation(
                            report["original_evaluation"], d["gap-recommend"]
                        )
                    return report

            scene_evaluate = evaluate_test_sets

            def evaluate_two_levels(d, fn=scene_evaluate):
                return attach_report(
                    fn(d),
                    d["concern-evaluation"],
                    original=d["concern-evaluation"]["original_evaluation"],
                )

            add(
                "exception-evaluation",
                (
                    "exception-generate",
                    "existing-extract",
                    "test-ground-truth",
                    "gap-compare",
                    "GT_G",
                    "GT_E",
                    "concern-evaluation",
                )
                + extra,
                build=lambda d: d,
                transform=evaluate_two_levels,
            )
        for task in ("rr-ssd", "sr-ssd", "object-operations"):
            extraction_jobs.append((cid, task, key(task)))
    # Each checker reads only its own case, in parallel to positive modeling.
    branch_keys = tuple(cid + ":existing-branches" for cid in cases)
    ex.add(
        "existing-branches",
        "existing-branches",
        branch_keys,
        build=lambda d: d,
        transform=lambda d: {
            "branches": [
                {**b, "id": key + "::" + b["id"]}
                for key, part in d.items()
                for b in part["branches"]
            ]
        },
    )
    for cid, task, source in extraction_jobs:
        truth_key = task if cid == "shared" else cid + ":" + task
        gt = extraction_truth.get(truth_key)
        decisions = adjudications.get(truth_key)
        from scene_completion.analysis.evaluation import accuracy, not_evaluated

        ex.add(
            truth_key + ":accuracy",
            "extraction-evaluation",
            (source,),
            static={"truth": gt, "decisions": decisions},
            build=lambda d, source=source, gt=gt, ds=decisions: {
                "actual": d[source],
                "truth": gt,
                "decisions": ds,
            },
            transform=lambda d, task=task: (
                accuracy(task, d["actual"], d["truth"], d["decisions"])
                if d["truth"] is not None
                else not_evaluated(task)
            ),
            case=cid,
        )

    # Shared v5 views depend on validated per-case facts, but do not wait for
    # anomaly generation or evaluation. A failed use case remains isolated.
    from scene_completion.analysis.domain_model import exact_field_map, merge_rows, source_chunks

    crud_keys = tuple(cid + ":business-crud" for cid in cases)
    fused_keys = tuple(cid + ":fused-ssd" for cid in cases)
    data_keys = tuple(cid + ":data-dependencies" for cid in cases)

    def merge_crud(d):
        return merge_rows((d[k] for k in crud_keys), ("rows",))

    ex.add(
        "business-crud-project",
        "business-crud",
        crud_keys + fused_keys + ("business-entities",),
        build=lambda d: {
            **d,
            "business-entities": d["business-entities"],
            "fused-ssd": {
                "interactions": [row for key in fused_keys for row in d[key]["interactions"]]
            },
        },
        transform=merge_crud,
        verify_derivation=True,
    )
    ex.add(
        "data-dependencies-project",
        "data-dependencies",
        data_keys,
        build=lambda d: d,
        transform=lambda d: merge_rows(d.values(), ("entities", "relations", "flows")),
        verify_derivation=True,
    )
    ex.add(
        "business-attribute-map",
        "business-attribute-map",
        ("api-parameters", "business-entities", "business-crud-project"),
        build=lambda d: d,
        transform=lambda d: exact_field_map(
            d["api-parameters"],
            d["business-entities"]["entities"],
            d["business-crud-project"]["rows"],
            {
                g["id"]: g["rr_ids"]
                + g["sr_ids"]
                + [
                    c["name"]
                    for layer in ("RR", "SR")
                    for c in catalogue[layer]
                    if c["id"] in g["rr_ids"] + g["sr_ids"]
                ]
                for g in groups
            },
        ),
        verify_derivation=True,
    )

    positive_docs = normal_projection(rr) + normal_projection(sr) + normal_projection(ar or [])
    dependency_parts = []
    for n, document in enumerate(source_chunks(positive_docs, max_chars=7000)):
        key = "business-dependencies-part-" + str(n + 1).zfill(3)

        def dep_input(d, doc=document, groups=groups):
            # Identities and operations are enough to inspect a source slice;
            # attribute constraints are retrieved by the entity task later.
            mini = [
                {
                    "id": e["id"],
                    "name": e["name"],
                    "attributes": [],
                    "business_rules": [],
                    "source_refs": e["source_refs"],
                }
                for e in d["business-entities"]["entities"]
            ]
            text = "\n".join(line["text"] for line in doc["lines"]).casefold()
            source_lines = {line["number"] for line in doc["lines"]}
            entity_names = {e["id"]: e["name"].casefold() for e in mini}

            def in_slice(row):
                name = entity_names.get(row["entity_id"])
                if row["case_id"].casefold() in text or (name and name in text):
                    return True
                return any(
                    ref["source_id"] == doc["source_id"]
                    and any(ref["line_start"] <= line <= ref["line_end"] for line in source_lines)
                    for ref in row["source_refs"]
                )

            scoped = [row for row in d["business-crud-project"]["rows"] if in_slice(row)]
            return {
                "normal-documents": [doc],
                "business-entities": {"entities": mini, "pending": []},
                "business-crud": {"rows": scoped, "pending": []},
                "case-groups": {"groups": groups},
            }

        ex.add(
            key,
            "business-dependencies",
            ("business-entities", "business-crud-project"),
            build=dep_input,
        )
        ex.scheduler.tasks[key].display_label = "业务依赖 · 来源片段 " + str(n + 1)
        dependency_parts.append(key)
    ex.add(
        "business-dependencies",
        "business-dependencies",
        tuple(dependency_parts) + ("business-entities",),
        build=lambda d: d,
        transform=lambda d: merge_rows((d[k] for k in dependency_parts), ("dependencies",)),
        verify_derivation=True,
    )
    _schedule_global_analysis(ex, rr, sr, ar or [], tests)
