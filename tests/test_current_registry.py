import pytest

from scene_completion.domain.concern_registry import default_registry, validate_registry
from scene_completion.infrastructure.storage import fingerprint, write_json
from scene_completion.review.project_review import project_registry


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
