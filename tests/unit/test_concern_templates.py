from copy import deepcopy

from scene_completion.analysis.ssd.inverse import recognize_records
from scene_completion.analysis.ssd.pipeline import build_cases, generate_g
from scene_completion.domain.concern_presentation import presentation
from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.concern_templates import reference_catalog, templates_for
from tests.support.paths import ROOT


def test_reference_catalog_covers_every_active_check_and_authentication_five_variants():
    registry = default_registry()
    catalog = reference_catalog()
    for key, definition in registry["definitions"].items():
        if definition.get("enabled", True) and definition["kind"] == "check":
            assert catalog["by_key"][key]
    auth = templates_for("human.authentication")
    assert {v["variant_id"] for v in auth} == {
        "missing_credential",
        "empty_credential",
        "malformed_credential",
        "invalid_token",
        "expired_token",
    }
    assert len(templates_for("human.authorization")) == 2
    assert len(
        {v["template_id"] for variants in catalog["by_key"].values() for v in variants}
    ) == sum(map(len, catalog["by_key"].values()))
    auth[0]["condition"] = "外部修改"
    assert templates_for("human.authentication")[0]["condition"] != "外部修改"


def test_scopes_keep_layer_ids_and_retire_duplicate_global_idempotency():
    registry = default_registry()
    definitions = registry["definitions"]
    assert definitions["service.base.availability"]["layer"] == "base"
    assert definitions["service.base.availability"]["scope"] == "architecture"
    assert set(registry["profiles"]["business_chain"]) == {
        "service_relation.data_isolation",
        "global.dependency_consistency",
        "global.call_order",
        "global.cascade_operation",
    }
    assert not definitions["global.idempotency"]["enabled"]
    assert not definitions["service.resource_mutation.idempotency"]["enabled"]
    for kind in ("create", "update", "delete"):
        key = f"service.crud.{kind}.idempotency"
        assert definitions[key]["scope"] == "interaction" and definitions[key]["enabled"]
        assert key in registry["profiles"]["functional"][kind]
    paths = presentation(definitions)
    assert paths["paths"]["service.base.availability"][0][0] == "项目架构关注点"
    assert paths["paths"]["service_relation.data_isolation"][0][0] == "业务链路关注点"


def test_real_ssd_templates_keep_lineage_and_project_rules_outside_interaction():
    bundle = build_cases(ROOT / "datasets/mini-mall", ["UC-003"])[0]
    g = bundle["channels"]["G"]
    auth = [
        s
        for s in g["scenarios"]
        if s["step_id"] == "RR-003-REQ" and s["key"] == "human.authentication"
    ]
    assert len(auth) == 5
    assert len({s["id"] for s in auth}) == 5
    catalog = reference_catalog()["by_key"]
    for scene in g["scenarios"]:
        assert scene["scope"] == "interaction"
        assert scene["generation_origin"] in {"reference_template", "deterministic_constraint"}
        assert scene["template_id"] in {v["template_id"] for v in catalog[scene["key"]]}
    assert any(s["key"] == "service.crud.update.idempotency" for s in g["scenarios"])
    assert not any(c["key"] == "service.base.availability" for c in g["concerns"])
    assert not any(c["key"] == "service_relation.data_isolation" for c in g["concerns"])
    old = deepcopy(bundle)
    old["channels"] = {"E": {"scenarios": [{"condition": "伪造答案"}]}, "GT": {"scenarios": []}}
    assert generate_g(old) == g


def test_validity_uses_declared_reference_not_identifier_spelling_or_response():
    bundle = build_cases(ROOT / "datasets/mini-mall", ["UC-003"])[0]
    step = next(s for s in bundle["steps"] if s["id"] == "SR-003-REQ")
    field = next(f for f in step["data"] if f["name"] == "productId")
    assert not any(c["key"] == "api.data.validity" for c in generate_g(bundle)["concerns"])
    field["constraints"].append(
        {"kind": "reference", "value": "Product", "source_refs": field["source_refs"]}
    )
    scenes = [s for s in generate_g(bundle)["scenarios"] if s["key"] == "api.data.validity"]
    assert {s["variant_id"] for s in scenes} == {"missing_reference", "deleted_reference"}
    assert all(
        s["field_id"] == field["id"] and s["source_refs"] == field["source_refs"] for s in scenes
    )
    step["direction"] = "return"
    assert not any(c["key"] == "api.data.validity" for c in generate_g(bundle)["concerns"])


def test_inverse_idempotency_is_local_while_project_sources_preserve_independent_records():
    bundle = build_cases(ROOT / "datasets/mini-mall", ["UC-003"])[0]
    gt = bundle["channels"]["GT"]
    idem = [s for s in gt["scenarios"] if s["key"] == "service.crud.update.idempotency"]
    assert len(idem) == 1 and idem[0]["step_id"] == "SR-003-REQ"
    assert not any("Idempotency-Key" in s["condition"] for s in gt["pending"])
    availability = next(s for s in gt["project_records"] if s["scope"] == "architecture")
    assert availability["case_id"] == "UC-003" and availability["source_refs"]
    assert availability["raw"] and availability["id"]
    record = {
        "id": "independent-chain",
        "condition": "前置操作未完成就执行后续操作",
        "expected": "拒绝操作",
        "source_refs": [],
        "raw": {},
    }
    result = recognize_records(bundle, [record], "E")
    assert not result["scenarios"] and not result["pending"]
    assert result["project_records"][0]["key"] == "global.call_order"
    assert result["project_records"][0]["expected"] == record["expected"]
