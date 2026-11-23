"""A citation opens the original Markdown line behind a structured record.

The supplied function tree cites ``rrSpec``/``srSpec`` with their own line
numbers; those numbers disagreed with the shipped specification for most of
the SR records. The resolver must never show a different line than the quoted
text, so it verifies the declared line first and falls back to a unique
quotation, otherwise reporting the record as untraced.
"""

import json

from scene_completion.inputs.provenance import source_origins
from scene_completion.inputs.structured.colleague_formats import convert, format_of

RR = "# 需求\n\n## 目标\n\n| 系统 | 说明 |\n| --- | --- |\n| 商城 | 系统负责商品浏览与下单 |\n"
SR = (
    "# 设计\n\n"
    "## 查询参数\n"
    "- keyword：商品关键词，可选。\n"
    "- 成功响应：productId、name、price\n"
    "## 流程\n"
    "1. 系统根据请求条件查询 product 表。\n"
)


def documents(tmp_path):
    (tmp_path / "系统需求_spec.md").write_text(RR, encoding="utf-8")
    (tmp_path / "功能设计_spec.md").write_text(SR, encoding="utf-8")
    return source_origins.origin_index(
        [
            source_origins.read_origin_document(tmp_path / "系统需求_spec.md", "RR")[0],
            source_origins.read_origin_document(tmp_path / "功能设计_spec.md", "SR")[0],
        ]
    )


def test_declared_line_that_matches_is_exact(tmp_path):
    rr = documents(tmp_path)[0]
    found = source_origins.origin(rr, "系统负责商品浏览与下单", "L7")
    assert (found["match"], found["start_line"]) == ("exact", 7)


def test_wrong_declared_line_falls_back_to_the_unique_quotation(tmp_path):
    sr = documents(tmp_path)[1]
    found = source_origins.origin(sr, "productId、name、price", "L2")
    assert found["match"] == "located"
    assert found["start_line"] == 5
    assert found["declared_line"] == "L2"
    assert "productId" in found["quote"]


def test_ambiguous_quotation_is_reported_not_guessed(tmp_path):
    sr = documents(tmp_path)[1]
    docs = {
        **sr,
        "lines": sr["lines"] + [{"number": 9, "text": "- 成功响应：productId、name、price"}],
    }
    # Two equally close occurrences: picking either one would be a guess.
    found = source_origins.origin(docs, "productId、name、price", "L7")
    assert found["match"] == "pending"
    assert found["start_line"] is None
    assert "无法唯一定位" in found["reason"]


def test_function_id_tree_keeps_both_its_pointer_and_the_original_line(tmp_path):
    tree = {
        "functions": [
            {
                "functionId": "UCG-001-UC001",
                "name": "浏览商品",
                "rrLayer": {"entities": [], "commands": []},
                "srLayer": {
                    "entities": [
                        {
                            "entity": "Product",
                            "attributes": [
                                {
                                    "name": "product_id",
                                    "type": "string",
                                    "source": {
                                        "doc": "srSpec",
                                        "line": "L2",
                                        "quote": "根据请求条件查询 product 表",
                                    },
                                }
                            ],
                        }
                    ],
                    "commands": [],
                },
            }
        ]
    }
    assert format_of(tree) == "function_tree"
    product = convert(tree, "file", "功能树.json", documents(tmp_path))
    attribute = product["artifacts"][0]["payload"]["entities"][0]["attributes"][0]
    ref = attribute["source_refs"][0]
    assert ref["source_id"].startswith("import-file-facts-v1")
    assert ref["origin"]["document"] == "功能设计_spec.md"
    assert ref["origin"]["match"] in {"located", "exact"}
    assert "product 表" in ref["origin"]["quote"]


def test_legacy_single_string_source_is_read(tmp_path):
    origin = source_origins.source_origin("功能设计_spec.md:L6 - 根据请求条件查询 product 表")
    assert origin == ("功能设计_spec.md", "根据请求条件查询 product 表", "L6")


def test_absolute_path_uses_unique_suffix_or_configured_alias():
    from scene_completion.inputs.provenance.source_origins import resolve_name

    configured = {"name": "spec.md", "path": "design/spec.md", "registered": True}
    other = {"name": "spec.md", "path": "requirements/spec.md", "registered": True}
    docs = [configured, other]
    assert resolve_name(r"D:\handoff\DESIGN\Spec.md", docs) == configured
    assert resolve_name("/supplier/requirements/spec.md", docs) == other
    assert resolve_name("/old-workspace/spec.md", docs) is None
    assert resolve_name("/old-workspace/spec.md", [other]) == other
    assert resolve_name("wrong-folder/spec.md", [other]) is None
    assert resolve_name("/old-workspace/missing.md", docs) is None
    configured["configured_aliases"] = [r"\\supplier\share\spec.md"]
    assert resolve_name("//supplier/share/spec.md", docs) == configured


def test_absolute_source_reference_cannot_open_external_file(tmp_path):
    from scene_completion.inputs.provenance.ssd_sources import Sources
    from scene_completion.workflow.ssd.input_conversion.provenance import origin_documents

    root = tmp_path / "inputs"
    root.mkdir()
    original = tmp_path / "RR-secret.md"
    original.write_text("外部引文", encoding="utf-8")
    source = Sources(root, origin_documents(root))
    assert (
        source.trace({"doc": str(original), "line": "L1", "quote": "外部引文"})["match"]
        == "pending"
    )


def test_missing_original_keeps_the_pointer_without_a_line(tmp_path):
    tree = json.loads(json.dumps(_tree()))
    product = convert(tree, "file", "功能树.json", [])
    ref = product["artifacts"][0]["payload"]["entities"][0]["attributes"][0]["source_refs"][0]
    assert ref["origin"]["match"] == "pending"
    assert "原文未提供" in ref["origin"]["reason"]


def _tree():
    return {
        "functions": [
            {
                "functionId": "UCG-001-UC001",
                "name": "浏览商品",
                "rrLayer": {"entities": [], "commands": []},
                "srLayer": {
                    "entities": [
                        {
                            "entity": "Product",
                            "attributes": [
                                {
                                    "name": "product_id",
                                    "type": "string",
                                    "source": {"doc": "srSpec", "line": "L6", "quote": "查询"},
                                }
                            ],
                        }
                    ],
                    "commands": [],
                },
            }
        ]
    }
