import json
from pathlib import Path

import pytest

from scene_completion.analysis.ssd.core_input import convert, validate_core
from scene_completion.analysis.ssd.entity_semantics import classify, infer, validate_result
from scene_completion.analysis.ssd.pipeline import build_cases, rebind_steps
from scene_completion.domain.current_scope import ENTITY_PROFILE
from scene_completion.domain.ssd.matching import binding
from scene_completion.infrastructure.storage import write_json

DATA = Path(__file__).resolve().parents[2] / "datasets/mini-mall"


def test_entity_core_excludes_transport_fields_and_preserves_extensions(tmp_path):
    output = tmp_path / "core"
    assert convert(DATA, output, ["UC-002"], profile=ENTITY_PROFILE)["output"]
    assert validate_core(output)["valid"]
    main = next(output.glob("cases/*/main-success.json"))
    value = json.loads(main.read_text())
    assert value["analysis_profile"] == ENTITY_PROFILE
    assert value["case"]["id"] == "UC-002"
    assert all("declared_fields" not in row for row in value["steps"])
    assert (main.parent / "source-map.json").is_file()
    assert not (output / "api_extraction.json").exists()
    bundle = build_cases(output, generate=False)[0]
    assert not bundle["apis"]
    assert all(not row["data"] for row in bundle["steps"])
    assert all(row["original"]["extension_id"] for row in bundle["channels"]["GT"]["pending"])
    assert len({r["id"] for r in bundle["channels"]["GT"]["pending"]}) == len(
        json.loads(main.with_name("extension-mapping.json").read_text())["items"]
    )
    value["steps"][0]["operation"]["crud"] = ["display"]
    write_json(main, value)
    assert not validate_core(output)["valid"]


def party(party_id, **extra):
    return {"id": party_id, "name": party_id, "type": "service", **extra}


def test_independent_classification_uses_canonical_entity_anchor_and_retains_occurrence():
    from scene_completion.domain.concern_registry import default_registry
    from scene_completion.domain.current_scope import current_registry
    from scene_completion.domain.ssd.construction import channel, pending

    def step(sid, order, name, sender, receiver, kind="interaction", kinds=()):
        return {
            "id": sid,
            "order": order,
            "direction": "request",
            "kind": kind,
            "sender": sender,
            "receiver": receiver,
            "data": [],
            "api_id": None,
            "entity_ids": ["Product"],
            "operation": {"name": name, "kinds": list(kinds), "kinds_source": "declared"},
            "source_refs": [],
        }

    user, service = party("buyer", external=True), party("catalog")
    database = party("database", external=True, technology="database")
    minimum = {"concern_key": "api.data.range", "operation": "minimum", "value": 1}
    maximum = {"concern_key": "api.data.range", "operation": "maximum", "value": 50}
    bundle = {
        "case": {"id": "case", "name": "创建商品"},
        "analysis_profile": ENTITY_PROFILE,
        "registry": current_registry(default_registry()),
        "steps": [
            step("entry", 1, "发起创建", user, service, kinds=("create",)),
            step("check", 2, "校验 Product.name 字段", service, service, "action"),
            step("store", 3, "数据库检查后写入", service, database, kinds=("read", "create")),
        ],
        "entities": [
            {"id": "Product", "attributes": [{"name": "name", "atoms": [minimum, maximum]}]}
        ],
        "channels": {key: channel() for key in ("G", "E", "GT")},
        "gt_source_available": True,
    }
    bundle["channels"]["E"]["pending"] = [
        pending(
            "raw",
            "名称低于下限",
            original={
                "id": "raw",
                "condition": "名称低于下限",
                "failure_step_id": "store",
                "source_refs": [],
            },
            needs_semantic=True,
        )
    ]
    bundle["channels"]["GT"]["pending"] = [
        pending(
            "normal",
            "合法边界被接受",
            original={
                "id": "normal",
                "condition": "合法边界被接受",
                "extension_id": "EXT-01",
                "source_refs": [],
            },
            needs_semantic=True,
        )
    ]

    def semantic(task, inputs):
        assert task == "ssd-entity-classify"
        ids = {row["id"] for row in inputs["records"]}
        assert "G" not in inputs and "channels" not in inputs
        if inputs["channel"] == "E":
            assert ids == {"raw"}
            records = [
                {
                    "record_id": "raw",
                    "kind": "exception",
                    "reason": "明确的下界失败",
                    "bindings": [
                        {
                            "step_id": "store",
                            "target": "entity",
                            "key": "api.data.range",
                            "entity_id": "Product",
                            "attribute": "name",
                            "condition": "name < 1",
                            "expected": "",
                        }
                    ],
                }
            ]
        else:
            assert ids == {"normal"}
            records = [
                {"record_id": "normal", "kind": "normal", "reason": "成功边界", "bindings": []}
            ]
        return validate_result(task, {"records": records}, inputs)

    infer(bundle, None)
    classify(bundle, semantic)
    g = [row for row in bundle["channels"]["G"]["scenarios"] if row["key"] == "api.data.range"]
    assert len(g) == 2 and {row["step_id"] for row in g} == {"check"}
    condition = [
        row for row in bundle["channels"]["G"]["concerns"] if row["key"] == "api.data.range"
    ]
    assert len(condition) == 1
    e = bundle["channels"]["E"]["scenarios"][0]
    assert e["step_id"] == "check" and e["failure_step_id"] == "store"
    assert binding(e) == binding(g[0])
    assert not bundle["channels"]["GT"]["scenarios"]
    assert bundle["source_classifications"]["GT"][0]["kind"] == "normal"
    assert bundle["gt_identification_run_complete"]
    keys = {row["key"] for row in bundle["channels"]["G"]["concerns"] if row["step_id"] == "store"}
    assert {
        "database.special_characters",
        "service.base.availability",
        "service.crud.create.idempotency",
    } <= keys
    assert "database.storage_validity" not in keys
    assert "service.query_retrieval.data_visibility" not in keys
    bundle["steps"][1]["operation"]["kinds"] = ["display"]
    with pytest.raises(ValueError, match="create/read/update/delete"):
        rebind_steps(bundle, bundle)


def test_core_sidecars_bypass_paid_artifact_conversion(tmp_path):
    from scene_completion.inputs.imports import artifact_imports

    files = [{"name": "existing-exceptions.json", "content": json.dumps({"exceptions": []})}]
    result = artifact_imports.receive(tmp_path, files)
    item = result["received"][0]["id"]
    row = artifact_imports.view(tmp_path, item)
    assert row["status"] == "converted"
    assert row["core_input"]
    assert not row["artifacts"]
    # An explicit direct converter call must also bypass the model.
    assert artifact_imports.convert(tmp_path, item, None)["status"] == "converted"
