"""Assemble the analysis DAG from formally validated supplied facts."""

from copy import deepcopy

from scene_completion.analysis.interactions.domain_model import merge_entities
from scene_completion.analysis.matching.test_alignment import exact_alignment, known_catalogue
from scene_completion.compat.detailed.case_pipeline import _build_cases
from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.documents.source_documents import normal_projection
from scene_completion.inputs.imports.artifact_imports import selections
from scene_completion.inputs.structured.structure_models import imported_sources
from scene_completion.inputs.structured.supplied_api import supplied_interfaces
from scene_completion.inputs.structured.supplied_cases import inspect_cases


def build_supplied(ex, tests, extraction_truth, adjudications):
    preview, cases, groups, accepted = inspect_cases(ex.import_snapshot, ex.case_ids)
    ex.manifest.update(
        supplied_case_scope=preview, evaluation_scope="SR", test_supplement_enabled=False
    )
    ex.evaluation_scope = "SR"
    if not accepted:
        raise ValueError("没有通过正式校验的已有 SSD 用例")
    reference_groups = groups
    groups = [g for g in groups if g["id"] in accepted]
    scope = {cid for g in groups for cid in g["rr_ids"] + g["sr_ids"]}
    structures = imported_sources(ex.import_snapshot)
    rr, sr = ([structures[layer]] if layer in structures else [] for layer in ("RR", "SR"))
    root = ex.root.parent

    def fact(key, task, value, sources=(), deps=(), *, case=None, extra=None):
        inputs = {"supplied": value, "import-documents": list(sources), **(extra or {})}
        ex.add(
            key,
            task,
            deps,
            static=inputs,
            build=lambda d: {**inputs, **d},
            transform=lambda d: deepcopy(d["supplied"]),
            skip_review=True,
            verify_derivation=True,
            case=case,
        )
        ex.scheduler.tasks[key].display_label = "已有文件输入 · " + key

    entity_parts = selections(root, "business-entities", frozen=ex.import_snapshot)
    entity_values = [p["payload"] for p in entity_parts]
    entity_docs = [p["document"] for p in entity_parts]
    fact("business-entities", "business-entities", merge_entities(entity_values), entity_docs)
    if not entity_parts:
        ex.manifest["supplied_entity_status"] = "未提供业务实体属性"
    # A common export may contain unrelated participants. Each case validates
    # against its own explicit identities and receives its own composition.
    all_components = {}
    documents = []
    for entry in accepted.values():
        documents.append(entry["row"]["behavior_product"]["normal_document"])
        for component in entry["components"]["components"]:
            name = component["name"]
            previous = all_components.setdefault(name, component)
            if previous["composition_type"] != component["composition_type"]:
                raise ValueError("已纳入用例的参与者类型冲突：" + name)
    fact(
        "components",
        "components",
        {"components": list(all_components.values()), "relations": []},
        documents,
    )
    mapping, index, contracts, api_docs, pending = supplied_interfaces(
        root, ex.import_snapshot, accepted
    )
    ex.manifest["supplied_sr_api_pending"] = pending
    fact("api-map", "api-map", mapping, api_docs.values())
    fact(
        "api-index",
        "api-index",
        index,
        api_docs.values(),
        ("api-map",),
        extra={"SR": list(api_docs.values())},
    )
    keys = []
    for ident, (api, doc) in contracts.items():
        key = "api-parameters-part-" + fingerprint(ident)[:12]
        fact(key, "api-parameters", {"apis": [api]}, [doc], ("api-index",))
        keys.append(key)
    fact(
        "api-parameters",
        "api-parameters",
        {"apis": [api for api, _ in contracts.values()]},
        [doc for _, doc in contracts.values()],
        tuple(keys) or ("api-index",),
    )

    for cid, entry in accepted.items():
        case_mapping, _, case_contracts, case_api_docs, _ = supplied_interfaces(
            root, ex.import_snapshot, {cid: entry}
        )
        fact(
            cid + ":components",
            "components",
            entry["components"],
            [entry["row"]["behavior_product"]["normal_document"]],
            case=cid,
        )
        fact(cid + ":api-map", "api-map", case_mapping, case_api_docs.values(), case=cid)
        fact(
            cid + ":api-parameters",
            "api-parameters",
            {"apis": [api for api, _ in case_contracts.values()]},
            [doc for _, doc in case_contracts.values()],
            case=cid,
        )

    catalogue = {
        layer: [c for c in entries if c["id"] in scope] for layer, entries in cases.items()
    }
    # All catalogue entries are validated, including unselected SysOperation files.
    catalogue_sources = {}
    for row in ex.import_snapshot:
        product = row.get("behavior_product") or {}
        if product.get("kind") == "system_operations":
            doc = product["normal_document"]
            catalogue_sources[doc["source_id"]] = doc
    for layer, docs in (("RR", rr), ("SR", sr)):
        used = {span["source_id"] for c in cases[layer] for span in c["source_ranges"]}
        docs = normal_projection(docs + [d for sid, d in catalogue_sources.items() if sid in used])
        # Retain the complete supplied catalogue for source coverage, while the
        # actual case plan and test inventory use only the frozen selection.
        fact(
            layer.lower() + "-use-cases",
            "use-case-extract",
            {"cases": cases[layer]},
            docs,
            extra={"documents": docs, "layer": layer},
        )
    full_groups = list(reference_groups)
    paired_ids = {case_id for g in full_groups for case_id in g["rr_ids"] + g["sr_ids"]}
    for layer, entries in cases.items():
        for c in entries:
            if c["id"] not in paired_ids:
                full_groups.append(
                    {
                        "id": "unpaired-" + fingerprint([layer, c["id"]])[:20],
                        "rr_ids": [c["id"]] if layer == "RR" else [],
                        "sr_ids": [c["id"]] if layer == "SR" else [],
                        "status": "pending",
                        "reason": "结构化目录没有唯一的跨层名称对应",
                        "source_refs": c["source_refs"],
                    }
                )
    fact(
        "use-case-align",
        "use-case-align",
        {"groups": full_groups},
        deps=("rr-use-cases", "sr-use-cases"),
        extra={"rr-cases": {"cases": cases["RR"]}, "sr-cases": {"cases": cases["SR"]}},
    )

    test_catalogue = known_catalogue(tests)
    if test_catalogue is None:
        test_catalogue = {"cases": [], "tests": [], "pending": []}
        ex.manifest["supplied_test_status"] = "测试文件无法直接建立目录，等待结构化测试"
    alignments = []
    for case in test_catalogue["cases"]:
        match = exact_alignment(
            {
                "test-inventory": {"cases": [case]},
                "case-groups": {"groups": groups},
                "rr-cases": {"cases": catalogue["RR"]},
                "sr-cases": {"cases": catalogue["SR"]},
            }
        )
        if not match:
            candidates = [
                g
                for g in groups
                if any(
                    c["name"] == case["name"] and c["id"] in g["rr_ids"] + g["sr_ids"]
                    for entries in catalogue.values()
                    for c in entries
                )
            ]
            if len(candidates) == 1:
                match = {
                    "matches": [
                        {
                            "test_case_id": case["id"],
                            "case_group_id": candidates[0]["id"],
                            "status": "confirmed",
                            "basis": "测试用例名与已确认需求用例名唯一一致",
                            "source_refs": case["source_refs"],
                        }
                    ]
                }
        if match:
            alignments.extend(match["matches"])
    if test_catalogue["tests"] or not tests:
        fact(
            "test-inventory",
            "test-inventory",
            test_catalogue,
            tests,
            extra={"test-documents": tests},
        )
        known_ids = {a["test_case_id"] for a in alignments}
        full_test_alignments = alignments + [
            {
                "test_case_id": c["id"],
                "case_group_id": None,
                "status": "unmatched",
                "basis": "本轮未选择此用例或测试无法唯一对应",
                "source_refs": c["source_refs"],
            }
            for c in test_catalogue["cases"]
            if c["id"] not in known_ids
        ]
        fact(
            "test-case-align",
            "test-case-align",
            {"matches": full_test_alignments},
            tests,
            ("test-inventory",),
            extra={"case-groups": {"groups": groups}},
        )
    test_scope = {r["test_case_id"] for r in alignments if r["status"] == "confirmed"}
    selected_tests = {
        "cases": [c for c in test_catalogue["cases"] if c["id"] in test_scope],
        "tests": [t for t in test_catalogue["tests"] if t["case_id"] in test_scope],
        "pending": [],
    }
    ex.manifest.update(
        case_correspondence=groups,
        test_case_correspondence=alignments,
        supplied_unaligned_test_cases=len(test_catalogue["cases"]) - len(test_scope),
    )
    ex.scheduler.priority_cases = [g["id"] for g in groups]
    _build_cases(
        ex,
        rr,
        sr,
        tests,
        catalogue,
        groups,
        extraction_truth,
        adjudications,
        selected_tests,
        {"matches": alignments},
        supplied=accepted,
        reference_groups=reference_groups,
    )
