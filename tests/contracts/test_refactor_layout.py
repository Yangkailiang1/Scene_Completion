"""Structural changes must preserve current task contracts and cache identities."""

from copy import deepcopy

from scene_completion.domain.concern_registry import active_registry_identity, default_registry
from scene_completion.domain.contracts import PROTOCOL, SCHEMAS, schema
from scene_completion.infrastructure.paths import PROGRAM_ROOT, SKILLS_ROOT
from scene_completion.infrastructure.storage import read_json
from scene_completion.workflow.semantics import code_version, component_version


def test_source_resources_and_current_schema_exports():
    assert PROTOCOL == "scene-workflow-v5"
    assert (PROGRAM_ROOT / "src/scene_completion/domain/contracts.py").is_file()
    assert (SKILLS_ROOT / "scene-components/SKILL.md").is_file()
    assert not (PROGRAM_ROOT / ".cac/tools/scene_completion").exists()
    for task in SCHEMAS:
        published = PROGRAM_ROOT / "docs/scene-workflow-v5/schemas" / (task + ".schema.json")
        if published.exists():
            assert schema(task) == read_json(published), task


def test_refactor_has_an_explicit_baseline_semantic_identity_for_every_task():
    versions = read_json(PROGRAM_ROOT / "src/scene_completion/workflow/task_semantics.json")
    assert versions["protocol"] == PROTOCOL
    assert versions["baseline_commit"].startswith("8732a56")
    assert set(SCHEMAS) <= versions["tasks"].keys()
    assert all(code_version(task) == version for task, version in versions["tasks"].items())
    assert component_version("artifact-imports")


def test_disabled_metadata_does_not_change_active_semantics_but_a_rule_does():
    value = default_registry()
    augmented = deepcopy(value)
    augmented["definitions"]["project.disabled"] = {"enabled": False}
    assert active_registry_identity(value) == active_registry_identity(augmented)
    augmented["definitions"]["api.data.type"]["description"] += " changed rule"
    assert active_registry_identity(value) != active_registry_identity(augmented)
