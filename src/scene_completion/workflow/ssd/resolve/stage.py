"""Resolve operation, constraints and independent evidence for one SSD case."""

from copy import deepcopy

from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, STRUCTURED_PROFILES
from scene_completion.domain.ssd import validation as ssd_validation
from scene_completion.workflow.ssd.shared.semantic_execution import _semantic_available


def _resolve(ex, bundle, record):
    bundle = deepcopy(bundle)
    if bundle.get("analysis_profile") not in STRUCTURED_PROFILES:
        from scene_completion.workflow.ssd.resolve import legacy_resolution

        return legacy_resolution.resolve(ex, bundle, record)

    from scene_completion.workflow.ssd.resolve import entity_semantics, participants

    def semantic(task, inputs):
        value, _ = ex.semantic(task, inputs, record)
        return value

    executor = semantic if _semantic_available(ex) else None
    participants.classify(bundle, executor)
    if bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE:
        from scene_completion.workflow.ssd.resolve import classification, operations

        bundle["coverage_policy"] = GRAIN_POLICY
        operations.resolve(bundle, executor)
    entity_semantics.infer(bundle, executor)
    if bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE:
        classification.classify(bundle, executor)
    else:
        entity_semantics.classify(bundle, executor)
    return ssd_validation.validate(bundle)
