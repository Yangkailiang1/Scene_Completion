"""Planning for the current workflow."""

from scene_completion.infrastructure.storage import fingerprint, read_json
from scene_completion.inputs.documents.source_documents import documents_in, normal_projection
from scene_completion.workflow.case_dispatch import _build_cases
from scene_completion.workflow.support import payload


def build_pipeline(ex, rr, sr, tests, extraction_truth=None, adjudications=None, ar=None):
    from scene_completion.workflow.ssd_pipeline import build_structured, enabled, input_directory

    if enabled(ex):
        directory = input_directory(ex)
        if directory is not None and build_structured(ex, directory):
            return
    ex.manifest.update(
        test_policy="exception-only-v1",
        test_source_hash=fingerprint(tests),
        test_supplement_enabled=bool(ex.config.get("supplement_tests", False)),
    )
    if (ex.root.parent / "project.json").exists():
        project = read_json(ex.root.parent / "project.json")
        ex.manifest["test_source_version"] = project.get(
            "test_source_version", fingerprint(project["sources"]["test"])[:20]
        )
        from scene_completion.analysis.evaluation.evaluation_scope import validate_scope

        ex.evaluation_scope = validate_scope(project.get("evaluation_scope", "all"))
        ex.manifest["evaluation_scope"] = ex.evaluation_scope
    if getattr(ex, "supplied_only", False) and not enabled(ex):
        from scene_completion.compat.detailed.supplied_pipeline import build_supplied

        return build_supplied(ex, tests, extraction_truth or {}, adjudications or {})
    from scene_completion.inputs.documents.source_documents import (
        current_projection,
    )

    extraction_truth = extraction_truth or {}
    adjudications = adjudications or {}
    from scene_completion.inputs.provenance.indexed_context import (
        catalogue_context,
        markdown_index,
        task_document_view,
    )
    from scene_completion.inputs.structured.structure_models import imported_sources, model_layer

    imported_structure = imported_sources(ex.import_snapshot)
    if "RR" in imported_structure:
        rr = [d for d in rr if model_layer(d) != "RR"] + [imported_structure["RR"]]
    if "SR" in imported_structure:
        sr = [d for d in sr if model_layer(d) != "SR"] + [imported_structure["SR"]]
    ar = current_projection(ar or [])
    ex.add(
        "source-index",
        "source-index",
        static={"documents": rr + sr + ar},
        transform=lambda d: markdown_index(d["documents"]),
        verify_derivation=True,
    )
    rr = current_projection(rr)
    sr = current_projection(sr)

    def shared_positive(docs, layer):
        imported = imported_structure.get(layer, {}).get("source_id")
        primary = [d for d in docs if d["source_id"] != imported]
        return normal_projection(primary or docs)

    normal_rr = shared_positive(rr, "RR")
    normal_sr = shared_positive(sr, "SR")
    normal_ar = normal_projection(ar)
    from scene_completion.analysis.interactions.domain_model import merge_entities, source_chunks
    from scene_completion.inputs.imports.artifact_imports import selections
    from scene_completion.inputs.structured.colleague_formats import uncovered_entity_documents
    from scene_completion.inputs.structured.external_interfaces import index as external_index
    from scene_completion.inputs.structured.external_interfaces import mapping_view

    imported_entities = selections(ex.root.parent, "business-entities", frozen=ex.import_snapshot)
    entity_parts = []
    if imported_entities:
        ex.add(
            "business-entities-imports",
            "business-entities",
            static={"normal-documents": [p["document"] for p in imported_entities]},
            transform=lambda d: merge_entities([p["payload"] for p in imported_entities]),
            verify_derivation=True,
        )
        ex.scheduler.tasks[
            "business-entities-imports"
        ].display_label = "业务实体与属性 · 同事已声明部分"
        entity_parts.append("business-entities-imports")
    for n, document in enumerate(
        source_chunks(
            uncovered_entity_documents(normal_rr + normal_sr + normal_ar, imported_entities)
        )
    ):
        key = "business-entities-part-" + str(n + 1).zfill(3)
        ex.add(key, "business-entities", static={"normal-documents": [document]})
        ex.scheduler.tasks[key].display_label = "业务实体与属性 · 来源片段 " + str(n + 1)
        entity_parts.append(key)
    ex.add(
        "business-entities",
        "business-entities",
        tuple(entity_parts),
        build=lambda d: d,
        transform=lambda d: merge_entities(d[k] for k in entity_parts),
        verify_derivation=not bool(imported_entities),
    )
    ex.add(
        "components-context",
        "document-context",
        ("source-index",),
        static={"RR": normal_rr, "SR": normal_sr},
        transform=lambda d: {
            role: task_document_view(docs, "components") for role, docs in d.items()
        },
        verify_derivation=True,
    )
    ex.add(
        "components", "components", ("components-context",), build=lambda d: d["components-context"]
    )
    from scene_completion.inputs.documents.api_documents import (
        index_interfaces,
        response_contract_documents,
    )
    from scene_completion.inputs.imports.artifact_imports import selections
    from scene_completion.inputs.structured.api_layers import (
        merge_mappings,
        qualify_index,
        qualify_mapping,
        scoped_api_document,
        scoped_parameters,
    )

    imported_api_docs = {
        layer: documents_in(
            [
                scoped_api_document(a["document"], layer)
                for t in ("api-map", "api-parameters")
                for a in selections(ex.root.parent, t, frozen=ex.import_snapshot)
                if (a.get("source_layer") or "SR") == layer
            ]
        )
        for layer in ("RR", "SR")
    }
    api_documents = {
        "RR": normal_rr + imported_api_docs["RR"],
        "SR": normal_sr + imported_api_docs["SR"],
    }
    raw_documents = {"RR": rr + imported_api_docs["RR"], "SR": sr + imported_api_docs["SR"]}
    import re

    from scene_completion.inputs.structured.api_boundaries import (
        external_services,
        has_declarations,
        partition_documents,
        scope_inputs,
    )

    for layer, boundary in [
        (layer, boundary) for layer in ("RR", "SR") for boundary in ("system", "external")
    ]:
        docs = api_documents[layer]
        prefix = layer.lower() + ("-external-api-" if boundary == "external" else "-api-")
        context_key = prefix + "context"
        map_key = prefix + "map"
        ex.add(
            context_key,
            "document-context",
            ("source-index", "components"),
            build=lambda d, docs=docs, layer=layer, boundary=boundary: scope_inputs(
                docs, d["components"], layer, boundary
            ),
            transform=mapping_view
            if boundary == "external"
            else lambda d: {
                key: task_document_view(values, "api-map") if key in {"RR", "SR"} else values
                for key, values in d.items()
            },
            verify_derivation=True,
        )
        label = "外部Service" if boundary == "external" else "系统及内部Service"
        ex.scheduler.tasks[context_key].display_label = layer + label + "接口定义取片（工具）"
        has_rr_api = has_declarations(docs)
        ex.add(
            map_key,
            "api-map",
            (context_key,),
            build=lambda d, k=context_key: d[k],
            transform=(lambda d: {"services": []})
            if not has_rr_api and layer == "RR" and boundary == "system"
            else None,
            api_scope={"source_layer": layer, "boundary": boundary},
        )
        ex.scheduler.tasks[map_key].display_label = layer + label + "接口映射"
        index_key = prefix + "index"
        ex.add(
            index_key,
            "api-index",
            (map_key, "components"),
            build=lambda d, k=map_key, layer=layer, docs=docs, boundary=boundary: {
                **(
                    scope_inputs(docs, d["components"], layer, boundary)
                    if boundary == "external"
                    else {
                        layer: partition_documents(
                            docs, external_services(d["components"]), boundary
                        )
                    }
                ),
                "api-map": d[k],
            },
            transform=index_interfaces,
            verify_derivation=True,
        )
        ex.scheduler.tasks[index_key].display_label = layer + "接口参数目录（工具）"
    ex.add(
        "external-api-map",
        "api-map",
        ("rr-external-api-map", "sr-external-api-map"),
        build=lambda d: d,
        transform=lambda d: {
            "services": [
                service
                for layer in ("RR", "SR")
                for service in qualify_mapping(
                    d[layer.lower() + "-external-api-map"], layer, "external"
                )["services"]
            ]
        },
        skip_review=True,
        verify_derivation=True,
    )
    ex.scheduler.tasks["external-api-map"].display_label = "外部Service接口映射汇总（RR/SR来源）"
    ex.add(
        "external-api-index",
        "api-index",
        ("rr-external-api-index", "sr-external-api-index"),
        build=lambda d: {**d, "RR": api_documents["RR"], "SR": api_documents["SR"]},
        transform=lambda d: {
            "apis": [
                api
                for layer in ("RR", "SR")
                for api in qualify_index(
                    d[layer.lower() + "-external-api-index"], layer, "external"
                )["apis"]
            ]
        },
        skip_review=True,
        verify_derivation=True,
    )
    ex.scheduler.tasks["external-api-index"].display_label = "外部Service接口参数目录（工具）"
    ex.add(
        "api-map",
        "api-map",
        ("rr-api-map", "sr-api-map", "external-api-map"),
        build=lambda d: d,
        transform=lambda d: {
            "services": merge_mappings([("RR", d["rr-api-map"]), ("SR", d["sr-api-map"])])[
                "services"
            ]
            + d["external-api-map"]["services"]
        },
        skip_review=True,
        verify_derivation=True,
    )
    ex.add(
        "api-index",
        "api-index",
        ("rr-api-index", "sr-api-index", "external-api-index", "api-map"),
        build=lambda d: {**d, "RR": api_documents["RR"], "SR": api_documents["SR"]},
        transform=lambda d: {
            "apis": qualify_index(d["rr-api-index"], "RR")["apis"]
            + qualify_index(d["sr-api-index"], "SR")["apis"]
            + d["external-api-index"]["apis"]
        },
        verify_derivation=True,
    )

    def expand_api():
        record = ex.scheduler.state["tasks"].get("api-index", {})
        if record.get("status") != "passed":
            ex.add(
                "api-parameters", "api-parameters", ("api-index",), transform=lambda d: {"apis": []}
            )
            return
        index = payload(read_json(ex.root / record["output_file"]))["apis"]
        keys = {"RR": [], "SR": []}
        external_keys = []
        mapped = payload(read_json(ex.root / ex.scheduler.state["tasks"]["api-map"]["output_file"]))
        from scene_completion.inputs.structured.api_identity import mapping_lookup

        interfaces = mapping_lookup(mapped, {"apis": index})
        services = [
            {"name": service["name"], "source_refs": service["source_refs"]}
            for service in mapped["services"]
            if any(a.get("interface_scope") == "external" for a in service["interfaces"])
        ]
        contract_docs = {
            (layer, boundary): partition_documents(docs, services, boundary)
            for layer, docs in api_documents.items()
            for boundary in ("system", "external")
        }
        response_docs = {
            (layer, boundary): response_contract_documents(
                partition_documents(docs, services, boundary)
            )
            for layer, docs in raw_documents.items()
            for boundary in ("system", "external")
        }
        full_indexes = {}
        for layer, boundary in contract_docs:
            raw_mapping = {
                "services": [
                    {
                        **s,
                        "interfaces": [
                            a
                            for a in s["interfaces"]
                            if a["source_layer"] == layer
                            and a.get("interface_scope", "system") == boundary
                        ],
                    }
                    for s in mapped["services"]
                ]
            }
            full_indexes[(layer, boundary)] = (
                {
                    a["id"]: a
                    for a in (
                        external_index(
                            raw_mapping,
                            {
                                layer: partition_documents(
                                    raw_documents[layer], services, boundary
                                ),
                                "interface-scope": {
                                    "boundary": boundary,
                                    "external_services": services,
                                },
                            },
                            require_complete=False,
                        )
                        if boundary == "external"
                        else index_interfaces(
                            {
                                layer: partition_documents(
                                    raw_documents[layer], services, boundary
                                ),
                                "api-map": raw_mapping,
                            }
                        )
                    )["apis"]
                }
                if response_docs[(layer, boundary)]
                else {}
            )
        for entry in index:
            layer = entry["source_layer"]
            boundary = entry.get("interface_scope", "system")
            key = "api-parameters-part-" + fingerprint(entry["id"])[:12]
            docs = []
            for doc in contract_docs[(layer, boundary)]:
                ranges = [r for r in entry["source_ranges"] if r["source_id"] == doc["source_id"]]
                lines = [
                    r
                    for r in doc["lines"]
                    if any(span["start"] <= r["number"] <= span["end"] for span in ranges)
                ]
                if lines:
                    docs.append({**doc, "lines": lines})
            if not docs:
                raise ValueError("API index has no valid source range")
            interface = {**interfaces[entry["id"]]}
            source_text = "\n".join(r["text"] for doc in docs for r in doc["lines"])
            if re.search(
                r"(发送|发起|调用).{0,40}\b(GET|POST|PUT|PATCH|DELETE)\s+/", source_text
            ) and not re.search(
                r"请求参数|请求头|路径参数|查询参数|数据类型|参数名称|必填|可选|枚举", source_text
            ):
                interface["source_role"] = "invocation_only"
            error_docs = []
            spans = full_indexes[(layer, boundary)].get(entry["id"], {}).get("source_ranges", [])
            for doc in response_docs[(layer, boundary)]:
                lines = [
                    r
                    for r in doc["lines"]
                    if any(
                        span["source_id"] == doc["source_id"]
                        and span["start"] <= r["number"] <= span["end"]
                        for span in spans
                    )
                ]
                if lines:
                    error_docs.append({**doc, "lines": lines})
            ex.add(
                key,
                "api-parameters",
                ("api-index", "api-map"),
                build=lambda d, docs=docs, interface=interface, error_docs=error_docs, layer=layer: {
                    layer: docs,
                    "interface": interface,
                    **({"response-documents": error_docs} if error_docs else {}),
                },
                api_scope=interface,
            )
            is_external = entry.get("interface_scope") == "external"
            ex.scheduler.tasks[key].display_label = (
                layer + ("外部Service" if is_external else "") + "接口参数 · " + entry["name"]
            )
            (external_keys if is_external else keys[layer]).append(key)
        for layer in ("RR", "SR"):
            child = layer.lower() + "-api-parameters"
            ex.add(
                child,
                "api-parameters",
                tuple(keys[layer]) or ("api-index",),
                build=lambda d: d,
                transform=lambda d, layer=layer, parts=tuple(keys[layer]): scoped_parameters(
                    [d[k] for k in parts], layer
                ),
                skip_review=True,
                verify_derivation=True,
            )
            ex.scheduler.tasks[child].display_label = layer + "接口参数与响应分支汇总"
        ex.add(
            "external-api-parameters",
            "api-parameters",
            tuple(external_keys) or ("external-api-index",),
            build=lambda d: d,
            transform=lambda d, parts=tuple(external_keys): {
                "apis": [api for k in parts for api in d[k]["apis"]]
            },
            skip_review=True,
            verify_derivation=True,
        )
        ex.scheduler.tasks["external-api-parameters"].display_label = "外部Service完整接口契约汇总"
        ex.add(
            "api-parameters",
            "api-parameters",
            ("rr-api-parameters", "sr-api-parameters", "external-api-parameters"),
            build=lambda d: d,
            transform=lambda d: {
                "apis": d["rr-api-parameters"]["apis"]
                + d["sr-api-parameters"]["apis"]
                + d["external-api-parameters"]["apis"]
            },
            skip_review=True,
            verify_derivation=True,
        )

    ex.expand_api = expand_api
    for layer, docs in [("RR", normal_rr), ("SR", normal_sr)]:
        # The imported catalogue is authoritative for this extraction only.
        # Keep other positive specs for shared contracts/entity extraction.
        structured_docs = (
            normal_projection([imported_structure[layer]])
            if layer in imported_structure
            else [doc for doc in docs if model_layer(doc) == layer]
        )
        catalogue_docs = structured_docs or docs
        k = layer.lower() + "-catalogue-context"
        ex.add(
            k,
            "document-context",
            ("source-index",),
            static={"documents": docs},
            build=lambda d, docs=docs: {"documents": docs, "index": d["source-index"]},
            transform=lambda d: catalogue_context(d["documents"], d["index"]),
            verify_derivation=True,
        )
        ex.scheduler.tasks[k].display_label = layer + "用例元数据取片（工具）"
        ex.add(
            layer.lower() + "-use-cases",
            "use-case-extract",
            (k,),
            build=lambda d, k=k, layer=layer, docs=catalogue_docs: (
                {"documents": docs, "layer": layer}
                if docs and all(model_layer(doc) == layer for doc in docs)
                else {**d[k], "layer": layer}
            ),
        )
    if not enabled(ex) and not ex.config.get("scenario_patterns", False):
        ex.add(
            "gap-recommend",
            "gap-recommend",
            transform=lambda d: {"enabled": False, "status": "未启用"},
        )
    ex.add(
        "use-case-align",
        "use-case-align",
        ("rr-use-cases", "sr-use-cases"),
        build=lambda d: {"rr-cases": d["rr-use-cases"], "sr-cases": d["sr-use-cases"]},
    )
    ex.add("test-inventory", "test-inventory", static={"test-documents": tests})
    ex.add(
        "test-case-align",
        "test-case-align",
        ("test-inventory", "rr-use-cases", "sr-use-cases", "use-case-align"),
        build=lambda d: __import__(
            "scene_completion.analysis.matching.test_alignment", fromlist=["alignment_context"]
        ).alignment_context(
            {
                "test-inventory": {**d["test-inventory"], "tests": []},
                "rr-cases": d["rr-use-cases"],
                "sr-cases": d["sr-use-cases"],
                "case-groups": d["use-case-align"],
            }
        ),
    )

    def expand():
        state = ex.scheduler.state["tasks"]

        def get(key):
            return payload(read_json(ex.root / state[key]["output_file"]))

        catalogue = {"RR": get("rr-use-cases")["cases"], "SR": get("sr-use-cases")["cases"]}
        groups = get("use-case-align")["groups"]
        if ex.case_ids:
            groups = [
                g
                for g in groups
                if g["id"] in ex.case_ids or set(ex.case_ids) & set(g["rr_ids"] + g["sr_ids"])
            ]
            if not groups:
                raise ValueError("指定用例范围没有对应组，请使用用例目录中的RR/SR编号或组ID")
        priorities = ex.config.get("priority_cases", [])
        if any(
            not any(p == g["id"] or p in g["rr_ids"] + g["sr_ids"] for g in groups)
            for p in priorities
        ):
            raise ValueError("优先用例不在当前确认范围，请使用组ID或RR/SR原编号")
        groups.sort(
            key=lambda g: next(
                (
                    n
                    for n, p in enumerate(priorities)
                    if p == g["id"] or p in g["rr_ids"] + g["sr_ids"]
                ),
                len(priorities),
            )
        )
        ex.scheduler.priority_cases = [g["id"] for g in groups if g["status"] == "confirmed"]
        ex.manifest["case_correspondence"] = groups
        test_catalogue = get("test-inventory")
        test_alignment = get("test-case-align")
        ex.manifest["test_case_correspondence"] = test_alignment["matches"]
        ex.manifest["test_import_pending_count"] = len(test_catalogue.get("pending", []))
        _build_cases(
            ex,
            rr,
            sr,
            tests,
            catalogue,
            groups,
            extraction_truth,
            adjudications,
            test_catalogue,
            test_alignment,
            ar,
        )

    ex.expand_pipeline = expand
