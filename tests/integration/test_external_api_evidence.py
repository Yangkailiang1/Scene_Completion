"""External HTTP calls and the two citation transports share the same proof."""

import json
from copy import deepcopy

import pytest

from scene_completion.analysis.validation import validate_result
from scene_completion.domain.contracts import packet
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.inputs.provenance.indexed_context import EvidenceContext, task_document_view
from scene_completion.inputs.provenance.reference_contract import (
    ReferenceContractError,
    validate_raw_references,
)
from scene_completion.inputs.structured.http_interfaces import (
    complete_explicit_calls,
    mapping_declarations,
)
from scene_completion.models.clients.deepagents_client import task_message
from scene_completion.workflow.runtime.scheduler import TaskRejected
from tests.support.external_api_evidence import api_packet, client, document, external_scope


def test_large_api_slice_keeps_mermaid_participants_and_literal_external_calls():
    original = document()
    view = task_document_view([original], "api-map")[0]
    assert 2 not in {r["number"] for r in view["lines"]}
    calls = mapping_declarations([view])
    assert len(calls) == 4
    assert calls[1]["receiver"] == "CloudMapService"
    assert calls[3]["receiver"] == "ExternalDatabase"
    assert calls[1]["source_refs"][0]["line_start"] == 10
    assert calls[1]["source_refs"][1]["quote"] == "participant C as CloudMapService"
    assert original == document()


@pytest.mark.parametrize("layer", ["RR", "SR"])
def test_literal_external_calls_complete_mapping_with_stable_ids_and_scoped_parameters(layer):
    inputs = api_packet(layer)["input"]
    result, notes = complete_explicit_calls({"services": []}, inputs[layer])
    validate_result("api-map", result, inputs)
    assert {s["name"] for s in result["services"]} == {
        "AdminService",
        "CloudMapService",
        "ExternalDatabase",
    }
    assert len(notes) == 4
    again, extra = complete_explicit_calls(result, inputs[layer])
    assert again == result and extra == []
    assert all(
        a["id"].startswith("local-http-") for s in result["services"] for a in s["interfaces"]
    )
    assert all("parameters" not in a for s in result["services"] for a in s["interfaces"])
    assert "method" not in inputs[layer][0]["lines"][0]  # no document rewrite


def test_unknown_ownership_still_requires_mapping_and_incomplete_paths_are_not_invented():
    d = document()
    d["lines"] = [
        {"number": 1, "text": "POST /literal/path"},
        {"number": 2, "text": "P->>C: DELETE /broken/{id"},
    ]
    result, notes = complete_explicit_calls({"services": []}, [d])
    assert result == {"services": []} and notes == []
    with pytest.raises(ValueError, match="omitted explicit"):
        validate_result("api-map", result, {"SR": [d]})


@pytest.mark.parametrize("indexed", [False, True])
def test_model_omission_is_repaired_from_literal_calls_and_validated_in_both_transports(
    tmp_path, indexed
):
    sent = []

    def transport(url, key, body, timeout, retries):
        sent.append(body)
        return {"choices": [{"message": {"content": '{"services":[]}'}, "finish_reason": "stop"}]}

    p = api_packet()
    result = client(tmp_path, transport, indexed).agent(p)
    validate_result(
        "api-map", {k: v for k, v in result.items() if k != "execution_model_evidence"}, p["input"]
    )
    assert len([a for s in result["services"] for a in s["interfaces"]]) == 4
    text = json.dumps(sent[0]["messages"], ensure_ascii=False)
    assert "interface_declarations" in text and "CloudMapService" in text
    if not indexed:
        assert '"evidence_catalog"' not in text
        assert "没有lookup_evidence工具" in text
    context = read_json(tmp_path / "context_index" / (fingerprint("sr-api-map") + ".json"))
    assert context["reference_contract"]["mode"] == ("indexed" if indexed else "raw")


def test_malformed_raw_reference_and_unknown_indexed_reference_have_distinct_errors():
    bad = {"services": [{"source_refs": ["e0123456789ab"]}]}
    with pytest.raises(ReferenceContractError) as raw:
        validate_raw_references(bad)
    assert raw.value.details["path"] == "/services/0/source_refs"
    assert raw.value.details["reference_mode"] == "raw"
    context = EvidenceContext(api_packet())
    with pytest.raises(ReferenceContractError) as unknown:
        context.expand(bad)
    assert unknown.value.details["category"] == "unknown_evidence_id"
    assert unknown.value.details["allowed_evidence_count"] > 0
    bad["services"][0]["source_refs"] = [{"source_id": "other"}]
    with pytest.raises(ReferenceContractError) as shape:
        context.expand(bad)
    assert shape.value.details["category"] == "reference_format_mismatch"


def test_indexed_interface_inventory_encodes_only_current_task_evidence():
    p = api_packet()
    p["interface_declarations"] = mapping_declarations(p["input"]["SR"])
    context = EvidenceContext(p)
    hints = context.packet["interface_declarations"]
    assert hints and all(r in context.pool for row in hints for r in row["source_refs"])
    assert "interface_declarations" in task_message(context.packet)
    assert all(r["source_id"] == "sr-document" for r in context.pool.values())


def test_raw_rejection_records_reference_mode_without_fabricating_an_evidence_catalog(tmp_path):
    response = {
        "services": [{"name": "X", "interfaces": [], "source_refs": ["imaginary-evidence"]}]
    }

    def transport(*args):
        return {
            "choices": [{"message": {"content": json.dumps(response)}, "finish_reason": "stop"}]
        }

    with pytest.raises(TaskRejected) as rejected:
        client(tmp_path, transport).agent(api_packet())
    saved = read_json(tmp_path / rejected.value.details["rejected_output"])
    assert saved["reference_mode"] == "raw"
    assert saved["reference_error"]["category"] == "reference_format_mismatch"
    assert saved["reference_error"]["path"] == "/services/0/source_refs"


def test_portable_version_comes_from_package_metadata_not_source_document(tmp_path):
    from scene_completion.infrastructure.program_version import program_version

    app = tmp_path / "app"
    app.mkdir()
    assert program_version(app)["source_commit"] is None
    write_json(tmp_path / "VERSION.json", {"source_commit": "a7e31f1", "platform": "windows-x64"})
    assert program_version(app) == {
        "source_commit": "a7e31f1",
        "origin": "VERSION.json",
        "built_at": None,
        "platform": "windows-x64",
    }
    assert document()["source_id"] == "sr-document"


def test_mermaid_alias_scope_does_not_leak_between_diagrams():
    d = document()
    d["lines"] = [
        {"number": n, "text": text}
        for n, text in enumerate(
            [
                "```mermaid",
                "sequenceDiagram",
                "participant X as FirstService",
                "P->>X: POST /first",
                "```",
                "```mermaid",
                "sequenceDiagram",
                "participant X as SecondService",
                "P->>X: DELETE /second",
                "```",
            ],
            1,
        )
    ]
    before = deepcopy(d)
    assert [c["receiver"] for c in mapping_declarations([d])] == ["FirstService", "SecondService"]
    assert d == before


def test_system_and_external_maps_are_disjoint_without_url_prefix_inference():
    from scene_completion.inputs.structured.api_boundaries import partition_documents

    services = [{"name": "CloudMapService"}, {"name": "ExternalDatabase"}]
    system = partition_documents([document()], services, "system")
    external = partition_documents([document()], services, "external")
    assert [c["path"] for c in mapping_declarations(system)] == ["/mx/v2/instances"]
    assert {c["receiver"] for c in mapping_declarations(external)} == {
        "CloudMapService",
        "ExternalDatabase",
    }
    assert {
        r["number"] for d in system for r in d["lines"] if "POST /cloudmap" in r["text"]
    } == set()


def test_external_contract_sections_keep_security_and_responses_separate():
    from scene_completion.inputs.structured.api_boundaries import partition_documents

    d = document()
    texts = [
        "# 接口",
        "## CloudMapService POST /any-prefix/resources",
        "需要 SA+RS256_PSS 签名认证。",
        "### 请求参数",
        "| resourceId | string | 必填 |",
        "### 成功响应",
        "| id | string |",
        "## PlatformService GET /same-prefix/resources",
        "请求字段 q 可选。",
    ]
    d["lines"] = [{"number": n, "text": s} for n, s in enumerate(texts, 1)]
    services = [{"name": "CloudMapService"}]
    external = partition_documents([d], services, "external")
    system = partition_documents([d], services, "system")
    assert "SA+RS256_PSS" in str(external) and "resourceId" in str(external)
    assert "SA+RS256_PSS" not in str(system)
    assert [c["path"] for c in mapping_declarations(system)] == ["/same-prefix/resources"]
    assert [c["path"] for c in mapping_declarations(external)] == ["/any-prefix/resources"]


def test_service_label_survives_subheadings_and_external_returns_and_notes_are_indexed():
    from scene_completion.inputs.documents.api_documents import index_interfaces
    from scene_completion.inputs.structured.api_boundaries import partition_documents

    d = document()
    texts = [
        "# 接口",
        "## API-C POST /resources",
        "| 所属服务 | CloudMapService |",
        "### 请求参数",
        "| count | integer | 可选 |",
        "## 调用",
        "```mermaid",
        "sequenceDiagram",
        "participant P as PlatformService",
        "participant C as CloudMapService",
        "P->>C: POST /resources",
        "Note over P,C: 必须使用SA+RS256_PSS签名认证",
        "C-->>P: 200 OK 返回 resourceId:string",
        "```",
    ]
    d["lines"] = [{"number": n, "text": s} for n, s in enumerate(texts, 1)]
    external = partition_documents([d], [{"name": "CloudMapService"}], "external")
    assert "count" in str(external) and "resourceId:string" in str(external)
    assert "SA+RS256_PSS" in str(external)
    maps, _ = complete_explicit_calls({"services": []}, external)
    index = index_interfaces({"SR": external, "api-map": maps})
    spans = index["apis"][0]["source_ranges"]
    for number in (12, 13):
        assert any(s["start"] <= number <= s["end"] for s in spans)


def test_external_parameters_bind_to_actual_external_call_and_keep_input_response_separate():
    from scene_completion.analysis.interactions.interaction_enrichment import (
        parameters_for,
        resolved_api_id,
    )
    from tests.support.workflow import R, exchange, parameter

    request = exchange(layer="SR", api=None)
    request["receiver"].update(name="CloudMapService", position="外部Actor（系统）")
    request["operation"]["name"] = "POST /anything/resources"
    mapping = {
        "services": [
            {
                "name": "CloudMapService",
                "interfaces": [
                    {
                        "id": "SR::external::C1",
                        "declared_id": "C1",
                        "source_layer": "SR",
                        "interface_scope": "external",
                        "name": "创建资源",
                        "address": "/anything/resources",
                        "method": "POST",
                        "source_refs": R,
                    }
                ],
            }
        ]
    }
    parameters = {
        "apis": [
            {
                "id": "SR::external::C1",
                "source_layer": "SR",
                "declared_id": "C1",
                "interface_scope": "external",
                "name": "创建资源",
                "address": "/anything/resources",
                "source_refs": R,
                "parameters": [
                    parameter("count", "body", False, "integer"),
                    parameter("resourceId", "response", True, "string"),
                ],
            }
        ]
    }
    inputs = {"api-map": mapping, "api-parameters": parameters}
    assert resolved_api_id(request, inputs) == "SR::external::C1"
    assert [p["name"] for p in parameters_for(request, inputs)] == ["count"]


def test_external_security_requirement_survives_without_inventing_parameters(tmp_path):
    from scene_completion.analysis.diagrams.artifact_exports import export_task
    from scene_completion.inputs.structured.api_catalog import combine

    d = document()
    d["lines"] = [{"number": 1, "text": "CloudMapService POST /resources 需要SA+RS256_PSS签名认证"}]
    ref = {
        "source_id": d["source_id"],
        "line_start": 1,
        "line_end": 1,
        "quote": d["lines"][0]["text"],
    }
    constraint = {"kind": "signature", "requirement": "SA+RS256_PSS签名认证", "source_refs": [ref]}
    interface = {
        "id": "SR::external::cloud",
        "name": "云资源创建",
        "address": "/resources",
        "method": "POST",
        "source_layer": "SR",
        "interface_scope": "external",
        "declared_id": "cloud",
        "source_refs": [ref],
        "interface_constraints": [constraint],
    }
    p = packet("api-parameters", {"SR": [d], "interface": interface})
    p.update(skill_text="test", node_key="external-api-part")
    original = deepcopy(p)

    def transport(*args):
        value = {
            "apis": [
                {
                    "id": interface["id"],
                    "name": interface["name"],
                    "address": "/resources",
                    "parameters": [],
                    "source_refs": [ref],
                }
            ]
        }
        return {"choices": [{"message": {"content": json.dumps(value)}, "finish_reason": "stop"}]}

    result = client(tmp_path / "run", transport).agent(p)
    result.pop("execution_model_evidence", None)
    validate_result("api-parameters", result, p["input"])
    api = result["apis"][0]
    assert api["interface_constraints"] == [constraint]
    assert api["parameters"] == [] and api["interface_scope"] == "external"
    catalog = combine(
        {"services": [{"name": "CloudMapService", "interfaces": [interface]}]}, result
    )
    assert catalog["rows"][0]["interface_constraints"] == [constraint]
    export_task(tmp_path / "exports", "api-parameters", result)
    assert "SA+RS256_PSS" in (tmp_path / "exports/api-parameters.md").read_text()
    assert p == original


def test_pipeline_publishes_independent_external_maps_and_contracts(tmp_path):
    from scene_completion.application.execution import Execution
    from scene_completion.workflow.planning import build_pipeline
    from tests.support.workflow import fake_pipeline

    rr, sr, tests, mocks = fake_pipeline(tmp_path)
    texts = [
        "```mermaid",
        "sequenceDiagram",
        "participant P as Platform",
        "participant X as CloudMapService",
        "P->>X: POST /cloudmap/resources",
        "P->>X: DELETE /cloudmap/resources/{id}",
        "```",
    ]
    start = len(sr[0]["lines"]) + 1
    sr[0]["lines"].extend({"number": start + n, "text": s} for n, s in enumerate(texts))
    ref = {
        "source_id": sr[0]["source_id"],
        "line_start": start + 3,
        "line_end": start + 3,
        "quote": texts[3],
    }
    mocks["components"]["components"].append(
        {
            "id": "cloud",
            "name": "CloudMapService",
            "composition_type": "外部Actor（系统）",
            "parent_id": None,
            "source_status": "explicit",
            "source_refs": [ref],
        }
    )
    mocks["api-map"] = lambda p: complete_explicit_calls(
        {"services": []}, p["input"].get("RR", []) + p["input"].get("SR", [])
    )[0]

    def parameters(p):
        i = p["input"]["interface"]
        return {"apis": [{**{k: v for k, v in i.items() if k != "source_role"}, "parameters": []}]}

    mocks["api-parameters"] = parameters
    ex = Execution(tmp_path / "run", mocks=mocks)
    build_pipeline(ex, rr, sr, tests)
    result = ex.finish()
    assert result["complete"], result
    state = read_json(tmp_path / "run/workflow_tasks.json")["tasks"]

    def saved(key):
        return read_json(tmp_path / "run" / state[key]["output_file"])["payload"]

    assert saved("sr-api-map") == {"services": []}
    assert len(saved("sr-external-api-map")["services"][0]["interfaces"]) == 2
    external = saved("external-api-parameters")["apis"]
    assert len(external) == 2 and all(a["interface_scope"] == "external" for a in external)
    assert all(a["id"].startswith("SR::external::") for a in external)
    assert saved("api-parameters")["apis"] == external


def test_signature_on_literal_external_call_is_retained_without_hardcoded_algorithms():
    from scene_completion.inputs.structured.http_interfaces import literal_call_requirements

    d = document()
    d["lines"][9]["text"] += "；必须采用SA+RS256_PSS签名认证"
    result, _ = complete_explicit_calls({"services": []}, [d])
    cloud = next(s for s in result["services"] if s["name"] == "CloudMapService")
    signature = cloud["interfaces"][0]["interface_constraints"][0]
    assert signature["kind"] == "signature" and "SA+RS256_PSS" in signature["requirement"]
    validate_result("api-map", result, {"SR": [d]})
    ref = deepcopy(signature["source_refs"][0])
    ref["quote"] = "POST /different-path 必须采用Other-Signature签名"
    assert "Other-Signature" in literal_call_requirements([ref])[0]["requirement"]
    ref["quote"] = "POST /different-path 本次携带Token"
    assert literal_call_requirements([ref]) == []


def test_diagnostics_exposes_recorded_reference_mode_and_program_identity(tmp_path, monkeypatch):
    from scene_completion.infrastructure import program_version
    from scene_completion.models.configuration.model_diagnostics import node_diagnostics

    program = tmp_path / "installed-program"
    program.mkdir()
    commit = "a" * 40
    write_json(program / "VERSION.json", {"source_commit": commit})
    monkeypatch.setattr(program_version, "PROGRAM_ROOT", program)
    root = tmp_path / "run"
    key = "sr-api-map"
    write_json(
        root / "workflow_tasks.json", {"tasks": {key: {"stage": "api-map", "status": "rejected"}}}
    )
    write_json(
        root / "context_index" / (fingerprint(key) + ".json"),
        {
            "reference_contract": {
                "mode": "raw",
                "source_ids": ["sr-source"],
                "evidence_count": None,
            },
        },
    )
    write_json(
        root / "agent_rejections/one.json",
        {
            "node_key": key,
            "error": "reference error",
            "reference_mode": "raw",
            "reference_error": {
                "category": "reference_format_mismatch",
                "path": "/services/0/source_refs",
            },
        },
    )
    diag = node_diagnostics(tmp_path, {"agent_model": "offline"}, key)
    assert diag["program_version"]["source_commit"] == commit
    assert diag["program_version"]["origin"] == "VERSION.json"
    assert diag["nodes"][0]["reference_contract"]["mode"] == "raw"
    assert (
        diag["nodes"][0]["validation_rejections"][0]["reference_error"]["path"]
        == "/services/0/source_refs"
    )


def test_abstract_external_call_is_not_mistaken_for_no_interface_declarations():
    from scene_completion.inputs.structured.api_boundaries import (
        has_declarations,
        partition_documents,
    )

    d = document()
    texts = [
        "# 调用",
        "```mermaid",
        "sequenceDiagram",
        "participant C as CloudMapService",
        "P->>C: createResource(name)",
        "```",
    ]
    d["lines"] = [{"number": n, "text": s} for n, s in enumerate(texts, 1)]
    external = partition_documents([d], [{"name": "CloudMapService"}], "external")
    view = task_document_view(external, "api-map")
    assert has_declarations(view, include_abstract=True)
    assert not has_declarations(view)
    # The tool cannot turn an abstract operation into an invented method/path.
    result, notes = complete_explicit_calls({"services": []}, view)
    assert result == {"services": []} and notes == []


def test_external_call_without_a_contract_cannot_enter_mapping_or_index():
    from scene_completion.inputs.documents.api_documents import index_interfaces
    from scene_completion.inputs.structured.external_interfaces import inventory

    inputs = external_scope(
        [
            "# GaussDB",
            "平台写入外部 GaussDB。",
            "```mermaid",
            "sequenceDiagram",
            "participant D as GaussDB",
            "P->>D: insertInstance(record)",
            "```",
        ]
    )
    assert not inventory(inputs)
    assert index_interfaces({**inputs, "api-map": {"services": []}}) == {"apis": []}
    fake = complete_explicit_calls({"services": []}, [document()])[0]
    api = fake["services"][0]["interfaces"][0]
    ref = {"source_id": "rr", "line_start": 2, "line_end": 2, "quote": "平台写入外部 GaussDB。"}
    api.update(address="/gaussdb/write", source_refs=[ref])
    bad = {"services": [{"name": "GaussDB", "interfaces": [api], "source_refs": [ref]}]}
    with pytest.raises(ValueError, match="no cited declaration"):
        validate_result("api-map", bad, inputs)
    with pytest.raises(ValueError, match="no cited declaration"):
        index_interfaces({**inputs, "api-map": bad})


def test_mixed_external_contracts_use_the_owned_declaration_and_exact_ranges():
    from scene_completion.inputs.documents.api_documents import index_interfaces
    from scene_completion.inputs.structured.external_interfaces import inventory, mapping_view

    inputs = external_scope(
        [
            "# GaussDB",
            "平台写入外部 GaussDB。",
            "# CloudMapService接口",
            "## API-C1 POST /resources",
            "### 请求",
            "必须使用SA+RS256_PSS签名认证",
            "### 成功响应",
            "200 OK",
            "## API-C2 订阅事件",
            "事件内容见订阅协议。",
        ],
        "SR",
    )
    seen = inventory(mapping_view(inputs))
    assert [(i["id"], i["method"], i["path"]) for i in seen] == [
        ("API-C1", "POST", "/resources"),
        ("API-C2", None, None),
    ]
    mapping = {
        "services": [
            {
                "name": "CloudMapService",
                "source_refs": seen[0]["source_refs"],
                "interfaces": [
                    {
                        "id": i["id"],
                        "name": i["name"],
                        "method": i["method"],
                        "address": i["path"],
                        "source_refs": i["source_refs"],
                    }
                    for i in seen
                ],
            }
        ]
    }
    validate_result("api-map", mapping, inputs)
    spans = index_interfaces({**inputs, "api-map": mapping})["apis"][0]["source_ranges"]
    assert spans == [{"source_id": "sr", "start": 4, "end": 8}]
    counterfeit = deepcopy(mapping)
    counterfeit["services"][0]["name"] = "GaussDB"
    with pytest.raises(ValueError, match="no cited declaration"):
        validate_result("api-map", counterfeit, inputs)


def test_adopted_external_mapping_is_indexed_from_its_structured_provenance():
    from scene_completion.inputs.documents.api_documents import index_interfaces
    from scene_completion.inputs.imports.artifact_conversion import cited_payload
    from scene_completion.inputs.structured.api_boundaries import scope_inputs
    from scene_completion.inputs.structured.external_interfaces import mapping_view

    mapping, doc = cited_payload(
        {
            "services": [
                {
                    "name": "CloudMapService",
                    "interfaces": [
                        {
                            "id": "API-TEST",
                            "name": "Create",
                            "method": "POST",
                            "address": "/remote/create",
                        }
                    ],
                }
            ]
        },
        "api-map",
        "file",
        "external.json",
    )
    inputs = scope_inputs(
        [doc],
        {
            "components": [
                {
                    "name": "CloudMapService",
                    "composition_type": "外部Actor（系统）",
                    "source_refs": [],
                }
            ]
        },
        "SR",
        "external",
    )
    validate_result("api-map", mapping, mapping_view(inputs))
    assert index_interfaces({**inputs, "api-map": mapping})["apis"][0]["source_ranges"]


def test_external_contract_table_preserves_explicit_owner_and_method_path_columns():
    from scene_completion.inputs.structured.external_interfaces import inventory, mapping_view

    inputs = external_scope(
        [
            "# 接口目录",
            "| API名称 | 所属服务 | 方法 | 路径 |",
            "| --- | --- | --- | --- |",
            "| API-CL | CloudMapService | POST | /cloud/resources |",
            "| API-IN | InternalService | POST | /internal/resources |",
        ]
    )
    assert [(d["receiver"], d["method"], d["path"]) for d in inventory(mapping_view(inputs))] == [
        ("CloudMapService", "POST", "/cloud/resources")
    ]


def test_pipeline_revalidates_stale_external_cache_without_model_or_parameter_task(tmp_path):
    from scene_completion.application.execution import Execution
    from scene_completion.workflow.planning import build_pipeline
    from tests.support.workflow import fake_pipeline

    rr, sr, tests, mocks = fake_pipeline(tmp_path)
    texts = [
        "# 系统组成",
        "```mermaid",
        "sequenceDiagram",
        "participant D as GaussDB",
        "P->>D: writeData(record)",
        "```",
    ]
    start = len(rr[0]["lines"]) + 1
    rr[0]["lines"].extend({"number": start + n, "text": text} for n, text in enumerate(texts))
    ref = {
        "source_id": rr[0]["source_id"],
        "line_start": start + 4,
        "line_end": start + 4,
        "quote": texts[4],
    }
    mocks["components"]["components"].append(
        {
            "id": "gauss",
            "name": "GaussDB",
            "composition_type": "外部Actor（系统）",
            "parent_id": None,
            "source_status": "explicit",
            "source_refs": [ref],
        }
    )
    seen = []

    def mapping(p):
        scope = p["input"]["interface-scope"]
        seen.append(scope["boundary"])
        return {"services": []}

    mocks["api-map"] = mapping
    root = tmp_path / "run"
    first = Execution(root, mocks=mocks)
    build_pipeline(first, rr, sr, tests)
    assert first.finish()["complete"]
    assert seen == ["system"]
    key = "rr-external-api-map"
    state = read_json(root / "workflow_tasks.json")
    record = state["tasks"][key]
    path = root / record["output_file"]
    stale = read_json(path)
    stale["payload"]["services"] = [
        {
            "name": "GaussDB",
            "source_refs": [ref],
            "interfaces": [
                {
                    "id": "DB-WRITE",
                    "name": "writeData",
                    "method": "POST",
                    "address": "/gaussdb/write",
                    "source_refs": [ref],
                }
            ],
        }
    ]
    write_json(path, stale)
    record["output_hash"] = fingerprint(stale)
    write_json(root / "workflow_tasks.json", state)

    second = Execution(root, mocks=mocks)
    build_pipeline(second, rr, sr, tests)
    assert second.finish()["complete"]
    assert seen == ["system"]
    saved = second.scheduler.state["tasks"]
    assert read_json(root / saved[key]["output_file"])["payload"] == {"services": []}
    assert read_json(root / saved["rr-external-api-index"]["output_file"])["payload"] == {
        "apis": []
    }
    assert not any(k.startswith("api-parameters-part-") for k in saved)
