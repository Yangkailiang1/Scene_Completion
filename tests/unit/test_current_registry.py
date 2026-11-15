import pytest

from scene_completion.domain.concern_registry import default_registry, validate_registry
from scene_completion.infrastructure.storage import fingerprint, write_json
from scene_completion.review.decisions.project_review import (
    project_registry,
    registry_view,
    save_registry,
)


def test_only_current_registry_version_is_accepted():
    value = default_registry()
    assert "api.data.legality" not in value["definitions"]
    assert "service.resource_mutation.business_constraint" not in value["definitions"]
    assert value["definitions"]["service.business_attribute_constraint"]
    value["version"] = "obsolete-protocol"
    value["hash"] = fingerprint({k: v for k, v in value.items() if k != "hash"})
    with pytest.raises(ValueError, match="unsupported"):
        validate_registry(value)


def test_current_snapshot_is_pinned_without_migration(tmp_path):
    value = default_registry()
    value["definitions"]["api.data.type"]["description"] = "项目审核过的说明"
    value["hash"] = fingerprint({k: v for k, v in value.items() if k != "hash"})
    write_json(tmp_path / "run/registry_override.json", value)
    assert project_registry(tmp_path) == value
    assert not (tmp_path / "concern_versions").exists()


def test_explicit_default_upgrade_preserves_custom_keys_and_frozen_snapshot(tmp_path):
    from copy import deepcopy

    old = default_registry()
    old.pop("reference_templates")
    old.pop("scopes")
    for definition in old["definitions"].values():
        definition.pop("scope", None)
    old["definitions"]["service.crud.create.idempotency"]["enabled"] = False
    old["definitions"]["global.idempotency"]["enabled"] = True
    custom = deepcopy(old["definitions"]["global.call_order"])
    custom.update(key="custom.chain", label="项目自定义链路", description="项目保留的具体规则")
    old["definitions"][custom["key"]] = custom
    old["hash"] = fingerprint({k: v for k, v in old.items() if k != "hash"})
    path = tmp_path / "run/registry_override.json"
    write_json(path, old)
    frozen = path.read_bytes()
    assert project_registry(tmp_path) == old
    assert path.read_bytes() == frozen
    assert not (tmp_path / "concern_versions").exists()
    preview = save_registry(
        tmp_path, {"expected_hash": old["hash"], "apply_current_defaults": True, "dry_run": True}
    )
    assert preview["valid"] and not preview["saved"]
    assert path.read_bytes() == frozen
    upgraded = save_registry(
        tmp_path,
        {
            "expected_hash": old["hash"],
            "apply_current_defaults": True,
            "note": "显式采用三范围规则",
        },
    )
    definitions = upgraded["registry"]["definitions"]
    assert definitions["service.crud.create.idempotency"]["enabled"]
    assert not definitions["global.idempotency"]["enabled"]
    assert definitions["custom.chain"]["description"] == custom["description"]
    assert definitions["custom.chain"]["scope"] == "business_chain"
    assert "custom.chain" in upgraded["registry"]["profiles"]["business_chain"]
    assert registry_view(tmp_path, old["hash"])["registry"] == old
    assert registry_view(tmp_path, old["hash"])["read_only"]


def test_saving_current_scope_profiles_does_not_move_project_rules_back_to_interactions(tmp_path):
    current = registry_view(tmp_path)
    current["registry"]["definitions"]["api.data.type"]["description"] += "；本项目说明"
    saved = save_registry(
        tmp_path, {"expected_hash": current["current_hash"], "registry": current["registry"]}
    )["registry"]
    assert saved["profiles"]["architecture"] == ["service.base.availability"]
    assert "service.base.availability" not in saved["profiles"]["base"]
    assert "service_relation.data_isolation" in saved["profiles"]["business_chain"]
    assert "service_relation.data_isolation" not in saved["profiles"]["relation"]
    assert saved["profiles"]["global"] == []
    assert saved["reference_templates"] == default_registry()["reference_templates"]
