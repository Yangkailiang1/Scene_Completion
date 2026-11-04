"""Planning for the current workflow."""

from scene_completion.infrastructure.storage import fingerprint, read_json
from scene_completion.inputs.source_documents import documents_in, normal_projection
from scene_completion.workflow.case_pipeline import _build_cases
from scene_completion.workflow.support import payload


def build_pipeline(ex, rr, sr, tests, extraction_truth=None, adjudications=None, ar=None):
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
        from scene_completion.analysis.evaluation_scope import validate_scope

        ex.evaluation_scope = validate_scope(project.get("evaluation_scope", "all"))
        ex.manifest["evaluation_scope"] = ex.evaluation_scope
    from scene_completion.inputs.source_documents import (
        current_projection,
    )

    extraction_truth = extraction_truth or {}
    adjudications = adjudications or {}
    from scene_completion.inputs.indexed_context import (
        catalogue_context,
        markdown_index,
        task_document_view,
    )
    from scene_completion.inputs.structure_models import imported_sources, model_layer

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
    from scene_completion.analysis.domain_model import merge_entities, source_chunks
    from scene_completion.inputs.artifact_imports import selections
    from scene_completion.inputs.colleague_formats import uncovered_entity_documents

    imported_entities = selections(ex.root.parent, "business-entities", frozen=ex.import_snapshot)
    entity_parts = []
    if imported_entities:
        ex.add(
            "business-entities-imports",
            "business-entities",
            static={"normal-documents": [p["document"] for p in imported_entities]},
            transform=lambda d: merge_entities([p["payload"] for p in imported_entities]),
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
    )
    ex.add(
        "components-context",
        "document-context",
        ("source-index",),
        static={"RR": normal_rr, "SR": normal_sr},
        transform=lambda d: {
            role: task_document_view(docs, "components") for role, docs in d.items()
        },
    )
    ex.add(
        "components", "components", ("components-context",), build=lambda d: d["components-context"]
    )
    from scene_completion.inputs.api_documents import index_interfaces, response_contract_documents
    from scene_completion.inputs.api_layers import (
        merge_mappings,
        qualify_index,
        scoped_api_document,
        scoped_parameters,
    )
    from scene_completion.inputs.artifact_imports import selections

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

    for layer, docs in api_documents.items():
        prefix = layer.lower() + "-api-"
        context_key = prefix + "context"
        map_key = prefix + "map"
        ex.add(
            context_key,
            "document-context",
            ("source-index",),
            static={layer: docs},
            transform=lambda d: {
                role: task_document_view(values, "api-map") for role, values in d.items()
            },
        )
        ex.scheduler.tasks[context_key].display_label = layer + "接口定义取片（工具）"
        has_rr_api = any(
            re.search(
                r"API[-–—][A-Za-z0-9]|\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/",
                r["text"],
                re.I,
            )
            for d in docs
            for r in d["lines"]
        )
        ex.add(
            map_key,
            "api-map",
            (context_key,),
            build=lambda d, k=context_key: d[k],
            transform=(lambda d: {"services": []}) if layer == "RR" and not has_rr_api else None,
            api_scope={"source_layer": layer},
        )
        ex.scheduler.tasks[map_key].display_label = layer + (
            "对外接口映射" if layer == "RR" else "内部接口映射"
        )
        index_key = prefix + "index"
        ex.add(
            index_key,
            "api-index",
            (map_key,),
            build=lambda d, k=map_key, layer=layer, docs=docs: {layer: docs, "api-map": d[k]},
            transform=index_interfaces,
        )
        ex.scheduler.tasks[index_key].display_label = layer + "接口参数目录（工具）"
    ex.add(
        "api-map",
        "api-map",
        ("rr-api-map", "sr-api-map"),
        build=lambda d: d,
        transform=lambda d: merge_mappings([("RR", d["rr-api-map"]), ("SR", d["sr-api-map"])]),
        skip_review=True,
    )
    ex.add(
        "api-index",
        "api-index",
        ("rr-api-index", "sr-api-index"),
        build=lambda d: {**d, "RR": api_documents["RR"], "SR": api_documents["SR"]},
        transform=lambda d: {
            "apis": qualify_index(d["rr-api-index"], "RR")["apis"]
            + qualify_index(d["sr-api-index"], "SR")["apis"]
        },
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
        mapped = payload(read_json(ex.root / ex.scheduler.state["tasks"]["api-map"]["output_file"]))
        interfaces = {i["id"]: i for service in mapped["services"] for i in service["interfaces"]}
        response_docs = {
            layer: response_contract_documents(docs) for layer, docs in raw_documents.items()
        }
        full_indexes = {}
        for layer in ("RR", "SR"):
            raw_mapping = payload(
                read_json(
                    ex.root / ex.scheduler.state["tasks"][layer.lower() + "-api-map"]["output_file"]
                )
            )
            full_indexes[layer] = (
                {
                    a["id"]: a
                    for a in index_interfaces(
                        {layer: raw_documents[layer], "api-map": raw_mapping}
                    )["apis"]
                }
                if response_docs[layer]
                else {}
            )
        for entry in index:
            layer = entry["source_layer"]
            key = "api-parameters-part-" + fingerprint(entry["id"])[:12]
            docs = []
            for doc in api_documents[layer]:
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
            spans = full_indexes[layer].get(entry["declared_id"], {}).get("source_ranges", [])
            for doc in response_docs[layer]:
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
            ex.scheduler.tasks[key].display_label = layer + "接口参数 · " + entry["name"]
            keys[layer].append(key)
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
            )
            ex.scheduler.tasks[child].display_label = layer + "接口参数与响应分支汇总"
        ex.add(
            "api-parameters",
            "api-parameters",
            ("rr-api-parameters", "sr-api-parameters"),
            build=lambda d: d,
            transform=lambda d: {
                "apis": d["rr-api-parameters"]["apis"] + d["sr-api-parameters"]["apis"]
            },
            skip_review=True,
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
    if not ex.config.get("scenario_patterns", False):
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
            "scene_completion.analysis.test_alignment", fromlist=["alignment_context"]
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
