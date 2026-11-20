"""Compatibility imports for the stage-organized SSD workflow."""

from scene_completion.workflow.ssd.input_conversion.evidence_records import (
    TARGETS,
    _classification,
    _entity_attribute,
    _field_candidates,
    _locate,
    _provided,
    _supplied,
    _target_of,
    declared_entity_mismatch,
    recognize_records,
)
from scene_completion.workflow.ssd.input_conversion.requirements import existing_channel
from scene_completion.workflow.ssd.input_conversion.test_evidence import test_channel

__all__ = [
    "TARGETS",
    "_classification",
    "_entity_attribute",
    "_field_candidates",
    "_locate",
    "_provided",
    "_supplied",
    "_target_of",
    "declared_entity_mismatch",
    "existing_channel",
    "recognize_records",
    "test_channel",
]
