import pytest

from scene_completion.analysis.validation import validate_result
from scene_completion.inputs.documents.api_documents import index_interfaces


def test_index_uses_every_mapped_interface_and_exact_paths():
    lines = [
        "# APIs",
        "## API-1 List",
        "GET /items",
        "query page",
        "## API-2 Detail",
        "GET /items/{id}",
        "path id",
    ]
    doc = {
        "source_id": "s",
        "name": "sr.md",
        "channel": "normal",
        "lines": [{"number": n, "text": v} for n, v in enumerate(lines, 1)],
    }

    def api(id, name, address, n):
        return {
            "id": id,
            "name": name,
            "address": address,
            "method": "GET",
            "source_refs": [
                {"source_id": "s", "line_start": n, "line_end": n, "quote": lines[n - 1]}
            ],
        }

    mapping = {
        "services": [
            {
                "name": "Service",
                "interfaces": [
                    api("API-1", "List", "/items", 3),
                    api("API-2", "Detail", "/items/{id}", 6),
                ],
                "source_refs": [
                    {"source_id": "s", "line_start": 1, "line_end": 1, "quote": "# APIs"}
                ],
            }
        ]
    }
    inputs = {"SR": [doc], "api-map": mapping}
    result = index_interfaces(inputs)
    assert [a["id"] for a in result["apis"]] == ["API-1", "API-2"]
    spans = result["apis"][0]["source_ranges"]
    assert any(r["start"] == 2 and r["end"] == 4 for r in spans)
    assert not any(r["start"] >= 5 for r in spans)
    validate_result("api-index", result, inputs)


def test_parameter_task_preserves_known_interface_address():
    inputs = {"SR": [], "interface": {"id": "a", "address": "/items"}}
    p = {
        "apis": [
            {
                "id": "a",
                "name": "List",
                "address": None,
                "parameters": [],
                "source_refs": [
                    {"source_id": "s", "line_start": 1, "line_end": 1, "quote": "list"}
                ],
            }
        ]
    }
    inputs["interface"]["source_refs"] = p["apis"][0]["source_refs"]
    with pytest.raises(ValueError, match="地址"):
        validate_result("api-parameters", p, inputs)


def test_unknown_interface_never_falls_back_to_all_parameter_contracts():
    from scene_completion.inputs.documents.api_documents import case_parameters
    from tests.support.workflow import exchange

    i = exchange(api="unknown")
    assert case_parameters(
        {"api-parameters": {"apis": [{"id": "unrelated"}]}, "api-map": {"services": []}},
        {"interactions": [i]},
    ) == {"apis": []}


def test_explicit_method_path_resolves_without_path_similarity_or_name_guessing():
    from scene_completion.analysis.interactions.interaction_enrichment import resolved_api_id
    from tests.support.workflow import exchange

    i = exchange(api=None)
    i["operation"]["name"] = "POST /catalog/search"
    context = {
        "api-parameters": {
            "apis": [{"id": "search", "address": "/catalog/search", "name": "搜索"}]
        },
        "api-map": {
            "services": [
                {
                    "name": "Catalog",
                    "interfaces": [
                        {
                            "id": "search",
                            "name": "搜索",
                            "method": "POST",
                            "address": "/catalog/search",
                        }
                    ],
                }
            ]
        },
    }
    assert resolved_api_id(i, context) == "search"
    i["operation"]["name"] = "GET /catalog/search"
    assert resolved_api_id(i, context) is None
    i["operation"]["name"] = "POST /catalog/search-similar"
    assert resolved_api_id(i, context) is None


def test_mapping_cannot_omit_an_explicit_downstream_method_path():
    ref = {
        "source_id": "s",
        "line_start": 1,
        "line_end": 1,
        "quote": "系统向 SearchService 发送 POST /catalog/search 请求。",
    }
    doc = {
        "source_id": "s",
        "name": "sr.md",
        "channel": "normal",
        "lines": [{"number": 1, "text": ref["quote"]}],
    }
    with pytest.raises(ValueError, match="downstream"):
        validate_result("api-map", {"services": []}, {"SR": [doc]})
    value = {
        "services": [
            {
                "name": "SearchService",
                "interfaces": [
                    {
                        "id": "local-search",
                        "name": "Search",
                        "method": "POST",
                        "address": "/catalog/search",
                        "source_refs": [ref],
                    }
                ],
                "source_refs": [ref],
            }
        ]
    }
    validate_result("api-map", value, {"SR": [doc]})


def test_invocation_values_are_not_global_interface_defaults_or_enum():
    ref = {
        "source_id": "s",
        "line_start": 1,
        "line_end": 1,
        "quote": "系统发送 POST /search，请求体补充status=ON_SALE。",
    }
    doc = {
        "source_id": "s",
        "name": "sr.md",
        "channel": "normal",
        "lines": [{"number": 1, "text": ref["quote"]}],
    }
    inputs = {
        "SR": [doc],
        "interface": {"id": "search", "address": "/search", "source_role": "invocation_only"},
    }
    p = {
        "name": "status",
        "location": "body",
        "data_type": None,
        "required": None,
        "default": "ON_SALE",
        "constraints": [],
        "source_refs": [ref],
    }
    value = {
        "apis": [
            {
                "id": "search",
                "name": "search",
                "address": "/search",
                "parameters": [p],
                "source_refs": [ref],
            }
        ]
    }
    with pytest.raises(ValueError, match="默认值"):
        validate_result("api-parameters", value, inputs)
    p["default"] = None
    validate_result("api-parameters", value, inputs)


def test_bold_interface_and_peer_response_sections_remain_in_parameter_context():
    lines = [
        "**API-1**",
        "GET /items",
        "## 请求参数",
        "| 参数 | 类型 |",
        "| page | integer |",
        "## 成功响应",
        "| 字段 | 类型 | 是否必填 |",
        "| items | array | 是 |",
        "**API-2**",
        "GET /next",
    ]
    ref = {"source_id": "s", "line_start": 1, "line_end": 1, "quote": lines[0]}
    doc = {
        "source_id": "s",
        "name": "sr.md",
        "channel": "normal",
        "lines": [{"number": i, "text": t} for i, t in enumerate(lines, 1)],
    }
    iface = {
        "id": "API-1",
        "name": "List",
        "method": "GET",
        "address": "/items",
        "source_refs": [ref],
    }
    result = index_interfaces(
        {"SR": [doc], "api-map": {"services": [{"name": "svc", "interfaces": [iface]}]}}
    )
    spans = result["apis"][0]["source_ranges"]
    assert any(s["start"] <= 8 <= s["end"] for s in spans)
    assert all(s["end"] < 9 for s in spans)
    from scene_completion.inputs.documents.api_documents import complete_success_responses

    output = {"apis": [{"id": "API-1", "parameters": []}]}
    filled = complete_success_responses(output, {"SR": [doc], "interface": iface})
    assert [
        (p["name"], p["location"], p["data_type"], p["required"])
        for p in filled["apis"][0]["parameters"]
    ] == [("items", "response", "array", True)]
    assert output["apis"][0]["parameters"] == []


def test_response_contract_variants_keep_success_and_failure_fields_separate():
    from scene_completion.inputs.documents.api_documents import (
        case_parameters,
        complete_success_responses,
        response_contract_documents,
    )
    from scene_completion.inputs.documents.source_documents import normal_projection
    from tests.support.workflow import exchange

    lines = [
        "## API-1 查询",
        "GET /items",
        "### 成功响应 200",
        "| 字段 | 类型 | 是否必填 | 默认值 | 长度 |",
        "| name | string | 是 |  | 1-30 |",
        "### 失败响应 400",
        "| 字段 | 类型 | 是否必填 |",
        "| name | integer | 否 |",
        "| message | string | 是 |",
        "### 失败响应 404",
        "| 字段 | 类型 | 是否必填 |",
        "| code | string | 是 |",
        "## API-2 next",
        "GET /next",
    ]
    raw = {
        "source_id": "s",
        "name": "sr.md",
        "channel": "normal",
        "lines": [{"number": n, "text": t} for n, t in enumerate(lines, 1)],
    }
    refs = [{"source_id": "s", "line_start": 1, "line_end": 1, "quote": lines[0]}]
    base = {
        "apis": [
            {
                "id": "API-1",
                "name": "查询",
                "address": "/items",
                "parameters": [],
                "source_refs": refs,
            }
        ]
    }
    source = normal_projection([raw])
    errors = response_contract_documents([raw])
    inputs = {
        "SR": source,
        "interface": {"id": "API-1", "address": "/items"},
        "response-documents": errors,
    }
    filled = complete_success_responses(base, inputs)
    validate_result("api-parameters", filled, inputs)
    a = filled["apis"][0]
    success = a["parameters"][0]
    assert (success["name"], success["data_type"], success["required"]) == ("name", "string", True)
    assert success["constraints"][0]["kind"] == "length"
    variants = {(v["kind"], v["status_code"]): v for v in a["responses"]}
    assert set(variants) == {("success", "200"), ("error", "400"), ("error", "404")}
    assert variants["error", "400"]["parameters"][0]["data_type"] == "integer"
    assert {p["name"] for p in a["parameters"]} == {"name"}
    assert complete_success_responses(filled, inputs) == filled
    i = exchange(api="API-1")
    safe = case_parameters({"api-parameters": filled}, {"interactions": [i]})
    assert "responses" not in safe["apis"][0] and "message" not in str(safe)
    bad = __import__("copy").deepcopy(filled)
    bad["apis"][0]["parameters"].append(variants["error", "404"]["parameters"][0])
    with pytest.raises(ValueError, match="失败响应"):
        validate_result("api-parameters", bad, inputs)


def test_response_table_fills_known_field_missing_attributes_without_erasing_false_or_zero():
    from scene_completion.inputs.documents.api_documents import complete_success_responses
    from tests.support.workflow import parameter

    lines = [
        "### 成功响应 201",
        "| 字段 | 类型 | 是否必填 | 默认值 |",
        "| count | integer | 否 | 0 |",
    ]
    doc = {
        "source_id": "s",
        "name": "sr.md",
        "channel": "normal",
        "lines": [{"number": n, "text": t} for n, t in enumerate(lines, 1)],
    }
    p = parameter("count", "response", None, None)
    out = complete_success_responses(
        {"apis": [{"id": "API-1", "parameters": [p]}]}, {"SR": [doc], "interface": {"id": "API-1"}}
    )
    p = out["apis"][0]["parameters"][0]
    assert p["data_type"] == "integer" and p["required"] is False and p["default"] == 0


def test_api_binding_uses_explicit_identifier_or_pure_method_path_not_nearby_names():
    from scene_completion.analysis.interactions.interaction_enrichment import resolved_api_id
    from tests.support.workflow import exchange

    i = exchange(api=None)
    ctx = {
        "api-parameters": {"apis": [{"id": "API-M-IF2", "name": "查询", "address": "/items"}]},
        "api-map": {
            "services": [
                {
                    "name": "svc",
                    "interfaces": [
                        {"id": "API-M-IF2", "name": "查询", "method": "GET", "address": "/items"}
                    ],
                }
            ]
        },
    }
    i["operation"]["name"] = "调用 API-M-IF2 查询"
    assert resolved_api_id(i, ctx) == "API-M-IF2"
    i["operation"]["name"] = "GET /items<br/>查询"
    assert resolved_api_id(i, ctx) == "API-M-IF2"
    i["operation"]["name"] = "POST /items"
    assert resolved_api_id(i, ctx) is None
    i["api_id"] = " API–M–IF2 "
    assert resolved_api_id(i, ctx) == "API-M-IF2"
