"""Real mixed-layer imports and unresolved questions must not fail as known facts."""

from copy import deepcopy

import pytest

from scene_completion.analysis.validation import refs_required, validate_result
from scene_completion.infrastructure.storage import read_json
from scene_completion.inputs.api_layers import scoped_api_document, scoped_imports
from scene_completion.inputs.artifact_imports import snapshot
from scene_completion.inputs.colleague_formats import convert
from scene_completion.inputs.input_bundles import apply, discover
from scene_completion.inputs.source_documents import read_project_documents, validate_evidence
from scene_completion.inputs.structure_models import imported_sources
from scene_completion.workflow.engine import Execution, build_pipeline
from tests.test_input_bundles import apis, project, write_folder
from tests.test_workflow import R


def layered_api():
    value = apis()
    for api, layer in zip(value["apis"], ("RR", "SR"), strict=True):
        api["source_layer"] = layer
    return value


def test_mixed_api_import_preserves_source_lines_but_separates_layer_evidence():
    converted = convert(layered_api(), "input", "api_extraction.json")
    maps = [a for a in converted["artifacts"] if a["task"] == "api-map"]
    assert len(maps) == 2
    for a, own, other in (
        (maps[0], "/arbitrary/1", "/arbitrary/2"),
        (maps[1], "/arbitrary/2", "/arbitrary/1"),
    ):
        doc = a["document"]
        text = "\n".join(r["text"] for r in doc["lines"])
        assert own in text and other not in text
        assert {r["number"] for r in doc["lines"]} == {r["line"] for r in a["json_locations"]}
        validate_result("api-map", a["payload"], {a["source_layer"]: [doc]})
        validate_evidence(a["payload"], [doc])
        # A genuine omission within this layer still fails completeness validation.
        with pytest.raises(ValueError, match="omitted explicit"):
            validate_result("api-map", {"services": []}, {a["source_layer"]: [doc]})


def test_saved_old_import_documents_are_scoped_without_rewriting_sources():
    converted = convert(layered_api(), "old", "api_extraction.json")
    maps = [a for a in converted["artifacts"] if a["task"] == "api-map"]
    combined = {
        **maps[0]["document"],
        "lines": sorted(
            maps[0]["document"]["lines"] + maps[1]["document"]["lines"], key=lambda r: r["number"]
        ),
    }
    old = {**maps[1], "document": combined}
    before = deepcopy(old)
    scoped = scoped_imports([old], {"source_layer": "SR"})[0]
    assert old == before
    assert scoped["document"] == maps[1]["document"]
    validate_result("api-map", scoped["payload"], {"SR": [scoped["document"]]})


def test_layer_scoping_does_not_guess_urls_or_drop_unclassified_downstream_calls():
    doc = {
        "source_id": "spec",
        "name": "sr.md",
        "channel": "normal",
        "lines": [
            {"number": 41, "text": "## Internal interface"},
            {"number": 42, "text": "ServiceA calls ServiceB: POST /not-a-layer-prefix"},
        ],
    }
    assert scoped_api_document(doc, "RR") == doc
    assert scoped_api_document(doc, "SR") == doc
    with pytest.raises(ValueError, match="not-a-layer-prefix"):
        validate_result("api-map", {"services": []}, {"SR": [doc]})


@pytest.mark.parametrize("legacy", [False, True])
def test_current_dag_and_saved_imports_bypass_both_layer_maps_without_model(tmp_path, legacy):
    import json

    paths = write_folder(tmp_path / "input")
    from pathlib import Path

    Path(paths["api_extraction"]).write_text(json.dumps(layered_api()), encoding="utf8")
    preview, files = discover(paths=paths)
    service, p = project(tmp_path / "data")
    try:
        apply(service, p, preview, files, adopt_partial=True)
        known = imported_sources(snapshot(p))
        meta = read_json(p / "project.json")
        docs = read_project_documents(p, meta["sources"]["test"], "test")
        ex = Execution(p / "run", mocks={})
        if legacy:
            # Simulate old frozen import metadata, without rewriting formal outputs.
            for row in ex.import_snapshot:
                maps = [a for a in row.get("artifacts", []) if a["task"] == "api-map"]
                if len(maps) == 2:
                    lines = sorted(
                        maps[0]["document"]["lines"] + maps[1]["document"]["lines"],
                        key=lambda r: r["number"],
                    )
                    for a in maps:
                        a["document"]["lines"] = deepcopy(lines)
        build_pipeline(ex, [known["RR"]], [known["SR"]], docs)
        keep = {
            "source-index",
            "components-context",
            "components",
            "rr-api-context",
            "sr-api-context",
            "rr-api-map",
            "sr-api-map",
            "rr-api-index",
            "sr-api-index",
        }
        ex.scheduler.tasks = {k: v for k, v in ex.scheduler.tasks.items() if k in keep}

        def no_model(task, inputs, record):
            if task == "components":
                # The new scope partition requires a composition result. This
                # fixture declares no external services; only API model calls
                # are forbidden by this imported-map reuse test.
                return {"components": [], "relations": []}, {"provider": "offline_fixture"}
            pytest.fail("Imported complete layer map should not invoke a model")

        ex.semantic = no_model
        assert ex.scheduler.run()["complete"]
        for task, aid in (("rr-api-map", "A1"), ("sr-api-map", "A2")):
            state = ex.scheduler.state["tasks"][task]
            assert state["status"] == "passed"
            value = read_json(ex.root / state["output_file"])["payload"]
            assert [i["id"] for s in value["services"] for i in s["interfaces"]] == [aid]
    finally:
        service.pool.shutdown()


def business_entities():
    return {
        "entities": [
            {
                "id": "item",
                "name": "商品",
                "attributes": [
                    {
                        "name": "name",
                        "data_type": "string",
                        "required": None,
                        "operation": "create",
                        "constraints": [],
                        "source_refs": R,
                    }
                ],
                "business_rules": [],
                "source_refs": R,
            }
        ],
        "pending": [],
    }


def test_domain_pending_without_status_can_report_absent_information():
    value = business_entities()
    value["pending"] = [
        {"object": "商品.name长度", "reason": "本片段没有声明长度上限", "source_refs": []}
    ]
    validate_result("business-entities", value, {"normal-documents": [], "known": R})


def test_known_attribute_needs_own_evidence_and_reports_exact_repair_location():
    value = business_entities()
    value["entities"][0]["attributes"][0]["source_refs"] = []
    with pytest.raises(ValueError, match=r"/entities/0/attributes/0/source_refs; record=.*name"):
        validate_result("business-entities", value, {"normal-documents": [], "known": R})


def test_pending_exemption_does_not_hide_nested_known_facts_or_fake_citations():
    # Only the pending record itself may lack evidence, not known children.
    with pytest.raises(ValueError, match=r"/pending/0/known/source_refs"):
        refs_required({"pending": [{"source_refs": [], "known": {"source_refs": []}}]})
    value = business_entities()
    value["pending"] = [
        {
            "object": "unknown",
            "reason": "missing",
            "source_refs": [{**R[0], "quote": "fabricated quote"}],
        }
    ]
    with pytest.raises(ValueError, match="evidence outside"):
        validate_result("business-entities", value, {"normal-documents": [], "known": R})
