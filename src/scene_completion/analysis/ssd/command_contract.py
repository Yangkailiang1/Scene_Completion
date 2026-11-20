"""Compatibility imports for the stage-organized SSD workflow."""

from scene_completion.workflow.ssd.generate.command_fields import (
    _record_command_sources,
    generate_fields,
    signature,
)
from scene_completion.workflow.ssd.input_conversion.function_tree import (
    LOCATIONS,
    _location,
    catalogue,
)
from scene_completion.workflow.ssd.shared.command_bindings import (
    _HTTP,
    _gap,
    _pick,
    associate_entities,
    attach,
)

__all__ = [
    "LOCATIONS",
    "_HTTP",
    "_gap",
    "_location",
    "_pick",
    "_record_command_sources",
    "associate_entities",
    "attach",
    "catalogue",
    "generate_fields",
    "signature",
]
