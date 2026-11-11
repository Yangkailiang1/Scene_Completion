"""Assemble the analysis DAG from formally validated supplied facts."""

from copy import deepcopy

from scene_completion.analysis.domain_model import merge_entities
from scene_completion.analysis.test_alignment import exact_alignment, known_catalogue
from scene_completion.analysis.validation import validate_result
from scene_completion.infrastructure.storage import fingerprint
from scene_completion.inputs.api_layers import qualify_mapping, scoped_parameters
from scene_completion.inputs.artifact_imports import selections
from scene_completion.inputs.http_interfaces import declarations
from scene_completion.inputs.source_documents import normal_projection
from scene_completion.inputs.structure_models import imported_sources
from scene_completion.inputs.supplied_cases import inspect_cases
from scene_completion.workflow.case_pipeline import _build_cases


def supplied_interfaces(root, rows, accepted):
    maps = selections(root, "api-map", frozen=rows)
    params = selections(root, "api-parameters", frozen=rows)
    calls = [
        i
        for entry in accepted.values()
        for i in entry["fused"]["interactions"]
        if i["layer"] == "SR" and i["direction"] == "request" and i["step_kind"] != "action"
    ]
    targets, documents, pending = {}, {}, []
    for item in maps:
        if item.get("source_layer") != "SR":
            continue
        for service in qualify_mapping(item["payload"], "SR")["services"]:
            for api in service["interfaces"]:
                if not any(
                    call["receiver"]["name"] == service["name"]
                    and (
                        call.get("api_id") in {api["id"], api["declared_id"]}
                        or (api["method"], api["address"])
                        in declarations(call["operation"]["name"])
                    )
                    for call in calls
                ):
                    continue
                ident = api["id"]
                if ident in targets and targets[ident][1] != api:
                    pending.append(ident + " 有多个已提供定义")
                    continue
                targets[ident] = (service, api)
                documents[ident] = item["document"]
    conflicts = {note.split(" ", 1)[0] for note in pending}
    for ident in conflicts:
        targets.pop(ident, None)
    services = {}
    index = []
    contracts = {}
    for ident, (owner, api) in targets.items():
        service = services.setdefault(
            owner["name"], {"name": owner["name"], "interfaces": [], "source_refs": []}
        )
        service["interfaces"].append(api)
        service["source_refs"] = list(
            {fingerprint(r): r for r in service["source_refs"] + api["source_refs"]}.values()
        )
        index.append(
            {
                "id": ident,
                "name": api["name"],
                "source_layer": "SR",
                "declared_id": api["declared_id"],
                "source_refs": api["source_refs"],
                "source_ranges": [
                    {"source_id": r["source_id"], "start": r["line_start"], "end": r["line_end"]}
                    for r in api["source_refs"]
                ],
            }
        )
        matches = [
            (a, item["document"])
            for item in params
            if item.get("source_layer") == "SR"
            for a in item["payload"]["apis"]
            if a.get("declared_id", a["id"]) in {api["declared_id"], ident}
            and (a.get("method"), a.get("address")) == (api["method"], api["address"])
        ]
        if not matches or len({fingerprint(a) for a, _ in matches}) != 1:
            pending.append(ident + " 缺少唯一的已提供参数契约")
            continue
        raw, doc = matches[0]
        contract = scoped_parameters(
            [{"apis": [{**raw, "id": ident, "declared_id": api["declared_id"]}]}], "SR"
        )["apis"][0]
        validate_result("api-parameters", {"apis": [contract]}, {"import-documents": [doc]})
        contracts[ident] = (contract, doc)
        if not any(r["kind"] == "success" for r in contract.get("responses", [])):
            pending.append(ident + " 未提供成功响应")
        if not any(r["kind"] == "error" for r in contract.get("responses", [])):
            pending.append(ident + " 未提供失败响应")
    if not targets:
        pending.append("当前用例未绑定已提供的 SR 接口契约")
    for call in calls:
        identifier = call.get("api_id")
        if identifier and not any(
            identifier in {a["id"], a["declared_id"]} for _, a in targets.values()
        ):
            pending.append(identifier + " 未绑定已提供的 SR 接口契约")
    return (
        {"services": list(services.values())},
        {"apis": index},
        contracts,
        documents,
        list(dict.fromkeys(pending)),
    )


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
    rr, sr = [structures["RR"]], [structures["SR"]]
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
    for layer, docs in (("RR", rr), ("SR", sr)):
        # Retain the complete supplied catalogue for source coverage, while the
        # actual case plan and test inventory use only the frozen selection.
        fact(
            layer.lower() + "-use-cases",
            "use-case-extract",
            {"cases": cases[layer]},
            normal_projection(docs),
            extra={"documents": normal_projection(docs), "layer": layer},
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
