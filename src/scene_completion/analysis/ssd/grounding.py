"""Compatibility imports for the stage-organized SSD workflow."""

from scene_completion.workflow.ssd.compare import alignment as _alignment
from scene_completion.workflow.ssd.compare.alignment import (
    ALIGN,
    _add_matches,
    _allowed_keys,
    _auth_alignment,
    _candidates,
    _decision,
    _keys,
    _uses_step,
    align,
    strip_align_summary,
)
from scene_completion.workflow.ssd.resolve import classification as _classification
from scene_completion.workflow.ssd.resolve.classification import (
    CLASSIFY,
    _excerpt,
    _verified_parts,
    classify,
)

__all__ = [
    "ALIGN",
    "CLASSIFY",
    "_add_matches",
    "_allowed_keys",
    "_auth_alignment",
    "_candidates",
    "_decision",
    "_excerpt",
    "_keys",
    "_uses_step",
    "_verified_parts",
    "align",
    "classify",
    "strip_align_summary",
    "validate_result",
]


def validate_result(task, result, inputs):
    if task == CLASSIFY:
        return _classification.validate_result(task, result, inputs)
    return _alignment.validate_result(task, result, inputs)
