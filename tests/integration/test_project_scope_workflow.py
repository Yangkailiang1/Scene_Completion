from copy import deepcopy
from types import SimpleNamespace

import pytest

from scene_completion.analysis.project_scopes.pipeline import structure_bundles, structure_inputs
from scene_completion.analysis.validation import validate_result
from scene_completion.application import project_scope_service as service
from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.contracts import packet
from scene_completion.domain.project_scopes.metrics import analyze
from scene_completion.domain.project_scopes.validation import validate
from scene_completion.workflow.project_scopes import _compare, _generate, _identify, _prepare


def source_cases():
    doc = {
        "id": "rr",
        "name": "需求",
        "role": "RR",
        "content": "# 正常流程\n创建商品完成后才能发布商品。\n发布商品后通过外部通知服务通知商家。\n# 异常流程\nE_SECRET不得进入正向分析",
    }
    cases = []
    for cid, name in (("C1", "创建商品"), ("C2", "发布商品")):
        channels = {
            ch: {"concerns": [], "scenarios": [], "pending": [], "project_records": []}
            for ch in ("E", "G", "GT")
        }
        for ch in ("E", "GT"):
            channels[ch]["project_records"] = [
                {
                    "id": ch + cid,
                    "scope": "business_chain",
                    "key": "global.call_order",
                    "condition": ch + "_SECRET:尚未创建商品就发布",
                    "expected": "拒绝发布",
                    "source_refs": [
                        {
                            "document_id": ch,
                            "quote": ch + "_SECRET",
                            "start_line": 1,
                            "end_line": 1,
                            "kind": "test" if ch == "GT" else "origin",
                        }
                    ],
                }
            ]
        cases.append(
            {
                "case": {"id": cid, "name": name},
                "steps": [],
                "channels": channels,
                "documents": [doc],
                "entities": [{"id": "Product", "name": "商品", "attributes": []}],
                "apis": [],
            }
        )
    return cases


def graph():
    return {
        "dependencies": [
            {
                "from_case_id": "C1",
                "to_case_id": "C2",
                "relation_type": "direct",
                "condition": "商品创建完成",
                "obligation": "创建后发布",
                "entity_ids": ["Product"],
                "source_ref_ids": ["rr:2"],
            }
        ],
        "services": [
            {
                "name": "外部通知服务",
                "identity": "notification",
                "description": "通知商家",
                "technology": None,
                "api_ids": [],
                "case_ids": ["C2"],
                "source_ref_ids": ["rr:3"],
            }
        ],
        "pending": [],
    }


def bundles(parts=None):
    cases = source_cases()
    docs, inputs = structure_inputs(cases)
    return structure_bundles(cases, docs, inputs, parts or [graph()], default_registry())


def executor(tmp_path, enabled=True):
    calls = []
    ex = SimpleNamespace(
        root=tmp_path / "run",
        client=object() if enabled else None,
        mode="client" if enabled else "packets",
        mocks=None,
        artifact_identity={},
        registry_snapshot=default_registry(),
    )

    def semantic(task, inputs, record):
        calls.append((task, deepcopy(inputs)))
        if task == "project-structure":
            result = graph()
        elif task == "project-scope-generate":
            result = {
                "analyses": [
                    {
                        "scenario_id": row["id"],
                        "analysis": "在商品发布业务中核对前置商品状态及调用条件",
                    }
                    for row in inputs["templates"]
                ],
                "supplements": [],
            }
        elif task == "project-scope-identify":
            result = {
                "observations": [
                    {
                        "source_record_id": row["id"],
                        "anchor_id": inputs["anchors"][0]["id"],
                        "key": "global.call_order",
                        "condition": row["condition"],
                        "expected": row["expected"],
                    }
                    for row in inputs["records"]
                ],
                "pending": [],
                "excluded": [],
            }
        else:
            result = {
                "decisions": [
                    {
                        "left_id": p["left"]["id"],
                        "right_id": p["right"]["id"],
                        "status": "partial",
                        "reason": "具体条件存在差异",
                    }
                    for p in inputs["pairs"]
                ]
            }
        validate_result(task, result, inputs)
        return result, {}

    ex.semantic = semantic
    return ex, calls


def test_direct_relations_keep_distinct_semantics_services_deduplicate_and_cascade_is_local():
    first = graph()
    second = graph()
    second["dependencies"][0].update(condition="商品价格审核通过", obligation="审核后发布")
    third = graph()
    third["dependencies"][0].update(
        relation_type="cascade", condition="前置商品删除", obligation="联动撤销发布"
    )
    data = bundles([first, deepcopy(first), second, third])
    chain, architecture = data["business_chain"], data["architecture"]
    assert len(chain["anchors"]) == 3
    assert len(architecture["anchors"]) == 1
    assert len(chain["channels"]["G"]["concerns"]) == 10
    cascades = [
        r for r in chain["channels"]["G"]["concerns"] if r["key"] == "global.cascade_operation"
    ]
    assert len(cascades) == 1
    assert (
        next(a for a in chain["anchors"] if a["id"] == cascades[0]["anchor_id"])["relation_type"]
        == "cascade"
    )
    assert all("step_id" not in r for c in data.values() for r in c["channels"]["G"]["concerns"])


def test_real_task_contract_paths_preserve_positive_and_channel_isolation(tmp_path):
    ex, calls = executor(tmp_path)
    prepared = _prepare(ex, source_cases(), [], None)["business_chain"]
    generated = _generate(ex, prepared, None)
    identified = _identify(ex, prepared, None)
    result = _compare(ex, generated, identified, None)
    assert result["gt_identification_run_complete"] is True
    for task, inputs in calls:
        text = str(inputs)
        if task in {"project-structure", "project-scope-generate"}:
            assert "E_SECRET" not in text and "GT_SECRET" not in text
            assert "channels" not in inputs
        if task == "project-scope-identify":
            other = "GT_SECRET" if inputs["channel"] == "E" else "E_SECRET"
            assert other not in text
            assert "templates" not in inputs
        assert packet(task, inputs)["task"] == task
    assert all(r.get("analysis") for r in result["channels"]["G"]["scenarios"])
    assert result["channels"]["E"]["scenarios"][0]["source_refs"][0]["document_id"] == "E"
    assert result["channels"]["GT"]["scenarios"][0]["source_refs"][0]["kind"] == "test"
    assert service.editor(tmp_path, "business_chain")["bundle"]["scope"]["id"] == "business_chain"


def test_sources_without_positive_anchors_are_pending_and_never_dropped(tmp_path):
    ex, calls = executor(tmp_path)
    value = bundles()["business_chain"]
    value["anchors"] = []
    value["channels"]["G"] = {"concerns": [], "scenarios": [], "pending": []}
    result = _identify(ex, value, None)
    assert not calls
    assert len(result["channels"]["E"]["pending"]) == 2
    assert len(result["channels"]["GT"]["pending"]) == 2
    assert result["channels"]["GT"]["pending"][0]["source_refs"]
    assert not analyze(result)["completeness"]["complete"]


def test_no_model_retains_templates_and_visible_generation_pending(tmp_path):
    ex, calls = executor(tmp_path, False)
    value = _generate(ex, bundles()["business_chain"], None)
    assert not calls and value["channels"]["G"]["scenarios"]
    assert value["generation_pending"]
    assert not analyze(value)["completeness"]["complete"]


def test_project_revision_preserves_original_and_manual_changes_across_publish(tmp_path):
    baseline = bundles()["business_chain"]
    first = service.publish(tmp_path, baseline)
    edited = deepcopy(first["bundle"])
    edited["channels"]["G"]["scenarios"][0]["analysis"] = "人工业务分析"
    saved = service.save_revision(
        tmp_path, "business_chain", {"base_revision": 1, "bundle": edited, "reason": "人工修订"}
    )
    assert saved["revision"] == 2
    rerun = deepcopy(baseline)
    rerun["channels"]["G"]["scenarios"][0]["analysis"] = "机器新的分析"
    current = service.publish(tmp_path, rerun)
    assert current["bundle"]["channels"]["G"]["scenarios"][0]["analysis"] == "人工业务分析"
    assert (
        service.editor(tmp_path, "business_chain", "original")["bundle"]["channels"]["G"][
            "scenarios"
        ][0]["analysis"]
        == "机器新的分析"
    )
    assert service.editor(tmp_path, "business_chain", 1)["bundle"] == first["bundle"]
    with pytest.raises(service.RevisionConflict):
        service.save_revision(tmp_path, "business_chain", {"base_revision": 1, "bundle": edited})


def test_delete_anchor_retains_unbound_records_and_pending_can_be_promoted(tmp_path):
    first = service.publish(tmp_path, bundles()["business_chain"])
    modified = deepcopy(first["bundle"])
    anchor = modified["anchors"][0]["id"]
    modified["channels"]["E"]["pending"] = [
        {
            "id": "manual-source",
            "anchor_id": anchor,
            "target": "dependency",
            "key": "global.call_order",
            "condition": "未创建商品就发布",
            "expected": "拒绝",
            "status": "active",
            "source_refs": [],
        }
    ]
    promoted = service.save_revision(
        tmp_path, "business_chain", {"base_revision": 1, "bundle": modified}
    )
    assert len(promoted["bundle"]["channels"]["E"]["scenarios"]) == 1
    assert not promoted["bundle"]["channels"]["E"]["pending"]
    removed = deepcopy(promoted["bundle"])
    removed["anchors"] = []
    saved = service.save_revision(
        tmp_path, "business_chain", {"base_revision": 2, "bundle": removed}
    )
    assert all(r["status"] == "unbound" for r in saved["bundle"]["channels"]["G"]["scenarios"])
    assert saved["completeness"]["pending_records"] > 0


def test_semantic_contract_rejects_omitted_source_or_template_before_cache():
    with pytest.raises(ValueError, match="逐条"):
        validate_result(
            "project-scope-identify",
            {"observations": [], "pending": [], "excluded": []},
            {
                "records": [{"id": "E1"}],
                "anchors": [],
                "allowed_keys": [],
                "scope": "business_chain",
            },
        )
    with pytest.raises(ValueError, match="模板"):
        validate_result(
            "project-scope-generate",
            {"analyses": [], "supplements": []},
            {"templates": [{"id": "t1", "concern_id": "c1"}]},
        )


def test_project_metrics_are_anchor_unique_and_cross_anchor_decisions_rejected():
    value = bundles()["business_chain"]
    value["channels"]["E"] = deepcopy(value["channels"]["G"])
    value["channels"]["GT"] = deepcopy(value["channels"]["G"])
    assert analyze(value)["metrics"]["generation_validity"]["value"] == 100
    a, b = value["channels"]["G"]["concerns"][:2]
    value["decisions"] = [
        {
            "id": "bad",
            "level": "concern",
            "pair": "G_E",
            "left_id": a["id"],
            "right_id": b["id"],
            "status": "full",
            "origin": "manual",
        }
    ]
    with pytest.raises(ValueError, match="同一项目锚点"):
        validate(value)


def test_structure_rejects_human_actor_and_state_only_inferred_edges():
    _, inputs = structure_inputs(source_cases())
    inputs["human_parties"] = [{"id": "merchant", "name": "商家"}]
    value = graph()
    value["services"][0].update(name="商家", identity="merchant")
    with pytest.raises(ValueError, match="人类Actor"):
        validate_result("project-structure", value, inputs)
    value = graph()
    inputs["source_lines"][1]["text"] = "商品仅允许DRAFT状态更新，并检查version。"
    with pytest.raises(ValueError, match="单用例状态"):
        validate_result("project-structure", value, inputs)


def test_project_projection_is_compact_and_excludes_human_actors():
    import json

    from scene_completion.analysis.ssd.pipeline import build_cases
    from tests.support.paths import ROOT

    cases = build_cases(ROOT / "datasets/mini-mall/输入文件")
    docs, inputs = structure_inputs(cases)
    names = {row["name"] for row in inputs["known_external_services"]}
    assert names == {"CatalogDatabaseService"}
    text = json.dumps(inputs["positive_cases"], ensure_ascii=False)
    assert "source_refs" not in text
    assert len(text) < 80_000
    result = structure_bundles(cases, docs, inputs, [], default_registry())
    services = {a["name"] for a in result["architecture"]["anchors"]}
    assert "CatalogDatabaseService" in services
    assert "商家" not in services
    assert all(
        a["kind"] == "external_service" and a["external"] for a in result["architecture"]["anchors"]
    )
    assert len(result["architecture"]["anchors"]) == len(
        {a["id"] for a in result["architecture"]["anchors"]}
    )


def test_architecture_mounts_one_availability_concern_per_external_service():
    data = bundles([graph()])
    architecture = data["architecture"]
    assert len(architecture["anchors"]) == 1
    assert {c["key"] for c in architecture["channels"]["G"]["concerns"]} == {
        "service.base.availability"
    }
    assert len(architecture["channels"]["G"]["concerns"]) == len(architecture["anchors"])
    assert len(architecture["channels"]["G"]["scenarios"]) == len(architecture["anchors"])
    assert all(
        s["template_id"] == "service.base.availability:service_unavailable"
        for s in architecture["channels"]["G"]["scenarios"]
    )


def test_project_scope_routes_return_404_when_scope_has_no_result(tmp_path):
    import json

    from fastapi.testclient import TestClient

    from scene_completion.api.application import create_app
    from scene_completion.application.project_service import Workbench

    service = Workbench(tmp_path / "projects")
    project = service.create(
        {
            "name": "no project scope",
            "review_mode": "auto",
            "sources": {
                "RR": [{"name": "rr.md", "content": "# RR 正常需求\n创建商品。\n"}],
                "SR": [{"name": "sr.md", "content": "# SR 正常设计\n创建商品。\n"}],
            },
        }
    )
    client = TestClient(create_app(tmp_path / "projects"))
    response = client.get(f"/api/projects/{project['id']}/project-results/architecture/editor")
    assert response.status_code == 404
    assert "尚无项目结果" in response.json()["detail"]["message"]
    invalid = client.get(f"/api/projects/{project['id']}/project-results/unknown/editor")
    assert invalid.status_code == 404
    assert json.loads(invalid.text)["detail"]["message"] == "未知的项目分析范围"
    service.pool.shutdown()


def test_project_offline_review_round_trip(tmp_path):
    import json

    from scene_completion.application import project_scope_review as review

    service.publish(tmp_path, bundles()["business_chain"])
    html = review.export_legacy_review(tmp_path, {"scope": "business_chain"})
    payload, entry = review._parse(html)
    assert entry["scope"] == "business_chain"
    row = next(
        r
        for r in payload["cases"][0]["bundle"]["channels"]["G"]["scenarios"]
        if r["status"] == "active"
    )
    row["condition"] = "离线业务修正：" + row["condition"]
    content = json.dumps(payload, ensure_ascii=False)
    preview = review.preview_feedback(tmp_path, content)
    assert preview["status"] == "ready" and not preview["conflicts"]
    applied = review.apply_feedback(tmp_path, content, scope="business_chain")
    assert applied["status"] == "applied" and applied["revision"] == 2
    saved = service.editor(tmp_path, "business_chain")["bundle"]
    assert any(
        s["condition"].startswith("离线业务修正") for s in saved["channels"]["G"]["scenarios"]
    )
    assert review.apply_feedback(tmp_path, content, scope="business_chain")["status"] == "unchanged"
