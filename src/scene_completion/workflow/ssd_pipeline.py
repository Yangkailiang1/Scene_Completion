"""Compatibility imports for the stage-organized SSD workflow."""

from scene_completion.workflow.ssd.compare.stage import (
    _compare,
    _compare_pairs,
    _reuse_machine_decisions,
    _review_identity,
    _review_material,
)
from scene_completion.workflow.ssd.generate.stage import _generate
from scene_completion.workflow.ssd.pipeline import (
    _tail,
    _task,
    build_from_documents,
    build_structured,
    enabled,
    finish,
    input_directory,
    progress,
)
from scene_completion.workflow.ssd.resolve.stage import _resolve
from scene_completion.workflow.ssd.shared.machine_history import _machine_baselines
from scene_completion.workflow.ssd.shared.semantic_execution import (
    _semantic_available,
    _semantic_cache_identity,
)
from scene_completion.workflow.ssd.shared_services.stage import _project_scopes

__all__ = [
    "_compare",
    "_compare_pairs",
    "_generate",
    "_machine_baselines",
    "_project_scopes",
    "_resolve",
    "_reuse_machine_decisions",
    "_review_identity",
    "_review_material",
    "_semantic_available",
    "_semantic_cache_identity",
    "_tail",
    "_task",
    "build_from_documents",
    "build_structured",
    "enabled",
    "finish",
    "input_directory",
    "progress",
]
